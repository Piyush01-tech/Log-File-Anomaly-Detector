"""
dashboard/permissions.py — Phase 9B
=======================================
Central permission constants and reusable authorization utilities.

PURPOSE:
  - Single source of truth for all custom permission codenames.
  - Eliminates magic strings scattered across views, templates,
    and decorators.
  - Provides reusable helper functions for permission checks
    and queryset filtering (user isolation).

DESIGN DECISIONS:
  - Permission codenames follow the pattern: `dashboard.<codename>`.
  - The `DashboardPermissions` class acts as an enum-like namespace
    for type-safe references throughout the codebase.
  - `get_user_objects()` centralizes the user isolation logic:
    Analysts see only their own data; Admins see everything.
  - All permission codenames are defined on the User model's
    content type via `Meta.permissions` (populated by `setup_rbac`
    management command).

ARCHITECTURE:
  - This module is imported by views, mixins, decorators, and
    management commands.
  - It does NOT import from views or other modules to avoid
    circular dependencies.

FUTURE EXTENSIBILITY:
  - New permissions: Add a constant here and assign it to the
    appropriate group in `setup_rbac`.
  - New roles: Create a new group in Django admin and assign
    existing permissions — no code changes needed.
"""

import logging
from typing import Optional

from django.db.models import QuerySet

logger = logging.getLogger(__name__)


# ===========================================================================
# Permission Constants
# ===========================================================================


class DashboardPermissions:
    """
    Central registry of all custom permission codenames.

    Each constant is the full Django permission string in the format
    `app_label.codename` (e.g., `dashboard.upload_evtx`).

    WHY AN ENUM-LIKE CLASS:
      - Provides IDE autocompletion and import-time error checking.
      - Avoids magic strings like `"dashboard.upload_evtx"` scattered
        across the codebase.
      - New permissions are added in ONE place, then referenced
        everywhere via `DashboardPermissions.UPLOAD_EVTX`.

    NAMING CONVENTION:
      - Constants use UPPER_SNAKE_CASE.
      - Codenames use lower_snake_case matching Django conventions.
      - All permissions belong to the `dashboard` app label.
    """

    # --- Super Admin Exclusive ---
    DASHBOARD_FULL_ACCESS = "dashboard.dashboard_full_access"
    VIEW_ALL_LOGS = "dashboard.view_all_logs"
    VIEW_ALL_INCIDENTS = "dashboard.view_all_incidents"
    MANAGE_USERS = "dashboard.manage_users"
    DISABLE_USERS = "dashboard.disable_users"
    DELETE_USERS = "dashboard.delete_users"
    PROMOTE_USERS = "dashboard.promote_users"
    VIEW_SYSTEM_STATS = "dashboard.view_system_stats"
    MANAGE_RAG = "dashboard.manage_rag"
    MANAGE_SETTINGS = "dashboard.manage_settings"

    # --- Shared (Analyst + Super Admin) ---
    UPLOAD_EVTX = "dashboard.upload_evtx"
    VIEW_OWN_UPLOADS = "dashboard.view_own_uploads"
    VIEW_OWN_INCIDENTS = "dashboard.view_own_incidents"
    EDIT_OWN_PROFILE = "dashboard.edit_own_profile"

    # --- Group Names ---
    GROUP_SUPER_ADMIN = "Super Admin"
    GROUP_ANALYST = "Analyst"

    @classmethod
    def get_super_admin_permissions(cls) -> list[str]:
        """
        Return the list of permission codenames for the Super Admin group.

        Super Admins get ALL permissions (both admin-exclusive and shared).

        Returns:
            List of codename strings (without app_label prefix).
        """
        return [
            "dashboard_full_access",
            "view_all_logs",
            "view_all_incidents",
            "manage_users",
            "disable_users",
            "delete_users",
            "promote_users",
            "view_system_stats",
            "manage_rag",
            "manage_settings",
            "upload_evtx",
            "view_own_uploads",
            "view_own_incidents",
            "edit_own_profile",
        ]

    @classmethod
    def get_analyst_permissions(cls) -> list[str]:
        """
        Return the list of permission codenames for the Analyst group.

        Analysts get only the shared permissions — no admin-exclusive
        permissions. This enforces least privilege.

        Returns:
            List of codename strings (without app_label prefix).
        """
        return [
            "upload_evtx",
            "view_own_uploads",
            "view_own_incidents",
            "edit_own_profile",
        ]

    @classmethod
    def get_all_custom_permissions(cls) -> list[tuple[str, str]]:
        """
        Return all custom permission definitions for Meta.permissions.

        Each tuple is (codename, human_readable_name) as expected by
        Django's `Meta.permissions` attribute.

        Returns:
            List of (codename, description) tuples.
        """
        return [
            ("dashboard_full_access", "Can access full admin dashboard"),
            ("view_all_logs", "Can view all uploaded logs across users"),
            ("view_all_incidents", "Can view all incidents across users"),
            ("manage_users", "Can create and edit user accounts"),
            ("disable_users", "Can deactivate user accounts"),
            ("delete_users", "Can permanently delete user accounts"),
            ("promote_users", "Can change user roles and group membership"),
            ("view_system_stats", "Can view system-wide statistics"),
            ("manage_rag", "Can manage RAG configuration"),
            ("manage_settings", "Can manage system settings"),
            ("upload_evtx", "Can upload .evtx files for analysis"),
            ("view_own_uploads", "Can view own uploaded logs"),
            ("view_own_incidents", "Can view own analysis results"),
            ("edit_own_profile", "Can edit own user profile"),
        ]


