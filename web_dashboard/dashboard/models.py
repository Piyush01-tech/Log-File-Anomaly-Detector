"""
dashboard/models.py — Phase 8
===============================
Django ORM models for the SOC Anomaly Detection Dashboard.

MODELS:
  User         — Custom user model with RBAC role field.
  AnalysisJob  — Tracks .evtx file upload and processing lifecycle.
  Anomaly      — Individual anomalous time windows detected by the ML pipeline.
  AuditLog     — Append-only compliance log for user actions.

ARCHITECTURE:
  These models represent the persistence layer of the Django web dashboard.
  Django NEVER imports from ml_engine directly. All ML results arrive
  via HTTP from the Flask API and are persisted here.

DATABASE AGNOSTICISM:
  All fields use standard Django ORM types. Switching from SQLite to
  PostgreSQL requires only a settings.py change — zero model code changes.

SCHEMA REFERENCE:
  See DATABASE_DESIGN.md for the full ER diagram and constraint rationale.
"""

import logging
import uuid
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from .managers import UserManager

logger = logging.getLogger(__name__)


# ===========================================================================
# User Model
# ===========================================================================


class User(AbstractUser):
    """
    Custom user model extending Django's AbstractUser with RBAC roles.

    WHY EXTEND AbstractUser:
      - Preserves all Django auth features: password hashing (PBKDF2),
        session management, admin integration, last_login tracking.
      - Adds a 'role' field for Role-Based Access Control.
      - Must be set as AUTH_USER_MODEL BEFORE first migration.

    ROLES:
      - ADMIN:   Full system access including Django admin, user management,
                 and data purging.
      - ANALYST: Standard SOC analyst. Can upload files, view dashboard,
                 alerts, and incident history. Cannot delete records or
                 access system settings.

    Attributes:
        role:  TextChoices field defining the user's access level.
        email: Made required (blank=False) for enterprise use.
    """

    class Role(models.TextChoices):
        """Enumeration of available user roles."""
        ADMIN = "ADMIN", "Administrator"
        ANALYST = "ANALYST", "Analyst"

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.ANALYST,
        db_index=True,
        help_text="Determines the user's access level in the SOC dashboard.",
    )

    email = models.EmailField(
        "email address",
        blank=False,
        help_text="Required. Used for notifications and account recovery.",
    )

    # Wire up the custom manager
    objects = UserManager()

    class Meta:
        db_table = "dashboard_user"
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_admin(self) -> bool:
        """Check if the user has the Admin role."""
        return self.role == self.Role.ADMIN

    @property
    def is_analyst(self) -> bool:
        """Check if the user has the Analyst role."""
        return self.role == self.Role.ANALYST


# ===========================================================================
# AnalysisJob Model
# ===========================================================================


def _upload_to_evtx(instance: "AnalysisJob", filename: str) -> str:
    """
    Generate a unique upload path for .evtx files.

    Prevents filename collisions by prepending a UUID4 prefix.
    Files are stored under MEDIA_ROOT/evtx_uploads/.

    Args:
        instance: The AnalysisJob instance (unused but required by Django).
        filename: The original filename from the upload.

    Returns:
        Relative path string for Django's FileField storage.
    """
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "evtx"
    unique_name = f"{uuid.uuid4().hex[:12]}_{filename}"
    return f"evtx_uploads/{unique_name}"


