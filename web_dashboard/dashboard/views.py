"""
dashboard/views.py — Phase 12
================================
Django view controllers for dashboard pages.

VIEWS:
  home                — Landing page / dashboard home (auth-aware, RBAC).
  health_check        — System health check endpoint (public).
  profile_view        — Dashboard profile page (Phase 11A).
  UploadView          — EVTX file upload and analysis trigger (Phase 10).
  AnalysisDetailView  — Analysis job results with anomaly listing (Phase 10).
  AnalysisHistoryView — Paginated list of user's analysis jobs (Phase 10).
  AlertsListView      — Paginated, searchable, filterable anomaly list (Phase 11B).
  AlertDetailView     — Single anomaly incident detail page (Phase 11B).

PHASE 12 CHANGES:
  - Analytics API endpoint moved to analytics.py for separation of concerns.
  - Home view unchanged — chart data is fetched client-side via /api/analytics/.

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
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.generic import DetailView, ListView

from django.db.models import Sum
from .auth_views import _create_audit_log, _get_client_ip
from .forms import EVTXUploadForm
from .models import AnalysisJob, Anomaly, AuditLog, User
from .permissions import DashboardPermissions, is_object_owner
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
      - Super Admins: System-wide statistics, management actions,
        critical alert counts, and recent alerts.
      - Analysts: Personal statistics, upload actions, and own alerts.

    Phase 10: Added recent analysis counts and completed job stats.
    Phase 11B: Added critical/high alert counts and recent alerts table.

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

        # Phase 11B: Alert severity counts (system-wide)
        context["critical_alerts"] = Anomaly.objects.filter(
            severity=Anomaly.Severity.CRITICAL
        ).count()
        context["high_alerts"] = Anomaly.objects.filter(
            severity=Anomaly.Severity.HIGH
        ).count()

        # Recent data for admin (all users)
        context["recent_uploads"] = AnalysisJob.objects.select_related(
            'user'
        )[:5]
        context["recent_analyses"] = AnalysisJob.objects.filter(
            status=AnalysisJob.Status.COMPLETED
        ).select_related('user')[:5]

        # Phase 11B: Recent critical/high alerts
        context["recent_alerts"] = Anomaly.objects.filter(
            severity__in=[Anomaly.Severity.CRITICAL, Anomaly.Severity.HIGH]
        ).select_related('job', 'job__user').order_by(
            'anomaly_score'
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

        # Phase 11B: Alert severity counts (personal)
        user_anomalies = Anomaly.objects.filter(job__user=request.user)
        context["critical_alerts"] = user_anomalies.filter(
            severity=Anomaly.Severity.CRITICAL
        ).count()
        context["high_alerts"] = user_anomalies.filter(
            severity=Anomaly.Severity.HIGH
        ).count()

        # Recent data for analyst (own data only)
        context["recent_uploads"] = user_jobs[:5]
        context["recent_analyses"] = user_jobs.filter(
            status=AnalysisJob.Status.COMPLETED
        )[:5]

        # Phase 11B: Recent critical/high alerts (own only)
        context["recent_alerts"] = user_anomalies.filter(
            severity__in=[Anomaly.Severity.CRITICAL, Anomaly.Severity.HIGH]
        ).select_related('job').order_by(
            'anomaly_score'
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
        "Django Dashboard is running. Phase 11B Dashboard Features active.",
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
# Analysis History View (Phase 10, Enhanced Phase 11B)
# ===========================================================================


class AnalysisHistoryView(
    LoginRequiredMixin,
    AnalystOwnerQuerysetMixin,
    ListView,
):
    """
    Display paginated list of analysis jobs with search and filtering.

    Shows:
      - Job filename, status, upload time, anomaly count.
      - Status badges (PENDING, RUNNING, COMPLETED, FAILED).
      - Links to individual analysis detail pages.
      - Search by filename (Phase 11B).
      - Filter by status (Phase 11B).

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

    def get_queryset(self):
        """
        Override queryset to support search and status filter.

        GET params:
          - q: Search query (matches original_filename, case-insensitive).
          - status: Filter by job status (COMPLETED, FAILED, RUNNING, PENDING).
        """
        queryset = super().get_queryset().select_related('user')

        # Search filter
        search_query = self.request.GET.get("q", "").strip()
        if search_query:
            queryset = queryset.filter(
                original_filename__icontains=search_query
            )

        # Status filter
        status_filter = self.request.GET.get("status", "").strip().upper()
        if status_filter in dict(AnalysisJob.Status.choices):
            queryset = queryset.filter(status=status_filter)

        return queryset

    def get_context_data(self, **kwargs):
        """Add filter state to context for template rendering."""
        context = super().get_context_data(**kwargs)

        # Preserve filter state for the template
        search_query = self.request.GET.get("q", "").strip()
        status_filter = self.request.GET.get("status", "").strip().upper()

        context["current_search"] = search_query
        context["current_status"] = status_filter
        context["has_active_filters"] = bool(search_query or status_filter)

        return context


# ===========================================================================
# Alerts List View (Phase 11B)
# ===========================================================================


