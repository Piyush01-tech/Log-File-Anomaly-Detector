"""
dashboard/views.py — Phase 10
================================
Django view controllers for dashboard pages.

VIEWS:
  home                — Landing page / dashboard home (auth-aware, RBAC).
  health_check        — System health check endpoint (public).
  UploadView          — EVTX file upload and analysis trigger (Phase 10).
  AnalysisDetailView  — Analysis job results with anomaly listing (Phase 10).
  AnalysisHistoryView — Paginated list of user's analysis jobs (Phase 10).

PHASE 10 CHANGES:
  - Added UploadView: handles file upload, validation, Flask API call,
    result persistence, and redirect to detail page.
  - Added AnalysisDetailView: displays job summary and anomaly table
    with ownership enforcement.
  - Added AnalysisHistoryView: paginated job list with user isolation.
  - Updated home view context to include recent job counts.

ARCHITECTURE:
  - Upload workflow uses FlaskAPIClient (services.py) as the ACL.
  - Django NEVER imports from ml_engine directly.
  - OwnershipMixin and AnalystOwnerQuerysetMixin enforce user isolation.
  - All upload actions are audit-logged.
"""

import logging
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.generic import DetailView, ListView

from django.db.models import Sum
from .auth_views import _create_audit_log, _get_client_ip
from .forms import EVTXUploadForm
from .models import AnalysisJob, Anomaly, AuditLog, User
from .permissions import DashboardPermissions
from .rbac_mixins import AnalystOwnerQuerysetMixin, OwnershipMixin
from .services import FlaskAPIClient, FlaskAPIError

logger = logging.getLogger(__name__)


# ===========================================================================
# Dashboard Home
# ===========================================================================


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """
    Render the dashboard home page.

    Displays different content based on user role (Phase 9B):
      - Super Admins: System-wide statistics and management actions.
      - Analysts: Personal statistics and upload actions.

    Phase 10: Added recent analysis counts and completed job stats.

    Args:
        request: The HTTP request.

    Returns:
        Rendered home page.
    """
    context = {}

    # Super Admin context
    if request.user.has_perm(DashboardPermissions.VIEW_SYSTEM_STATS):
        context["total_users"] = User.objects.count()
        context["total_jobs"] = AnalysisJob.objects.count()
        context["completed_jobs"] = AnalysisJob.objects.filter(
            status=AnalysisJob.Status.COMPLETED
        ).count()
        context["failed_jobs"] = AnalysisJob.objects.filter(
            status=AnalysisJob.Status.FAILED
        ).count()
        context["total_anomalies_count"] = AnalysisJob.objects.aggregate(
            total=Sum('total_anomalies')
        )['total'] or 0
        
        # Recent data for admin (all users)
        context["recent_uploads"] = AnalysisJob.objects.all()[:5]
        context["recent_analyses"] = AnalysisJob.objects.filter(
            status=AnalysisJob.Status.COMPLETED
        )[:5]

        logger.debug("Admin context loaded for user '%s'.", request.user.username)

    # Analyst context (personal stats)
    else:
        user_jobs = AnalysisJob.objects.filter(user=request.user)
        context["my_jobs_count"] = user_jobs.count()
        context["my_completed_jobs"] = user_jobs.filter(
            status=AnalysisJob.Status.COMPLETED
        ).count()
        context["my_failed_jobs"] = user_jobs.filter(
            status=AnalysisJob.Status.FAILED
        ).count()
        context["my_anomalies_count"] = user_jobs.aggregate(
            total=Sum('total_anomalies')
        )['total'] or 0
        
        # Recent data for analyst (own data only)
        context["recent_uploads"] = user_jobs[:5]
        context["recent_analyses"] = user_jobs.filter(
            status=AnalysisJob.Status.COMPLETED
        )[:5]

        logger.debug("Analyst context loaded for user '%s'.", request.user.username)

    return render(request, "dashboard/home.html", context)


# ===========================================================================
# Dashboard Profile (Phase 11A)
# ===========================================================================

@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """
    Render the dashboard profile page.
    
    Displays user account information and personal activity statistics.
    This is distinct from the auth/profile view which is for editing.
    """
    context = {}
    
    # Personal stats for the profile
    user_jobs = AnalysisJob.objects.filter(user=request.user)
    context["my_jobs_count"] = user_jobs.count()
    context["my_anomalies_count"] = user_jobs.aggregate(
        total=Sum('total_anomalies')
    )['total'] or 0
    
    return render(request, "dashboard/profile.html", context)


# ===========================================================================
# Health Check
# ===========================================================================


def health_check(request: HttpRequest) -> HttpResponse:
    """
    System health check endpoint.

    Public endpoint for infrastructure monitoring (load balancers,
    orchestration tools). Returns plain text status.

    Args:
        request: The HTTP request.

    Returns:
        Plain text health status.
    """
    return HttpResponse(
        "Django Dashboard is running. Phase 10 Upload Workflow active.",
        content_type="text/plain",
    )


