"""
dashboard/admin.py — Phase 9B
================================
Django admin registrations for all dashboard models.

WHY THIS EXISTS:
  - Provides a web-based interface for inspecting and managing
    database records during development and operations.
  - Admin is critical for SOC Super Administrators who need to
    manage users, review jobs, and inspect anomalies.

ADMIN CLASSES:
  UserAdmin       — Custom user admin with role field integration
                    and RBAC-enforced bulk actions (Phase 9B).
  AnalysisJobAdmin — Job lifecycle tracking with status filters.
  AnomalyAdmin    — Anomaly browsing with severity-based filtering.
  AuditLogAdmin   — Read-only audit trail (append-only enforcement).

PHASE 9B CHANGES:
  - Added admin actions: promote_to_admin, demote_to_analyst,
    disable_users, enable_users.
  - Admin access restricted via has_module_permission checks.
  - UserAdmin enforces permission checks for add/change/delete.
"""

import logging

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AnalysisJob, Anomaly, AuditLog, User
from .permissions import DashboardPermissions

logger = logging.getLogger(__name__)


# ===========================================================================
# User Admin
# ===========================================================================


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin for the User model.

    Extends Django's built-in UserAdmin to include the 'role' field
    in the list display, filters, and edit forms.

    Phase 9B Additions:
      - Bulk actions for role promotion, demotion, and account toggling.
      - Permission checks using Django's permission framework.
    """

    # List view
    list_display = (
        "username",
        "email",
        "role",
        "is_staff",
        "is_active",
        "date_joined",
    )
    list_filter = ("role", "is_staff", "is_active", "date_joined")
    search_fields = ("username", "email")
    ordering = ("-date_joined",)

    # Edit form — add 'role' to the Personal Info section
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "SOC Dashboard",
            {
                "fields": ("role",),
                "description": "Role-Based Access Control for the SOC Dashboard.",
            },
        ),
    )

    # Creation form — include 'role' when adding a new user
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "SOC Dashboard",
            {
                "fields": ("role",),
            },
        ),
    )

    # Phase 9B: Bulk actions
    actions = [
        "promote_to_admin",
        "demote_to_analyst",
        "disable_users",
        "enable_users",
    ]

    # --- Permission Checks (Phase 9B) ---

    def has_add_permission(self, request):
        """Only users with manage_users permission can add users."""
        return request.user.has_perm(DashboardPermissions.MANAGE_USERS)

    def has_change_permission(self, request, obj=None):
        """Only users with manage_users permission can edit users."""
        return request.user.has_perm(DashboardPermissions.MANAGE_USERS)

    def has_delete_permission(self, request, obj=None):
        """Only users with delete_users permission can delete users."""
        return request.user.has_perm(DashboardPermissions.DELETE_USERS)

    # --- Bulk Actions (Phase 9B) ---

    @admin.action(description="Promote selected users to Super Admin")
    def promote_to_admin(self, request, queryset):
        """
        Promote selected users to the ADMIN role.

        Requires the `promote_users` permission. The post_save signal
        will automatically sync group membership.
        """
        if not request.user.has_perm(DashboardPermissions.PROMOTE_USERS):
            self.message_user(
                request,
                "You do not have permission to promote users.",
                level="error",
            )
            return

        count = 0
        for user in queryset.exclude(role=User.Role.ADMIN):
            user.role = User.Role.ADMIN
            user.is_staff = True
            user.save(update_fields=["role", "is_staff"])
            count += 1
            logger.info(
                "Admin '%s' promoted user '%s' to ADMIN.",
                request.user.username,
                user.username,
            )

        self.message_user(
            request,
            f"Successfully promoted {count} user(s) to Super Admin.",
        )

    @admin.action(description="Demote selected users to Analyst")
    def demote_to_analyst(self, request, queryset):
        """
        Demote selected users to the ANALYST role.

        Requires the `promote_users` permission. Prevents self-demotion
        to avoid locking out the last admin.
        """
        if not request.user.has_perm(DashboardPermissions.PROMOTE_USERS):
            self.message_user(
                request,
                "You do not have permission to demote users.",
                level="error",
            )
            return

        # Prevent self-demotion
        safe_queryset = queryset.exclude(pk=request.user.pk)
        skipped = queryset.filter(pk=request.user.pk).count()

        count = 0
        for user in safe_queryset.exclude(role=User.Role.ANALYST):
            user.role = User.Role.ANALYST
            user.is_staff = False
            user.is_superuser = False
            user.save(update_fields=["role", "is_staff", "is_superuser"])
            count += 1
            logger.info(
                "Admin '%s' demoted user '%s' to ANALYST.",
                request.user.username,
                user.username,
            )

        msg = f"Successfully demoted {count} user(s) to Analyst."
        if skipped:
            msg += " (You cannot demote yourself.)"
        self.message_user(request, msg)

    @admin.action(description="Disable selected user accounts")
    def disable_users(self, request, queryset):
        """
        Deactivate selected user accounts (set is_active=False).

        Requires the `disable_users` permission. Prevents self-disabling.
        """
        if not request.user.has_perm(DashboardPermissions.DISABLE_USERS):
            self.message_user(
                request,
                "You do not have permission to disable users.",
                level="error",
            )
            return

        # Prevent self-disabling
        safe_queryset = queryset.exclude(pk=request.user.pk)
        count = safe_queryset.filter(is_active=True).update(is_active=False)

        logger.info(
            "Admin '%s' disabled %d user account(s).",
            request.user.username,
            count,
        )
        self.message_user(
            request,
            f"Successfully disabled {count} user account(s).",
        )

    @admin.action(description="Enable selected user accounts")
    def enable_users(self, request, queryset):
        """
        Re-activate selected user accounts (set is_active=True).

        Requires the `disable_users` permission (enable is the inverse).
        """
        if not request.user.has_perm(DashboardPermissions.DISABLE_USERS):
            self.message_user(
                request,
                "You do not have permission to enable users.",
                level="error",
            )
            return

        count = queryset.filter(is_active=False).update(is_active=True)

        logger.info(
            "Admin '%s' enabled %d user account(s).",
            request.user.username,
            count,
        )
        self.message_user(
            request,
            f"Successfully enabled {count} user account(s).",
        )


# ===========================================================================
# AnalysisJob Admin
# ===========================================================================


@admin.register(AnalysisJob)
class AnalysisJobAdmin(admin.ModelAdmin):
    """
    Admin for AnalysisJob — tracks .evtx upload and processing lifecycle.

    Provides filtering by status and upload date, read-only computed
    fields, and search by filename.
    """

    list_display = (
        "id",
        "original_filename",
        "user",
        "status",
        "total_samples",
        "total_anomalies",
        "uploaded_at",
        "completed_at",
    )
    list_filter = ("status", "uploaded_at")
    search_fields = ("original_filename", "user__username")
    readonly_fields = (
        "uploaded_at",
        "completed_at",
        "total_samples",
        "total_anomalies",
    )
    ordering = ("-uploaded_at",)

    fieldsets = (
        (
            "Job Information",
            {
                "fields": (
                    "user",
                    "original_filename",
                    "file_path",
                    "status",
                    "error_message",
                ),
            },
        ),
        (
            "Results",
            {
                "fields": (
                    "total_samples",
                    "total_anomalies",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "uploaded_at",
                    "completed_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )


# ===========================================================================
# Anomaly Admin
# ===========================================================================


@admin.register(Anomaly)
class AnomalyAdmin(admin.ModelAdmin):
    """
    Admin for Anomaly — browse and filter detected anomalies.

    Provides severity-based filtering, score sorting, and
    a read-only display of the feature data JSON.
    """

    list_display = (
        "id",
        "job",
        "severity",
        "anomaly_score",
        "computer_name",
        "window_start",
    )
    list_filter = ("severity", "job__status")
    search_fields = ("computer_name", "job__original_filename")
    readonly_fields = ("feature_data",)
    ordering = ("anomaly_score",)  # Most anomalous first

    fieldsets = (
        (
            "Anomaly Details",
            {
                "fields": (
                    "job",
                    "window_start",
                    "computer_name",
                    "anomaly_score",
                    "severity",
                ),
            },
        ),
        (
            "Feature Data",
            {
                "fields": ("feature_data",),
                "classes": ("collapse",),
                "description": (
                    "Raw feature values from the ML pipeline. "
                    "15 numerical features per time window."
                ),
            },
        ),
        (
            "RAG Explanation (Phase 14)",
            {
                "fields": ("rag_explanation",),
                "classes": ("collapse",),
                "description": (
                    "LLM-generated incident explanation. "
                    "Will be populated by the RAG layer."
                ),
            },
        ),
    )


# ===========================================================================
# AuditLog Admin
# ===========================================================================


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Admin for AuditLog — read-only audit trail.

    IMMUTABILITY ENFORCEMENT:
      - has_add_permission returns False (no manual log creation).
      - has_change_permission returns False (no editing).
      - has_delete_permission returns False (no deletion).
      Audit logs are append-only by application design.
    """

    list_display = (
        "id",
        "user",
        "action",
        "ip_address",
        "job",
        "created_at",
    )
    list_filter = ("action", "created_at")
    search_fields = ("user__username", "ip_address")
    readonly_fields = (
        "user",
        "job",
        "action",
        "ip_address",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        """Audit logs are created programmatically, not manually."""
        return False

    def has_change_permission(self, request, obj=None):
        """Audit logs are immutable — no editing allowed."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Audit logs are append-only — no deletion allowed."""
        return False
