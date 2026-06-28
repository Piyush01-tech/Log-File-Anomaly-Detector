"""
dashboard/rbac_decorators.py — Phase 9B
==========================================
Function-based view (FBV) decorators for authorization enforcement.

PURPOSE:
  - Provides decorator-based authorization for function views.
  - Complements rbac_mixins.py (for CBVs) — same logic, different
    application pattern.
  - Includes audit logging for permission denials.

DECORATORS:
  @permission_required_with_audit — Checks permission, logs denial.
  @superadmin_required            — Shortcut for admin-only views.
  @owner_required                 — Object ownership check for detail views.

DESIGN DECISIONS:
  - Each decorator wraps Django's `user.has_perm()` for permission
    evaluation, ensuring consistency with Django's permission caching.
  - All denials are logged at WARNING level for security monitoring.
  - AuditLog entries are created on permission denials for compliance.
  - Decorators are composable and can be stacked.

USAGE:
  @login_required
  @permission_required_with_audit(DashboardPermissions.UPLOAD_EVTX)
  def upload_view(request):
      ...

  @login_required
  @superadmin_required
  def admin_settings_view(request):
      ...
"""

import logging
from functools import wraps
from typing import Any, Callable, Optional

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse

from .permissions import DashboardPermissions, is_object_owner

logger = logging.getLogger(__name__)


# ===========================================================================
# Permission Required with Audit Logging
# ===========================================================================


def permission_required_with_audit(
    permission: str,
    login_url: Optional[str] = None,
) -> Callable:
    """
    Decorator that checks a permission and logs denials.

    Unlike Django's built-in `@permission_required`, this decorator:
      1. Always raises PermissionDenied for authenticated users
         (triggers custom 403 handler).
      2. Logs denial events at WARNING level.
      3. Creates AuditLog entries for compliance.

    Args:
        permission: Full permission string (e.g., "dashboard.upload_evtx").
        login_url:  Optional URL to redirect unauthenticated users.
                    Defaults to settings.LOGIN_URL.

    Returns:
        Decorated view function.

    Usage:
        @login_required
        @permission_required_with_audit(DashboardPermissions.UPLOAD_EVTX)
        def upload_view(request):
            ...
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped_view(
            request: HttpRequest, *args: Any, **kwargs: Any
        ) -> HttpResponse:
            # Unauthenticated users are handled by @login_required
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(
                    request.get_full_path(),
                    login_url=login_url,
                )

            # Check permission
            if request.user.has_perm(permission):
                return view_func(request, *args, **kwargs)

            # Permission denied — log and raise
            logger.warning(
                "RBAC DENIED: user='%s' lacks '%s' for '%s'.",
                request.user.username,
                permission,
                request.path,
            )

            # Audit log the denial
            try:
                from .models import AuditLog
                from .auth_views import _get_client_ip

                AuditLog.objects.create(
                    user=request.user,
                    action=AuditLog.Action.VIEW,
                    ip_address=_get_client_ip(request),
                )
            except Exception:
                logger.exception("Failed to log RBAC denial in AuditLog.")

            raise PermissionDenied(
                "You do not have permission to perform this action."
            )

        return _wrapped_view

    return decorator


# ===========================================================================
# Super Admin Required Decorator
# ===========================================================================


def superadmin_required(view_func: Callable) -> Callable:
    """
    Decorator that restricts access to Super Admin users.

    Checks for `dashboard.dashboard_full_access` permission.

    WHY NOT CHECK user.is_admin:
      - `has_perm()` is the canonical Django way to check permissions.
      - Respects permission caching and future group changes.
      - Consistent with the mixin-based approach.

    Usage:
        @login_required
        @superadmin_required
        def admin_dashboard(request):
            ...
    """

    @wraps(view_func)
    def _wrapped_view(
        request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())

        if request.user.has_perm(DashboardPermissions.DASHBOARD_FULL_ACCESS):
            return view_func(request, *args, **kwargs)

        logger.warning(
            "RBAC DENIED: non-admin user '%s' attempted admin view '%s'.",
            request.user.username,
            request.path,
        )

        raise PermissionDenied(
            "You do not have permission to access this page."
        )

    return _wrapped_view


# ===========================================================================
# Owner Required Decorator
# ===========================================================================


def owner_required(
    model_class: type,
    pk_url_kwarg: str = "pk",
    owner_field: str = "user",
) -> Callable:
    """
    Decorator that verifies object ownership for detail views.

    Looks up the object by PK from URL kwargs, then checks if the
    requesting user owns it. Super Admins bypass the check.

    Args:
        model_class:  The Django model class to look up.
        pk_url_kwarg: URL kwarg name for the object PK (default: "pk").
        owner_field:  Field name on the model referencing the owner
                      (default: "user").

    Returns:
        Decorated view function.

    Usage:
        @login_required
        @owner_required(AnalysisJob, pk_url_kwarg="job_id")
        def job_detail(request, job_id):
            job = AnalysisJob.objects.get(pk=job_id)
            ...
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped_view(
            request: HttpRequest, *args: Any, **kwargs: Any
        ) -> HttpResponse:
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())

            # Look up the object
            pk = kwargs.get(pk_url_kwarg)
            try:
                obj = model_class.objects.get(pk=pk)
            except model_class.DoesNotExist:
                from django.http import Http404

                raise Http404(
                    f"{model_class.__name__} with pk={pk} not found."
                )

            # Check ownership
            if is_object_owner(request.user, obj, owner_field):
                return view_func(request, *args, **kwargs)

            logger.warning(
                "OWNERSHIP DENIED: user='%s' tried to access %s #%s.",
                request.user.username,
                model_class.__name__,
                pk,
            )

            raise PermissionDenied(
                "You do not have permission to access this resource."
            )

        return _wrapped_view

    return decorator
