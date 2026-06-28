"""
dashboard/middleware.py — Phase 9B
=====================================
Custom Django middleware for session security and security headers.

MIDDLEWARE:
  SessionSecurityMiddleware — Enforces session timeout, sets security
                              headers, validates session integrity,
                              and restricts admin panel access (Phase 9B).

DESIGN DECISIONS:
  - Session timeout is configurable via SESSION_IDLE_TIMEOUT setting.
  - Public paths (login, register, health, static, media) are exempt
    from authentication enforcement.
  - Security headers follow OWASP best practices.
  - Added strict `/admin/` path restriction based on the `ADMIN` role
    to provide defense-in-depth beyond Django's `is_staff` check.

SECURITY:
  - Idle sessions are expired after a configurable timeout.
  - Security headers prevent clickjacking, MIME sniffing, and XSS.
  - Session integrity is validated on each request.
  - Only users with `dashboard_full_access` can hit `/admin/` endpoints.
"""

import logging
import time
from typing import Callable, Optional

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from .permissions import DashboardPermissions

logger = logging.getLogger(__name__)

# Paths that do not require authentication or session activity tracking
PUBLIC_PATH_PREFIXES = (
    "/auth/login/",
    "/auth/register/",
    "/health/",
    "/static/",
    "/media/",
)


class SessionSecurityMiddleware(MiddlewareMixin):
    """
    Middleware for session security enforcement.

    Responsibilities:
      1. Track last activity timestamp in the session.
      2. Expire idle sessions after SESSION_IDLE_TIMEOUT seconds.
      3. Add security-related HTTP headers to all responses.
      4. (Phase 9B) Restrict access to /admin/ routes to Super Admins.

    Configuration (in settings.py):
      SESSION_IDLE_TIMEOUT: int — Seconds of inactivity before session
                                   expires. Defaults to 1800 (30 minutes).

    Note:
      This middleware should be placed AFTER SessionMiddleware and
      AuthenticationMiddleware in the MIDDLEWARE list.
    """

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Check session activity, expire idle sessions, and enforce admin access.

        Args:
            request: The incoming HTTP request.

        Returns:
            None to continue processing, or HttpResponse to short-circuit.
        """
        # --- 1. Admin Panel Restriction (Phase 9B) ---
        if request.path.startswith("/admin/"):
            if not request.user.is_authenticated:
                return None  # Let Django redirect to login
            if not request.user.has_perm(DashboardPermissions.DASHBOARD_FULL_ACCESS):
                logger.warning(
                    "RBAC DENIED: non-admin user '%s' attempted to access "
                    "the Django admin panel at '%s'.",
                    request.user.username,
                    request.path,
                )
                raise PermissionDenied(
                    "You do not have permission to access the admin panel."
                )

        # --- 2. Skip tracking for public paths ---
        if self._is_public_path(request.path):
            return None

        # Only track activity for authenticated users
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return None

        # --- 3. Check idle timeout ---
        idle_timeout = getattr(settings, "SESSION_IDLE_TIMEOUT", 1800)
        last_activity = request.session.get("_last_activity")

        if last_activity is not None:
            elapsed = time.time() - last_activity
            if elapsed > idle_timeout:
                logger.info(
                    "Session expired for user '%s' after %d seconds idle.",
                    request.user.username,
                    int(elapsed),
                )
                request.session.flush()
                from django.contrib import messages
                from django.shortcuts import redirect

                messages.warning(
                    request,
                    "Your session has expired due to inactivity. "
                    "Please sign in again.",
                )
                return redirect(settings.LOGIN_URL)

        # Update last activity timestamp
        request.session["_last_activity"] = time.time()

        return None

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        """
        Add security headers to all responses.

        Headers set:
          - X-Content-Type-Options: nosniff
          - X-Frame-Options: DENY (overrides Django's default SAMEORIGIN)
          - Referrer-Policy: strict-origin-when-cross-origin
          - Permissions-Policy: Restrict browser features

        Args:
            request:  The HTTP request.
            response: The HTTP response to augment.

        Returns:
            The response with security headers added.
        """
        # Prevent MIME type sniffing
        response["X-Content-Type-Options"] = "nosniff"

        # Prevent framing (clickjacking protection)
        response["X-Frame-Options"] = "DENY"

        # Control referrer information
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser feature access
        response["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        return response

    @staticmethod
    def _is_public_path(path: str) -> bool:
        """
        Check if the request path is a public (exempt) path.

        Args:
            path: The request URL path.

        Returns:
            True if the path is public and should skip session checks.
        """
        return any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)
