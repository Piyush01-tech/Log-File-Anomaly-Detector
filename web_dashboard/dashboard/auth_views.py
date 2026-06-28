"""
dashboard/auth_views.py — Phase 9A
=====================================
Django class-based views for authentication workflows.

VIEWS:
  CustomLoginView        — Login with audit logging and "Remember Me".
  CustomLogoutView       — Logout with audit logging.
  RegistrationView       — User self-registration (ANALYST role).
  ProfileView            — View/update user profile.
  CustomPasswordChangeView — Change password with success messaging.

DESIGN DECISIONS:
  - All views extend Django's built-in auth views where possible
    to leverage battle-tested authentication logic.
  - Audit logging (AuditLog model) is integrated into login/logout
    flows to satisfy enterprise compliance requirements.
  - "Remember Me" controls session duration: unchecked = browser
    session only; checked = SESSION_COOKIE_AGE from settings.
  - IP address is captured from request.META for audit entries.

SECURITY:
  - All views requiring authentication use LoginRequiredMixin.
  - CSRF protection is enforced by Django middleware.
  - Session key is regenerated on login (Django default behavior).
  - Passwords are validated by Django's AUTH_PASSWORD_VALIDATORS.
"""

import logging
from typing import Any, Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
)
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView

from .auth_forms import (
    CustomLoginForm,
    CustomPasswordChangeForm,
    UserProfileForm,
    UserRegistrationForm,
)
from .models import AuditLog

logger = logging.getLogger(__name__)

User = get_user_model()


# ===========================================================================
# Utility Functions
# ===========================================================================