class AnalysisJob(models.Model):
    """
    Represents a single .evtx file upload and its processing lifecycle.

    LIFECYCLE:
      PENDING  → User uploaded file, awaiting ML analysis.
      RUNNING  → Flask API is currently processing the file.
      COMPLETED → Analysis finished successfully; anomalies stored.
      FAILED   → Analysis encountered an error; error_message populated.

    RELATIONSHIPS:
      - ForeignKey to User (the analyst who uploaded the file).
      - One-to-Many to Anomaly (detected anomalous windows).
      - Referenced by AuditLog entries.

    FILE STORAGE:
      The .evtx file is stored in Django's MEDIA_ROOT under
      evtx_uploads/. The file_path field stores the relative path
      managed by Django's FileField.
    """

    class Status(models.TextChoices):
        """Enumeration of job processing states."""
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    # --- Relationships ---
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analysis_jobs",
        help_text="The analyst who initiated this analysis.",
    )

    # --- File Information ---
    original_filename = models.CharField(
        max_length=255,
        help_text="Original filename as uploaded by the user.",
    )

    file_path = models.FileField(
        upload_to=_upload_to_evtx,
        validators=[FileExtensionValidator(allowed_extensions=["evtx"])],
        help_text="Path to the uploaded .evtx file in MEDIA_ROOT.",
    )

    # --- Status Tracking ---
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        help_text="Current processing state of the analysis job.",
    )

    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Error details if the job failed. Empty on success.",
    )

    # --- Timestamps ---
    uploaded_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the file was uploaded.",
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the analysis finished (success or failure).",
    )

    # --- Result Summary ---
    total_samples = models.PositiveIntegerField(
        default=0,
        help_text="Total number of time windows analyzed.",
    )

    total_anomalies = models.PositiveIntegerField(
        default=0,
        help_text="Number of time windows flagged as anomalous.",
    )

    class Meta:
        db_table = "dashboard_analysisjob"
        verbose_name = "Analysis Job"
        verbose_name_plural = "Analysis Jobs"
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(
                fields=["status", "uploaded_at"],
                name="idx_job_status_uploaded",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Job #{self.pk} — {self.original_filename} "
            f"({self.get_status_display()})"
        )

    @property
    def is_complete(self) -> bool:
        """Whether this job has finished processing (success or failure)."""
        return self.status in (self.Status.COMPLETED, self.Status.FAILED)

    @property
    def anomaly_rate(self) -> Optional[float]:
        """
        Calculate the anomaly rate for this job.

        Returns:
            Float between 0.0 and 1.0, or None if no samples processed.
        """
        if self.total_samples == 0:
            return None
        return round(self.total_anomalies / self.total_samples, 4)

    def mark_running(self) -> None:
        """
        Transition the job status to RUNNING.

        Called when the Flask API begins processing.
        """
        self.status = self.Status.RUNNING
        self.save(update_fields=["status"])
        logger.info("Job #%s marked as RUNNING.", self.pk)

    def mark_completed(
        self, total_samples: int, total_anomalies: int
    ) -> None:
        """
        Transition the job status to COMPLETED with result summary.

        Args:
            total_samples:   Total time windows analyzed.
            total_anomalies: Number of anomalous windows detected.
        """
        self.status = self.Status.COMPLETED
        self.total_samples = total_samples
        self.total_anomalies = total_anomalies
        self.completed_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "total_samples",
                "total_anomalies",
                "completed_at",
            ]
        )
        logger.info(
            "Job #%s marked as COMPLETED (%d samples, %d anomalies).",
            self.pk,
            total_samples,
            total_anomalies,
        )

    def mark_failed(self, error_message: str) -> None:
        """
        Transition the job status to FAILED with error details.

        Args:
            error_message: Human-readable error description.
        """
        self.status = self.Status.FAILED
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save(
            update_fields=["status", "error_message", "completed_at"]
        )
        logger.warning("Job #%s marked as FAILED: %s", self.pk, error_message)


# ===========================================================================
# Anomaly Model
# ===========================================================================