class AlertsListView(LoginRequiredMixin, ListView):
    """
    Display paginated list of anomalies (alerts) with search and filtering.

    The main SOC operational view showing all detected anomalies across
    analysis jobs with:
      - Search by computer name or parent job filename.
      - Filter by severity level.
      - Severity badges, anomaly scores, and time window display.
      - Links to individual alert detail pages and parent jobs.
      - Responsive table with SOC dark theme styling.

    SECURITY:
      - LoginRequiredMixin: authenticated users only.
      - Custom get_queryset: analysts see only their own alerts
        (filtered via job__user). Super Admins see all alerts.

    URL: /alerts/
    """

    model = Anomaly
    template_name = "dashboard/alerts.html"
    context_object_name = "alerts"
    paginate_by = 20
    ordering = ["anomaly_score"]  # Most anomalous first

    def get_queryset(self):
        """
        Return anomalies filtered by user permissions and search/filter params.

        User isolation:
          - Analysts see only anomalies from their own jobs.
          - Super Admins see all anomalies.

        GET params:
          - q: Search query (matches computer_name or job filename).
          - severity: Filter by anomaly severity (CRITICAL, HIGH, MEDIUM, LOW).
        """
        queryset = Anomaly.objects.select_related(
            'job', 'job__user'
        ).order_by('anomaly_score')

        # User isolation: analysts see only their own alerts
        if not self.request.user.has_perm(DashboardPermissions.VIEW_ALL_INCIDENTS):
            queryset = queryset.filter(job__user=self.request.user)

        # Search filter
        search_query = self.request.GET.get("q", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(computer_name__icontains=search_query) |
                Q(job__original_filename__icontains=search_query)
            )

        # Severity filter
        severity_filter = self.request.GET.get("severity", "").strip().upper()
        if severity_filter in dict(Anomaly.Severity.choices):
            queryset = queryset.filter(severity=severity_filter)

        return queryset

    def get_context_data(self, **kwargs):
        """Add filter state and summary counts to context."""
        context = super().get_context_data(**kwargs)

        # Preserve filter state
        search_query = self.request.GET.get("q", "").strip()
        severity_filter = self.request.GET.get("severity", "").strip().upper()

        context["current_search"] = search_query
        context["current_severity"] = severity_filter
        context["has_active_filters"] = bool(search_query or severity_filter)

        # Severity summary counts (from the full filtered queryset, not page)
        full_queryset = self.get_queryset()
        context["total_alerts"] = full_queryset.count()
        context["critical_count"] = full_queryset.filter(
            severity=Anomaly.Severity.CRITICAL
        ).count()
        context["high_count"] = full_queryset.filter(
            severity=Anomaly.Severity.HIGH
        ).count()
        context["medium_count"] = full_queryset.filter(
            severity=Anomaly.Severity.MEDIUM
        ).count()
        context["low_count"] = full_queryset.filter(
            severity=Anomaly.Severity.LOW
        ).count()

        return context


# ===========================================================================
# Alert Detail View (Phase 11B)
# ===========================================================================


class AlertDetailView(LoginRequiredMixin, DetailView):
    """
    Display detailed information for a single anomaly (incident).

    Shows:
      - Full anomaly metadata (severity, score, time window, computer).
      - Complete feature data grid (all 15 ML features).
      - Parent job link and metadata.
      - Analyst information (visible to admins).
      - Severity-aware visual styling.

    SECURITY:
      - LoginRequiredMixin: authenticated users only.
      - Custom get_object: ownership check via job.user relationship.
        Analysts can only view their own alerts. Super Admins can view all.

    URL: /alerts/<int:pk>/
    """

    model = Anomaly
    template_name = "dashboard/alert_detail.html"
    context_object_name = "alert"

    def get_object(self, queryset=None):
        """
        Get the anomaly and verify ownership via the parent job.

        Analysts can only view anomalies from their own jobs.
        Super Admins bypass the ownership check.

        Raises:
            PermissionDenied: If the user doesn't own the parent job
                              and lacks admin bypass.
        """
        obj = super().get_object(queryset)

        # Ownership check via parent job
        if not is_object_owner(
            self.request.user, obj.job, "user"
        ):
            logger.warning(
                "OWNERSHIP DENIED: user='%s' tried to access Anomaly #%s "
                "from Job #%s owned by '%s'.",
                self.request.user.username,
                obj.pk,
                obj.job.pk,
                obj.job.user.username,
            )
            raise PermissionDenied(
                "You do not have permission to access this alert."
            )

        return obj

    def get_context_data(self, **kwargs):
        """Add parent job and feature data to context."""
        context = super().get_context_data(**kwargs)
        alert = self.object

        # Parent job with preloaded user
        context["job"] = alert.job
        context["analyst"] = alert.job.user

        # Feature data as sorted items for consistent display
        if alert.feature_data:
            context["feature_items"] = sorted(
                alert.feature_data.items(),
                key=lambda x: x[0],
            )
        else:
            context["feature_items"] = []

        # Sibling anomalies from the same job for navigation
        siblings = alert.job.anomalies.all().order_by('anomaly_score')
        context["sibling_count"] = siblings.count()

        # Previous/Next navigation
        sibling_list = list(siblings.values_list('pk', flat=True))
        if alert.pk in sibling_list:
            current_idx = sibling_list.index(alert.pk)
            context["prev_alert_pk"] = (
                sibling_list[current_idx - 1] if current_idx > 0 else None
            )
            context["next_alert_pk"] = (
                sibling_list[current_idx + 1]
                if current_idx < len(sibling_list) - 1
                else None
            )

        # Audit log
        _create_audit_log(
            user=self.request.user,
            action=AuditLog.Action.VIEW,
            request=self.request,
            job=alert.job,
        )

        return context