# ===========================================================================
# Authorization Helpers
# ===========================================================================


def user_has_permission(user, permission: str) -> bool:
    """
    Check if a user has a specific permission.

    Wraps Django's `user.has_perm()` with debug logging for
    auditing and troubleshooting.

    Args:
        user:       The User instance to check.
        permission: Full permission string (e.g., "dashboard.upload_evtx").

    Returns:
        True if the user has the permission, False otherwise.
    """
    if not user or not user.is_authenticated:
        logger.debug(
            "Permission check failed: unauthenticated user for '%s'.",
            permission,
        )
        return False

    has_perm = user.has_perm(permission)

    logger.debug(
        "Permission check: user='%s', permission='%s', result=%s.",
        user.username,
        permission,
        has_perm,
    )

    return has_perm


def get_user_objects(
    user,
    queryset: QuerySet,
    owner_field: str = "user",
) -> QuerySet:
    """
    Filter a queryset based on user permissions (user isolation).

    This is the CENTRAL function for enforcing data isolation:
      - Super Admins (with `view_all_logs` or `view_all_incidents`)
        see all records.
      - Analysts see only records where `owner_field == user`.

    WHY THIS EXISTS:
      - Prevents analysts from accessing other users' data by
        manipulating URL parameters or API requests.
      - Centralizes the filtering logic so it can't be forgotten
        in individual views.

    Args:
        user:        The authenticated User instance.
        queryset:    The base queryset to filter.
        owner_field: The model field name that references the owner
                     (default: "user").

    Returns:
        Filtered queryset — all records for admins, own records
        for analysts.
    """
    if not user or not user.is_authenticated:
        return queryset.none()

    # Super Admins with view_all permissions bypass the filter
    if user.has_perm(DashboardPermissions.VIEW_ALL_LOGS):
        logger.debug(
            "Admin '%s' accessing all records (view_all_logs granted).",
            user.username,
        )
        return queryset

    # Analysts see only their own data
    filter_kwargs = {owner_field: user}
    logger.debug(
        "Filtering queryset for user '%s' on field '%s'.",
        user.username,
        owner_field,
    )
    return queryset.filter(**filter_kwargs)


def is_object_owner(
    user,
    obj,
    owner_field: str = "user",
) -> bool:
    """
    Check if a user owns a specific object.

    Used for object-level permission checks in detail/update views.

    Args:
        user:        The authenticated User instance.
        obj:         The model instance to check ownership of.
        owner_field: The field name on the object that references
                     the owner (default: "user").

    Returns:
        True if the user owns the object or has admin bypass.
    """
    if not user or not user.is_authenticated:
        return False

    # Super Admins bypass ownership checks
    if user.has_perm(DashboardPermissions.VIEW_ALL_LOGS):
        return True

    owner = getattr(obj, owner_field, None)
    if owner is None:
        logger.warning(
            "Object %s has no '%s' field for ownership check.",
            obj,
            owner_field,
        )
        return False

    return owner == user
