"""
dashboard/auth_forms.py — Phase 9A
=====================================
Django form definitions for authentication workflows.

FORMS:
  CustomLoginForm        — Login with "Remember Me" checkbox.
  UserRegistrationForm   — Self-registration with email, password validation.
  UserProfileForm        — Profile update (name, email).
  CustomPasswordChangeForm — Password change with crispy layout.

DESIGN DECISIONS:
  - All forms use crispy-bootstrap5 for consistent, accessible rendering.
  - Forms leverage Django's built-in password validation pipeline
    (4 validators configured in settings.py).
  - Email is required on registration (matches User model: blank=False).
  - Username uniqueness is validated at the form level for clear error messages.

SECURITY:
  - Passwords are never stored or logged in plaintext.
  - CSRF protection is enforced by Django middleware on all POST requests.
  - Form inputs are validated server-side; client-side validation is cosmetic only.
"""

import logging
from typing import Any

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
)
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

User = get_user_model()


# ===========================================================================
# Login Form
# ===========================================================================


class CustomLoginForm(AuthenticationForm):
    """
    Extended login form with "Remember Me" functionality.

    Extends Django's AuthenticationForm to add a remember_me checkbox.
    When unchecked, the session expires when the browser closes.
    When checked, the session uses the default SESSION_COOKIE_AGE
    (configured in settings.py).

    Attributes:
        username:    Standard Django username field (relabeled).
        password:    Standard Django password field.
        remember_me: Boolean checkbox for session persistence.
    """

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Username",
                "autofocus": True,
                "autocomplete": "username",
                "id": "id_login_username",
            }
        ),
        label="Username",
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Password",
                "autocomplete": "current-password",
                "id": "id_login_password",
            }
        ),
        label="Password",
    )

    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
                "id": "id_remember_me",
            }
        ),
        label="Remember me",
        help_text="Keep me signed in on this device.",
    )

    class Meta:
        """Meta configuration for the login form."""
        fields = ("username", "password", "remember_me")


# ===========================================================================
# Registration Form
# ===========================================================================


class UserRegistrationForm(forms.ModelForm):
    """
    User self-registration form.

    Creates a new User with the ANALYST role (default from UserManager).
    Email is required to match the User model constraint (blank=False).

    Password validation uses Django's AUTH_PASSWORD_VALIDATORS pipeline:
      - UserAttributeSimilarityValidator
      - MinimumLengthValidator (8 chars)
      - CommonPasswordValidator
      - NumericPasswordValidator

    Attributes:
        username:  Unique username for login.
        email:     Required email address.
        password1: Password (validated against all validators).
        password2: Password confirmation (must match password1).
    """

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Create a password",
                "autocomplete": "new-password",
                "id": "id_register_password1",
            }
        ),
        help_text=(
            "Must be at least 8 characters. Cannot be entirely numeric "
            "or a commonly used password."
        ),
    )

    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm your password",
                "autocomplete": "new-password",
                "id": "id_register_password2",
            }
        ),
        help_text="Enter the same password again for verification.",
    )

    class Meta:
        model = User
        fields = ("username", "email")
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Choose a username",
                    "autofocus": True,
                    "autocomplete": "username",
                    "id": "id_register_username",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "you@company.com",
                    "autocomplete": "email",
                    "id": "id_register_email",
                }
            ),
        }
        labels = {
            "username": "Username",
            "email": "Email Address",
        }

    def clean_username(self) -> str:
        """
        Validate that the username is not already taken.

        Returns:
            The cleaned username string.

        Raises:
            ValidationError: If a user with this username already exists.
        """
        username = self.cleaned_data.get("username", "")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError(
                "A user with this username already exists.",
                code="username_taken",
            )
        return username

    def clean_email(self) -> str:
        """
        Validate that the email address is provided and not already in use.

        Returns:
            The cleaned, normalized email string.

        Raises:
            ValidationError: If email is empty or already registered.
        """
        email = self.cleaned_data.get("email", "").strip()
        if not email:
            raise ValidationError(
                "Email address is required.",
                code="email_required",
            )
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                "A user with this email address already exists.",
                code="email_taken",
            )
        return email

    def clean_password2(self) -> str:
        """
        Validate that both password fields match.

        Returns:
            The confirmed password string.

        Raises:
            ValidationError: If passwords don't match.
        """
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError(
                "Passwords do not match.",
                code="password_mismatch",
            )
        return password2

    def clean(self) -> dict[str, Any]:
        """
        Run Django's password validation pipeline on the password.

        This validates against all AUTH_PASSWORD_VALIDATORS configured
        in settings.py (similarity, length, common, numeric).
        """
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")

        if password1:
            # Import here to use Django's password validation framework
            from django.contrib.auth.password_validation import (
                validate_password,
            )

            try:
                # Pass the user instance for similarity check
                user = User(
                    username=cleaned_data.get("username", ""),
                    email=cleaned_data.get("email", ""),
                )
                validate_password(password1, user=user)
            except ValidationError as e:
                self.add_error("password1", e)

        return cleaned_data

    def save(self, commit: bool = True) -> "User":
        """
        Create the user with a properly hashed password.

        Uses the custom UserManager.create_user() which enforces
        role assignment (defaults to ANALYST).

        Args:
            commit: Whether to save to the database immediately.

        Returns:
            The newly created User instance.
        """
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
        )
        logger.info(
            "New user registered: '%s' (%s).",
            user.username,
            user.email,
        )
        return user


# ===========================================================================
# Profile Form
# ===========================================================================


class UserProfileForm(forms.ModelForm):
    """
    Form for updating user profile information.

    Allows users to update their display name and email address.
    Username and role are displayed as read-only context, not editable
    through this form.

    Note: Password changes are handled by a separate
    CustomPasswordChangeForm.
    """

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "First name",
                    "id": "id_profile_first_name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Last name",
                    "id": "id_profile_last_name",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "you@company.com",
                    "id": "id_profile_email",
                }
            ),
        }

    def clean_email(self) -> str:
        """
        Validate that the new email is not taken by another user.

        Returns:
            The cleaned email string.

        Raises:
            ValidationError: If the email belongs to a different user.
        """
        email = self.cleaned_data.get("email", "").strip()
        if not email:
            raise ValidationError(
                "Email address is required.",
                code="email_required",
            )
        # Exclude the current user from the uniqueness check
        if (
            User.objects.filter(email__iexact=email)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise ValidationError(
                "This email address is already in use by another account.",
                code="email_taken",
            )
        return email


# ===========================================================================
# Password Change Form
# ===========================================================================


class CustomPasswordChangeForm(PasswordChangeForm):
    """
    Extended password change form with Bootstrap styling.

    Extends Django's built-in PasswordChangeForm which handles:
      - Current password verification
      - New password validation (AUTH_PASSWORD_VALIDATORS)
      - Password confirmation matching

    Only styling and widget attributes are customized.
    """

    old_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter current password",
                "autocomplete": "current-password",
                "id": "id_old_password",
            }
        ),
    )

    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter new password",
                "autocomplete": "new-password",
                "id": "id_new_password1",
            }
        ),
        help_text=(
            "Must be at least 8 characters. Cannot be entirely numeric "
            "or a commonly used password."
        ),
    )

    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm new password",
                "autocomplete": "new-password",
                "id": "id_new_password2",
            }
        ),
    )
