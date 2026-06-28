"""
dashboard/admin.py — Phase 8
==============================
Django admin registrations for all dashboard models.

WHY THIS EXISTS:
  - Provides a web-based interface for inspecting and managing
    database records during development and operations.
  - Admin is critical for SOC Super Administrators who need to
    manage users, review jobs, and inspect anomalies.

ADMIN CLASSES:
  UserAdmin       — Custom user admin with role field integration.
  AnalysisJobAdmin — Job lifecycle tracking with status filters.
  AnomalyAdmin    — Anomaly browsing with severity-based filtering.
  AuditLogAdmin   — Read-only audit trail (append-only enforcement).
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AnalysisJob, Anomaly, AuditLog, User


# ===========================================================================
# User Admin
# ===========================================================================


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin for the User model.

    Extends Django's built-in UserAdmin to include the 'role' field
    in the list display, filters, and edit forms.
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