class Anomaly(models.Model):
    """
    Stores an individual anomalous time window detected during an AnalysisJob.

    Each row represents one 1-hour window (or configurable window size)
    that the Isolation Forest model flagged as anomalous.

    RELATIONSHIPS:
      - ForeignKey to AnalysisJob (CASCADE: deleting a job purges its anomalies).

    FEATURE DATA:
      The 15 numerical features computed by the ML pipeline are stored in
      a JSONField rather than 15 separate columns. This design:
        - Prevents schema bloat.
        - Accommodates future feature additions without migrations.
        - Allows flexible querying via Django's JSON lookups.

    RAG EXPLANATION:
      The rag_explanation field is reserved for Phase 14 (RAG Integration).
      It will contain an LLM-generated plain-English incident summary
      for HIGH/CRITICAL anomalies.

    SEVERITY LEVELS:
      CRITICAL — Score ≤ -0.3, requires immediate investigation.
      HIGH     — Score between -0.3 and -0.1, priority review.
      MEDIUM   — Score between -0.1 and 0.0, scheduled review.
      LOW      — Score > 0.0, monitoring only.
    """

    class Severity(models.TextChoices):
        """Enumeration of anomaly severity levels."""
        CRITICAL = "CRITICAL", "Critical"
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"

    # --- Relationships ---
    job = models.ForeignKey(
        AnalysisJob,
        on_delete=models.CASCADE,
        related_name="anomalies",
        help_text="The analysis job that detected this anomaly.",
    )

    # --- Anomaly Identification ---
    window_start = models.DateTimeField(
        help_text="Start timestamp of the anomalous time window.",
    )

    computer_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Hostname of the machine where the anomaly was detected.",
    )

    # --- Scoring ---
    anomaly_score = models.FloatField(
        db_index=True,
        help_text=(
            "Raw decision_function score from Isolation Forest. "
            "More negative = more anomalous."
        ),
    )

    severity = models.CharField(
        max_length=10,
        choices=Severity.choices,
        db_index=True,
        help_text="SOC-friendly severity classification based on anomaly_score.",
    )

    # --- Feature Snapshot ---
    feature_data = models.JSONField(
        default=dict,
        help_text=(
            "Dictionary of the 15 feature values for this time window. "
            "Keys match Config.FEATURE_COLUMNS (e.g., 'failed_logins', "
            "'process_creation_events')."
        ),
    )

    # --- RAG Explanation (Phase 14) ---
    rag_explanation = models.TextField(
        blank=True,
        default="",
        help_text=(
            "LLM-generated incident explanation. Populated by the "
            "RAG layer in Phase 14. Empty until then."
        ),
    )

    class Meta:
        db_table = "dashboard_anomaly"
        verbose_name = "Anomaly"
        verbose_name_plural = "Anomalies"
        ordering = ["anomaly_score"]  # Most anomalous first
        indexes = [
            models.Index(
                fields=["severity", "anomaly_score"],
                name="idx_anomaly_severity_score",
            ),
            models.Index(
                fields=["job", "severity"],
                name="idx_anomaly_job_severity",
            ),
        ]

    def __str__(self) -> str:
        computer = self.computer_name or "Unknown"
        return (
            f"Anomaly #{self.pk} — {self.get_severity_display()} "
            f"({self.anomaly_score:.4f}) on {computer}"
        )

    @property
    def is_critical(self) -> bool:
        """Whether this anomaly requires immediate investigation."""
        return self.severity == self.Severity.CRITICAL

    @property
    def is_actionable(self) -> bool:
        """Whether this anomaly is HIGH or CRITICAL severity."""
        return self.severity in (self.Severity.CRITICAL, self.Severity.HIGH)


# ===========================================================================
# AuditLog Model
# ===========================================================================


class AuditLog(models.Model):
    """
    Append-only compliance log for recording all user actions.

    WHY THIS EXISTS:
      Enterprise SOC platforms require accountability. Every significant
      user action (login, upload, view, delete) is recorded with the
      user's identity, IP address, and timestamp.

    IMMUTABILITY:
      This model is designed to be append-only. Application logic must
      NOT allow editing or deleting audit log entries. The Django admin
      registration enforces read-only access.

    RELATIONSHIPS:
      - ForeignKey to User (SET_NULL: audit logs survive user deletion).
      - ForeignKey to AnalysisJob (SET_NULL, nullable: not all actions
        relate to a specific job, e.g., LOGIN).
    """

    class Action(models.TextChoices):
        """Enumeration of auditable user actions."""
        LOGIN = "LOGIN", "User Login"
        LOGOUT = "LOGOUT", "User Logout"
        UPLOAD = "UPLOAD", "File Upload"
        VIEW = "VIEW", "View Results"
        DELETE = "DELETE", "Delete Record"
        EXPORT = "EXPORT", "Export Report"

    # --- Relationships ---
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_logs",
        help_text="The user who performed the action.",
    )

    job = models.ForeignKey(
        AnalysisJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="The analysis job related to this action (if applicable).",
    )

    # --- Action Details ---
    action = models.CharField(
        max_length=10,
        choices=Action.choices,
        db_index=True,
        help_text="The type of action performed.",
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP address at the time of the action.",
    )

    # --- Timestamp ---
    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the action was performed.",
    )

    class Meta:
        db_table = "dashboard_auditlog"
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["action", "created_at"],
                name="idx_audit_action_created",
            ),
            models.Index(
                fields=["user", "created_at"],
                name="idx_audit_user_created",
            ),
        ]

    def __str__(self) -> str:
        username = self.user.username if self.user else "System"
        return (
            f"[{self.created_at:%Y-%m-%d %H:%M}] "
            f"{username} — {self.get_action_display()}"
        )
