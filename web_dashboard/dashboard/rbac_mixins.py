"""
dashboard/rbac_mixins.py — Phase 9B
=======================================
Reusable class-based view (CBV) mixins for authorization enforcement.

PURPOSE:
  - Provides drop-in authorization mixins for Django CBVs.
  - Enforces permission checks and object ownership at the view level.
  - Centralizes authorization patterns to prevent ad-hoc permission
    checks scattered across views.

MIXINS:
  RBACPermissionRequiredMixin — Wraps Django's PermissionRequiredMixin
                                with custom 403 handling and audit logging.
  SuperAdminRequiredMixin     — Shortcut for admin-only views.
  OwnershipMixin              — Object-level ownership verification.
  AnalystOwnerQuerysetMixin   — Queryset filtering for list views.

DESIGN DECISIONS:
  - All mixins inherit from Django's built-in auth mixins where
    possible to leverage battle-tested logic.
  - Custom 403 handling renders our themed 403 template instead of
    Django's plain text response.
  - Audit logging on permission denials supports compliance monitoring.
  - Mixins are composable: combine OwnershipMixin with
    RBACPermissionRequiredMixin for dual checks.

USAGE (Phase 10+):
  class UploadView(RBACPermissionRequiredMixin, CreateView):
      permission_required = DashboardPermissions.UPLOAD_EVTX
      ...

  class JobDetailView(OwnershipMixin, DetailView):
      model = AnalysisJob
      owner_field = "user"
      admin_bypass_permission = DashboardPermissions.VIEW_ALL_LOGS
      ...

  class JobListView(AnalystOwnerQuerysetMixin, ListView):
      model = AnalysisJob
      ...
"""

import logging
from typing import Any, Optional

from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
)
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse

from .permissions import DashboardPermissions, get_user_objects, is_object_owner

logger = logging.getLogger(__name__)


# ===========================================================================
# Permission Required Mixin
# ===========================================================================


class RBACPermissionRequiredMixin(PermissionRequiredMixin):
    """
    Extended PermissionRequiredMixin with audit logging and custom 403.

    Extends Django's PermissionRequiredMixin to:
      1. Log permission denials for compliance auditing.
      2. Raise PermissionDenied (triggers custom 403 handler) instead
         of redirecting to login for authenticated users.

    Attributes:
        permission_required: String or iterable of permission strings
                             (e.g., "dashboard.upload_evtx").
        raise_exception:     Always True — authenticated users get 403,
                             not redirected to login.

    Usage:
        class MyView(RBACPermissionRequiredMixin, TemplateView):
            permission_required = DashboardPermissions.UPLOAD_EVTX
    """

    raise_exception = True

    def handle_no_permission(self) -> HttpResponse:
        """
        Handle permission denial with logging.

        Logs the denial event with the user, requested permission,
        and request path for security auditing.

        Returns:
            Calls parent's handler which raises PermissionDenied.
        """
        if self.request.user.is_authenticated:
            logger.warning(
                "RBAC DENIED: user='%s' attempted '%s' at '%s'.",
                self.request.user.username,
                self.get_permission_required(),
                self.request.path,
            )

            # Create audit log entry for denied access attempts
            try:
                from .models import AuditLog

                from .auth_views import _get_client_ip

                AuditLog.objects.create(
                    user=self.request.user,
                    action=AuditLog.Action.VIEW,
                    ip_address=_get_client_ip(self.request),
                )
            except Exception:
                logger.exception("Failed to log RBAC denial in AuditLog.")

        return super().handle_no_permission()


# ===========================================================================
# Super Admin Required Mixin
# ===========================================================================


class SuperAdminRequiredMixin(LoginRequiredMixin):
    """
    Mixin that restricts access to Super Admin users only.

    Checks for `dashboard.dashboard_full_access` permission, which
    is exclusively assigned to the Super Admin group.

    WHY NOT JUST CHECK user.is_admin:
      - `has_perm()` respects Django's permission caching.
      - Works with future role additions without code changes.
      - Supports permission overrides via Django admin.

    Usage:
        class AdminSettingsView(SuperAdminRequiredMixin, TemplateView):
            template_name = "dashboard/admin/settings.html"
    """

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        """
        Check Super Admin permission before dispatching.

        Args:
            request: The HTTP request.

        Returns:
            Normal dispatch if authorized, raises PermissionDenied otherwise.
        """
        response = super().dispatch(request, *args, **kwargs)

        # super().dispatch handles LoginRequired redirect
        if not request.user.is_authenticated:
            return response

        if not request.user.has_perm(
            DashboardPermissions.DASHBOARD_FULL_ACCESS
        ):
            logger.warning(
                "RBAC DENIED: non-admin user '%s' attempted admin view '%s'.",
                request.user.username,
                request.path,
            )
            raise PermissionDenied(
                "You do not have permission to access this page."
            )

        return response


# ===========================================================================
# Ownership Mixin
# ===========================================================================


class OwnershipMixin:
    """
    Mixin for detail/update/delete views that verifies object ownership.

    Ensures the requesting user owns the object (via `owner_field`)
    before allowing access. Super Admins with `admin_bypass_permission`
    bypass the ownership check.

    Attributes:
        owner_field:             Field name on the model that references
                                 the owner (default: "user").
        admin_bypass_permission: Permission that allows admin bypass
                                 (default: VIEW_ALL_LOGS).

    Usage:
        class JobDetailView(LoginRequiredMixin, OwnershipMixin, DetailView):
            model = AnalysisJob
            owner_field = "user"
    """

    owner_field: str = "user"
    admin_bypass_permission: str = DashboardPermissions.VIEW_ALL_LOGS

    def get_object(self, queryset: Optional[QuerySet] = None) -> Any:
        """
        Get the object and verify ownership.

        Calls the parent's get_object(), then checks if the current
        user owns it (or has admin bypass permission).

        Args:
            queryset: Optional queryset to use for lookup.

        Returns:
            The model instance if authorized.

        Raises:
            PermissionDenied: If the user doesn't own the object
                              and lacks admin bypass.
        """
        obj = super().get_object(queryset)

        if not is_object_owner(
            self.request.user, obj, self.owner_field
        ):
            logger.warning(
                "OWNERSHIP DENIED: user='%s' tried to access %s #%s "
                "owned by '%s'.",
                self.request.user.username,
                obj.__class__.__name__,
                obj.pk,
                getattr(obj, self.owner_field, "unknown"),
            )
            raise PermissionDenied(
                "You do not have permission to access this resource."
            )

        return obj


# ===========================================================================
# Analyst Owner Queryset Mixin
# ===========================================================================


class AnalystOwnerQuerysetMixin:
    """
    Mixin for list views that filters querysets by ownership.

    Applies user isolation:
      - Analysts see only their own records.
      - Super Admins see all records.

    Uses `get_user_objects()` from permissions.py for consistent
    filtering logic across all list views.

    Attributes:
        owner_field: Field name on the model that references the owner
                     (default: "user").

    Usage:
        class JobListView(LoginRequiredMixin, AnalystOwnerQuerysetMixin,
                          ListView):
            model = AnalysisJob
            owner_field = "user"
    """

    owner_field: str = "user"

    def get_queryset(self) -> QuerySet:
        """
        Return a filtered queryset based on user permissions.

        Analysts get their own records only; Admins get everything.

        Returns:
            Filtered queryset.
        """
        base_queryset = super().get_queryset()
        return get_user_objects(
            self.request.user,
            base_queryset,
            self.owner_field,
        )