# ===========================================================================
# Upload View (Phase 10)
# ===========================================================================


@login_required
def upload_view(request: HttpRequest) -> HttpResponse:
    """
    Handle EVTX file upload and trigger ML analysis.

    GET:  Render the upload form.
    POST: Validate the file, create an AnalysisJob, call Flask API,
          persist results, and redirect to the detail page.

    WORKFLOW:
      1. Validate uploaded file (extension, size).
      2. Create AnalysisJob record (PENDING).
      3. Save uploaded file to MEDIA_ROOT.
      4. Create AuditLog entry (UPLOAD action).
      5. Mark job as RUNNING.
      6. Call FlaskAPIClient.analyze() synchronously.
      7a. On success: mark COMPLETED, bulk-create Anomaly records.
      7b. On failure: mark FAILED with error message.
      8. Redirect to analysis detail page.

    SECURITY:
      - @login_required enforces authentication.
      - Permission check for upload_evtx.
      - File ownership is set to request.user.
      - CSRF enforced by Django middleware.

    Args:
        request: The HTTP request.

    Returns:
        GET:  Rendered upload form page.
        POST: Redirect to analysis detail or upload page (on error).
    """
    # Permission check
    if not request.user.has_perm(DashboardPermissions.UPLOAD_EVTX):
        messages.error(
            request,
            "You do not have permission to upload files.",
        )
        return redirect("dashboard:home")

    if request.method == "GET":
        form = EVTXUploadForm()
        return render(request, "dashboard/upload.html", {"form": form})

    # --- POST: Handle file upload ---
    form = EVTXUploadForm(request.POST, request.FILES)

    if not form.is_valid():
        return render(request, "dashboard/upload.html", {"form": form})

    uploaded_file = form.cleaned_data["evtx_file"]

    # --- Step 1: Create AnalysisJob (PENDING) ---
    job = AnalysisJob(
        user=request.user,
        original_filename=uploaded_file.name,
        status=AnalysisJob.Status.PENDING,
    )
    # Save the file via FileField (triggers _upload_to_evtx for unique path)
    job.file_path.save(uploaded_file.name, uploaded_file, save=False)
    job.save()

    logger.info(
        "AnalysisJob #%d created: user='%s', file='%s'.",
        job.pk,
        request.user.username,
        uploaded_file.name,
    )

    # --- Step 2: Audit log ---
    _create_audit_log(
        user=request.user,
        action=AuditLog.Action.UPLOAD,
        request=request,
        job=job,
    )

    # --- Step 3: Get absolute file path for Flask ---
    absolute_file_path = Path(settings.MEDIA_ROOT) / str(job.file_path)

    # --- Step 4: Mark as RUNNING and call Flask API ---
    job.mark_running()

    try:
        result = FlaskAPIClient.analyze(
            file_path=str(absolute_file_path),
            job_id=job.pk,
        )

    except FlaskAPIError as exc:
        # Flask communication failed — mark job as FAILED
        job.mark_failed(error_message=str(exc.message))
        logger.error(
            "Analysis failed for Job #%d: %s", job.pk, exc.message
        )
        messages.error(
            request,
            f"Analysis failed: {exc.message}",
        )
        return redirect("dashboard:analysis_detail", pk=job.pk)

    except Exception as exc:
        # Unexpected error — mark job as FAILED
        job.mark_failed(error_message=f"Unexpected error: {str(exc)}")
        logger.exception(
            "Unexpected error during analysis for Job #%d.", job.pk
        )
        messages.error(
            request,
            "An unexpected error occurred during analysis. "
            "Please try again or contact an administrator.",
        )
        return redirect("dashboard:analysis_detail", pk=job.pk)

    # --- Step 5: Mark as COMPLETED ---
    job.mark_completed(
        total_samples=result.total_samples,
        total_anomalies=result.total_anomalies,
    )

    # --- Step 6: Bulk-create Anomaly records ---
    anomaly_objects = []
    for anomaly_data in result.anomalies:
        anomaly_objects.append(
            Anomaly(
                job=job,
                window_start=_parse_anomaly_timestamp(
                    anomaly_data.get("timestamp")
                ),
                computer_name=anomaly_data.get("computer", ""),
                anomaly_score=anomaly_data.get("anomaly_score", 0.0),
                severity=_map_severity(
                    anomaly_data.get("severity", "LOW")
                ),
                feature_data=anomaly_data.get("features", {}),
            )
        )

    if anomaly_objects:
        Anomaly.objects.bulk_create(anomaly_objects)
        logger.info(
            "Created %d Anomaly records for Job #%d.",
            len(anomaly_objects),
            job.pk,
        )

    messages.success(
        request,
        f"Analysis complete: {result.total_anomalies} anomalies detected "
        f"out of {result.total_samples} time windows analyzed.",
    )

    return redirect("dashboard:analysis_detail", pk=job.pk)


