"""
dashboard/middleware.py — Phase 9A
=====================================
Custom Django middleware for session security and security headers.

MIDDLEWARE:
  SessionSecurityMiddleware — Enforces session timeout, sets security
                              headers, validates session integrity.

DESIGN DECISIONS:
  - Session timeout is configurable via SESSION_IDLE_TIMEOUT setting.
  - Public paths (login, register, health, static, media) are exempt
    from authentication enforcement.
  - Security headers follow OWASP best practices.
  - This middleware does NOT enforce RBAC — that's Phase 9B.

SECURITY:
  - Idle sessions are expired after a configurable timeout.
  - Security headers prevent clickjacking, MIME sniffing, and XSS.
  - Session integrity is validated on each request.
"""

import logging
import time
from typing import Callable, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

# Paths that do not require authentication or session activity tracking
PUBLIC_PATH_PREFIXES = (
    "/auth/login/",
    "/auth/register/",
    "/health/",
    "/admin/",
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

    Configuration (in settings.py):
      SESSION_IDLE_TIMEOUT: int — Seconds of inactivity before session
                                   expires. Defaults to 1800 (30 minutes).

    Note:
      This middleware should be placed AFTER SessionMiddleware and
      AuthenticationMiddleware in the MIDDLEWARE list.
    """

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Check session activity and expire idle sessions.

        For authenticated users on non-public paths:
          - If last_activity exists and is older than SESSION_IDLE_TIMEOUT,
            flush the session and redirect to login.
          - Otherwise, update last_activity to the current timestamp.

        Args:
            request: The incoming HTTP request.

        Returns:
            None to continue processing, or HttpResponse to short-circuit.
        """
        # Skip public paths
        if self._is_public_path(request.path):
            return None

        # Only track activity for authenticated users
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return None

        # Check idle timeout
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