def _get_client_ip(request: HttpRequest) -> Optional[str]:
    """
    Extract the client IP address from the request.

    Checks X-Forwarded-For header first (for reverse proxy setups
    like Nginx), then falls back to REMOTE_ADDR.

    Args:
        request: The Django HTTP request object.

    Returns:
        Client IP address string, or None if unavailable.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs; take the first
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _create_audit_log(
    user: Any,
    action: str,
    request: HttpRequest,
    job: Any = None,
) -> None:
    """
    Create an audit log entry for a user action.

    This is a convenience wrapper around AuditLog.objects.create()
    that handles IP extraction and error suppression.

    Args:
        user:    The User instance performing the action.
        action:  The AuditLog.Action choice string.
        request: The HTTP request (for IP extraction).
        job:     Optional AnalysisJob related to this action.
    """
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            ip_address=_get_client_ip(request),
            job=job,
        )
        logger.debug(
            "Audit log created: user='%s', action='%s'.",
            user.username if user else "anonymous",
            action,
        )
    except Exception:
        # Audit logging should never break authentication flows
        logger.exception(
            "Failed to create audit log entry for action '%s'.", action
        )


# ===========================================================================
# Login View
# ===========================================================================


class CustomLoginView(LoginView):
    """
    Custom login view with audit logging and "Remember Me" support.

    Extends Django's LoginView to:
      1. Use our CustomLoginForm with the "Remember Me" checkbox.
      2. Create an AuditLog entry on successful login.
      3. Control session duration based on "Remember Me" selection.
      4. Redirect authenticated users away from the login page.

    Template: dashboard/auth/login.html
    URL:      /auth/login/
    """

    template_name = "dashboard/auth/login.html"
    form_class = CustomLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form: CustomLoginForm) -> HttpResponse:
        """
        Handle successful login.

        Processes "Remember Me" before calling the parent's form_valid
        (which calls auth.login()). Then creates an audit log entry
        and adds a success message.

        Args:
            form: The validated login form.

        Returns:
            HTTP redirect to LOGIN_REDIRECT_URL or 'next' parameter.
        """
        # Handle "Remember Me"
        remember_me = form.cleaned_data.get("remember_me", False)
        if not remember_me:
            # Session expires when browser closes
            self.request.session.set_expiry(0)
        else:
            # Use the default SESSION_COOKIE_AGE from settings
            self.request.session.set_expiry(settings.SESSION_COOKIE_AGE)

        # Call parent's form_valid which performs the actual login
        response = super().form_valid(form)

        # Audit log the login event
        _create_audit_log(
            user=self.request.user,
            action=AuditLog.Action.LOGIN,
            request=self.request,
        )

        messages.success(
            self.request,
            f"Welcome back, {self.request.user.username}!",
        )

        logger.info(
            "User '%s' logged in from %s.",
            self.request.user.username,
            _get_client_ip(self.request),
        )

        return response

    def form_invalid(self, form: CustomLoginForm) -> HttpResponse:
        """
        Handle failed login attempt.

        Adds a warning message and logs the failed attempt.

        Args:
            form: The invalid login form.

        Returns:
            HTTP response re-rendering the login form with errors.
        """
        messages.error(
            self.request,
            "Invalid username or password. Please try again.",
        )
        logger.warning(
            "Failed login attempt from %s.",
            _get_client_ip(self.request),
        )
        return super().form_invalid(form)


# ===========================================================================
# Logout View
# ===========================================================================


class CustomLogoutView(LogoutView):
    """
    Custom logout view with audit logging.

    Extends Django's LogoutView to create an AuditLog entry before
    the session is destroyed. The user is redirected to the login page.

    Template: None (redirects immediately).
    URL:      /auth/logout/
    """

    next_page = reverse_lazy("auth:login")
    http_method_names = ["post", "get"]

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        """
        Log the logout event before destroying the session.

        The audit log must be created BEFORE super().dispatch()
        because that call flushes the session and anonymizes the user.

        Args:
            request: The HTTP request.

        Returns:
            HTTP redirect to the login page.
        """
        if request.user.is_authenticated:
            _create_audit_log(
                user=request.user,
                action=AuditLog.Action.LOGOUT,
                request=request,
            )
            logger.info(
                "User '%s' logged out from %s.",
                request.user.username,
                _get_client_ip(request),
            )
            messages.info(request, "You have been signed out successfully.")

        return super().dispatch(request, *args, **kwargs)


# ===========================================================================
# Registration View
# ===========================================================================


class RegistrationView(CreateView):
    """
    User self-registration view.

    Creates a new user with the default ANALYST role. After successful
    registration, the user is automatically logged in and redirected
    to the home page.

    Template: dashboard/auth/register.html
    URL:      /auth/register/
    """

    template_name = "dashboard/auth/register.html"
    form_class = UserRegistrationForm
    success_url = reverse_lazy("dashboard:home")

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        """
        Redirect authenticated users away from the registration page.

        Args:
            request: The HTTP request.

        Returns:
            HTTP redirect if authenticated, or normal dispatch.
        """
        if request.user.is_authenticated:
            return HttpResponseRedirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: UserRegistrationForm) -> HttpResponse:
        """
        Handle successful registration.

        Creates the user, logs them in, creates an audit log entry,
        and redirects to the home page.

        Args:
            form: The validated registration form.

        Returns:
            HTTP redirect to success_url.
        """
        # Create the user (form.save() uses UserManager.create_user)
        user = form.save()

        # Auto-login the newly registered user
        login(self.request, user)

        # Audit log the registration as a login event
        _create_audit_log(
            user=user,
            action=AuditLog.Action.LOGIN,
            request=self.request,
        )

        messages.success(
            self.request,
            f"Welcome, {user.username}! Your account has been created.",
        )

        logger.info(
            "New user '%s' registered and logged in from %s.",
            user.username,
            _get_client_ip(self.request),
        )

        return HttpResponseRedirect(self.success_url)


# ===========================================================================
# Profile View
# ===========================================================================


class ProfileView(LoginRequiredMixin, UpdateView):
    """
    User profile management view.

    Allows authenticated users to update their display name and email.
    Username and role are displayed as read-only context.

    Template: dashboard/auth/profile.html
    URL:      /auth/profile/
    """

    template_name = "dashboard/auth/profile.html"
    form_class = UserProfileForm
    success_url = reverse_lazy("auth:profile")

    def get_object(self, queryset=None) -> "User":
        """
        Return the current authenticated user as the form object.

        Returns:
            The current User instance.
        """
        return self.request.user

    def form_valid(self, form: UserProfileForm) -> HttpResponse:
        """
        Handle successful profile update.

        Args:
            form: The validated profile form.

        Returns:
            HTTP redirect to the profile page with success message.
        """
        response = super().form_valid(form)

        messages.success(self.request, "Profile updated successfully.")
        logger.info(
            "User '%s' updated their profile.",
            self.request.user.username,
        )

        return response


# ===========================================================================
# Password Change View
# ===========================================================================


class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """
    Custom password change view with Bootstrap styling and messaging.

    Extends Django's PasswordChangeView which handles:
      - Current password verification
      - New password validation (AUTH_PASSWORD_VALIDATORS)
      - Password confirmation matching
      - Session hash update (prevents logout after password change)

    Template: dashboard/auth/password_change.html
    URL:      /auth/password-change/
    """

    template_name = "dashboard/auth/password_change.html"
    form_class = CustomPasswordChangeForm
    success_url = reverse_lazy("auth:profile")

    def form_valid(self, form: CustomPasswordChangeForm) -> HttpResponse:
        """
        Handle successful password change.

        Calls parent's form_valid (which updates the session hash
        to keep the user logged in) and adds a success message.

        Args:
            form: The validated password change form.

        Returns:
            HTTP redirect to profile page.
        """
        response = super().form_valid(form)

        messages.success(
            self.request,
            "Your password has been changed successfully.",
        )
        logger.info(
            "User '%s' changed their password.",
            self.request.user.username,
        )

        return response