# ===========================================================================
# Upload Helper Functions
# ===========================================================================


def _parse_anomaly_timestamp(timestamp_str: Any) -> Any:
    """
    Parse an anomaly timestamp string into a timezone-aware datetime.

    The Flask API returns timestamps in various formats. This function
    handles ISO 8601 and common variants gracefully.

    Args:
        timestamp_str: Timestamp string from Flask API response.

    Returns:
        A timezone-aware datetime object, or timezone.now() as fallback.
    """
    from django.utils import timezone as tz
    from datetime import datetime

    if not timestamp_str:
        return tz.now()

    # Handle string timestamps
    if isinstance(timestamp_str, str):
        # Try ISO 8601 format
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
        ):
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                return tz.make_aware(dt, tz.utc)
            except (ValueError, TypeError):
                continue

        # Try pandas Timestamp string format
        try:
            from django.utils.dateparse import parse_datetime
            parsed = parse_datetime(timestamp_str)
            if parsed:
                if tz.is_naive(parsed):
                    return tz.make_aware(parsed, tz.utc)
                return parsed
        except (ValueError, TypeError):
            pass

    logger.warning(
        "Could not parse anomaly timestamp '%s', using current time.",
        timestamp_str,
    )
    return tz.now()


def _map_severity(severity_str: str) -> str:
    """
    Map a severity string from Flask to the Anomaly.Severity enum value.

    Normalizes case and validates against known severity levels.

    Args:
        severity_str: Severity string from Flask API response.

    Returns:
        A valid Anomaly.Severity choice value.
    """
    severity_upper = severity_str.upper().strip() if severity_str else "LOW"

    valid_severities = {
        "CRITICAL": Anomaly.Severity.CRITICAL,
        "HIGH": Anomaly.Severity.HIGH,
        "MEDIUM": Anomaly.Severity.MEDIUM,
        "LOW": Anomaly.Severity.LOW,
    }

    return valid_severities.get(severity_upper, Anomaly.Severity.LOW)


# ===========================================================================
# Analysis Detail View (Phase 10)
# ===========================================================================


class AnalysisDetailView(
    LoginRequiredMixin,
    OwnershipMixin,
    DetailView,
):
    """
    Display the results of a single analysis job.

    Shows:
      - Job metadata (filename, status, timestamps).
      - Summary statistics (total samples, anomalies, anomaly rate).
      - Anomaly table with severity, score, timestamp, and features.
      - Error message if the job failed.

    SECURITY:
      - LoginRequiredMixin: authenticated users only.
      - OwnershipMixin: analysts can only view their own jobs.
        Super Admins can view all jobs (admin bypass).

    URL: /analysis/<int:pk>/
    """

    model = AnalysisJob
    template_name = "dashboard/analysis_detail.html"
    context_object_name = "job"
    owner_field = "user"

    def get_context_data(self, **kwargs: Any) -> dict:
        """Add anomalies queryset to the template context."""
        context = super().get_context_data(**kwargs)
        job = self.object  # Already fetched by DetailView.get()

        # Get anomalies ordered by severity (most severe first)
        context["anomalies"] = job.anomalies.all().order_by("anomaly_score")
        context["anomaly_count"] = job.anomalies.count()

        # Severity breakdown
        context["critical_count"] = job.anomalies.filter(
            severity=Anomaly.Severity.CRITICAL
        ).count()
        context["high_count"] = job.anomalies.filter(
            severity=Anomaly.Severity.HIGH
        ).count()
        context["medium_count"] = job.anomalies.filter(
            severity=Anomaly.Severity.MEDIUM
        ).count()
        context["low_count"] = job.anomalies.filter(
            severity=Anomaly.Severity.LOW
        ).count()

        # Log audit view
        _create_audit_log(
            user=self.request.user,
            action=AuditLog.Action.VIEW,
            request=self.request,
            job=job,
        )

        return context


# ===========================================================================
# Analysis History View (Phase 10)
# ===========================================================================


class AnalysisHistoryView(
    LoginRequiredMixin,
    AnalystOwnerQuerysetMixin,
    ListView,
):
    """
    Display paginated list of analysis jobs.

    Shows:
      - Job filename, status, upload time, anomaly count.
      - Status badges (PENDING, RUNNING, COMPLETED, FAILED).
      - Links to individual analysis detail pages.

    SECURITY:
      - LoginRequiredMixin: authenticated users only.
      - AnalystOwnerQuerysetMixin: analysts see only their own jobs;
        Super Admins see all jobs.

    URL: /history/
    """

    model = AnalysisJob
    template_name = "dashboard/analysis_history.html"
    context_object_name = "jobs"
    paginate_by = 15
    ordering = ["-uploaded_at"]
    owner_field = "user"
