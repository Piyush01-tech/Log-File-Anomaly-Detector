"""
dashboard/analytics.py — Phase 12
====================================
Backend API for the Analytics & Visualization Framework.

Provides a single JSON endpoint that aggregates all chart data from
Django ORM models, scoped by the requesting user's role:
  - Super Admins: System-wide data across all users.
  - Analysts:     Personal data scoped to their own analysis jobs.

ENDPOINT:
  GET /api/analytics/
  Response: JSON with all chart datasets.

ARCHITECTURE:
  - Uses Django ORM aggregation (Count, Sum, values, annotate).
  - Extracts feature data from Anomaly.feature_data JSONField.
  - All aggregation happens at the database level for performance.
  - Time-series data limited to last 90 days by default.
  - Django NEVER imports from ml_engine directly.

DESIGN DECISIONS:
  - Single endpoint over multiple: reduces HTTP round-trips on
    dashboard load and simplifies frontend orchestration.
  - Role-aware scoping via the same pattern used in views.py
    (DashboardPermissions.VIEW_SYSTEM_STATS check).
"""

import logging
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.utils import timezone

from .models import AnalysisJob, Anomaly, AuditLog
from .permissions import DashboardPermissions

logger = logging.getLogger(__name__)

# Maximum number of days to include in time-series charts
TIME_SERIES_DAYS = 90

# Maximum items for "top N" charts
TOP_N_LIMIT = 10


@login_required
def analytics_api(request) -> JsonResponse:
    """
    Return aggregated analytics data for the dashboard charts.

    All data is scoped by the user's role:
      - Users with VIEW_SYSTEM_STATS permission see system-wide data.
      - Other users see only their own analysis results.

    Returns:
        JsonResponse with chart datasets.
    """
    try:
        is_admin = request.user.has_perm(DashboardPermissions.VIEW_SYSTEM_STATS)

        # Build base querysets scoped by role
        jobs_qs = AnalysisJob.objects.all()
        anomalies_qs = Anomaly.objects.select_related('job').all()

        if not is_admin:
            jobs_qs = jobs_qs.filter(user=request.user)
            anomalies_qs = anomalies_qs.filter(job__user=request.user)

        # Time boundary for time-series data: 
        # Calculate relative to the most recent data point so historical EVTX files display correctly.
        latest_anomaly = anomalies_qs.order_by('-window_start').first()
        if latest_anomaly:
            time_cutoff = latest_anomaly.window_start - timedelta(days=TIME_SERIES_DAYS)
        else:
            time_cutoff = timezone.now() - timedelta(days=TIME_SERIES_DAYS)

        data = {
            "severity_distribution": _severity_distribution(anomalies_qs),
            "anomalies_over_time": _anomalies_over_time(anomalies_qs, time_cutoff),
            "login_trends": _login_trends(anomalies_qs, time_cutoff),
            "top_event_ids": _top_event_ids(anomalies_qs),
            "top_hosts": _top_hosts(anomalies_qs),
            "analysis_status": _analysis_status(jobs_qs),
            "recent_activity": _recent_activity(request.user, is_admin),
            "system_health": _system_health(jobs_qs, anomalies_qs),
        }

        logger.debug(
            "Analytics API served for user='%s' (admin=%s).",
            request.user.username,
            is_admin,
        )

        return JsonResponse({"status": "success", "data": data})

    except Exception as exc:
        logger.exception("Analytics API error for user '%s'.", request.user.username)
        return JsonResponse(
            {"status": "error", "message": str(exc)},
            status=500,
        )


# ===========================================================================
# Aggregation Functions
# ===========================================================================


def _severity_distribution(anomalies_qs) -> dict[str, int]:
    """
    Count anomalies grouped by severity level.

    Returns:
        Dict mapping severity labels to counts.
        Example: {"CRITICAL": 5, "HIGH": 12, "MEDIUM": 30, "LOW": 45}
    """
    counts = anomalies_qs.values("severity").annotate(
        count=Count("id")
    ).order_by("severity")

    result = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
    }
    for entry in counts:
        if entry["severity"] in result:
            result[entry["severity"]] = entry["count"]

    return result


def _anomalies_over_time(anomalies_qs, time_cutoff) -> list[dict[str, Any]]:
    """
    Count anomalies per day, grouped by severity, within the time window.

    Returns:
        List of dicts: [{date, critical, high, medium, low}, ...]
    """
    recent = anomalies_qs.filter(window_start__gte=time_cutoff)

    daily = recent.annotate(
        date=TruncDate("window_start")
    ).values("date", "severity").annotate(
        count=Count("id")
    ).order_by("date")

    # Pivot severity into columns per date
    date_map: dict[str, dict[str, int]] = defaultdict(
        lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0}
    )

    for entry in daily:
        if entry["date"] is None:
            continue
        date_str = entry["date"].isoformat()
        severity_key = entry["severity"].lower()
        if severity_key in date_map[date_str]:
            date_map[date_str][severity_key] = entry["count"]

    result = []
    for date_str in sorted(date_map.keys()):
        row = {"date": date_str}
        row.update(date_map[date_str])
        result.append(row)

    return result


def _login_trends(anomalies_qs, time_cutoff) -> list[dict[str, Any]]:
    """
    Extract failed and successful login counts from feature_data JSONField.

    The ML pipeline stores 'failed_logins' and 'successful_logins' as
    features in each anomaly's feature_data dict.

    Returns:
        List of dicts: [{date, failed, success}, ...]
    """
    recent = anomalies_qs.filter(window_start__gte=time_cutoff)

    date_map: dict[str, dict[str, int]] = defaultdict(
        lambda: {"failed": 0, "success": 0}
    )

    for anomaly in recent.only("window_start", "feature_data"):
        if anomaly.window_start is None:
            continue
        date_str = anomaly.window_start.date().isoformat()
        features = anomaly.feature_data or {}

        date_map[date_str]["failed"] += int(
            features.get("failed_logins", 0)
        )
        date_map[date_str]["success"] += int(
            features.get("successful_logins", 0)
        )

    result = []
    for date_str in sorted(date_map.keys()):
        row = {"date": date_str}
        row.update(date_map[date_str])
        result.append(row)

    return result


def _top_event_ids(anomalies_qs) -> list[dict[str, Any]]:
    """
    Extract the most common event IDs from anomaly feature_data.

    Aggregates event type features across all anomalies. The feature
    names map directly to event categories (e.g. 'failed_logins',
    'process_creation_events', 'privilege_escalation_events').

    Returns:
        List of top N event feature categories with their total counts.
    """
    feature_totals: Counter = Counter()

    # Feature keys that represent countable event types
    event_features = [
        "failed_logins",
        "successful_logins",
        "account_lockouts",
        "password_changes",
        "user_account_changes",
        "process_creation_events",
        "privilege_escalation_events",
        "logon_logoff_events",
        "object_access_events",
        "policy_change_events",
        "system_events",
        "security_log_cleared",
    ]

    for anomaly in anomalies_qs.only("feature_data"):
        features = anomaly.feature_data or {}
        for key in event_features:
            val = features.get(key, 0)
            if val and float(val) > 0:
                feature_totals[key] += int(float(val))

    # Format feature names for display
    result = []
    for key, count in feature_totals.most_common(TOP_N_LIMIT):
        label = key.replace("_", " ").title()
        result.append({"event_id": key, "label": label, "count": count})

    return result


def _top_hosts(anomalies_qs) -> list[dict[str, Any]]:
    """
    Count anomalies per computer_name (top targeted hosts).

    Returns:
        List of top N hosts with anomaly counts.
    """
    hosts = anomalies_qs.exclude(
        computer_name=""
    ).values("computer_name").annotate(
        count=Count("id")
    ).order_by("-count")[:TOP_N_LIMIT]

    return [
        {"hostname": h["computer_name"], "count": h["count"]}
        for h in hosts
    ]


def _analysis_status(jobs_qs) -> dict[str, int]:
    """
    Count analysis jobs grouped by status.

    Returns:
        Dict mapping status labels to counts.
    """
    counts = jobs_qs.values("status").annotate(
        count=Count("id")
    )

    result = {
        "COMPLETED": 0,
        "FAILED": 0,
        "RUNNING": 0,
        "PENDING": 0,
    }
    for entry in counts:
        if entry["status"] in result:
            result[entry["status"]] = entry["count"]

    return result


def _recent_activity(user, is_admin: bool) -> list[dict[str, Any]]:
    """
    Get recent audit log entries for the activity timeline.

    Returns:
        List of recent activity entries (max 10).
    """
    audit_qs = AuditLog.objects.select_related("user", "job").order_by(
        "-created_at"
    )

    if not is_admin:
        audit_qs = audit_qs.filter(user=user)

    entries = []
    for log in audit_qs[:10]:
        entry = {
            "action": log.get_action_display(),
            "user": log.user.username if log.user else "System",
            "timestamp": log.created_at.isoformat(),
            "detail": "",
        }
        if log.job:
            entry["detail"] = log.job.original_filename
        entries.append(entry)

    return entries


def _system_health(jobs_qs, anomalies_qs) -> dict[str, Any]:
    """
    Compute system health summary metrics.

    Returns:
        Dict with aggregate health indicators.
    """
    total_jobs = jobs_qs.count()
    completed_jobs = jobs_qs.filter(
        status=AnalysisJob.Status.COMPLETED
    ).count()
    failed_jobs = jobs_qs.filter(
        status=AnalysisJob.Status.FAILED
    ).count()

    total_anomalies = anomalies_qs.count()
    critical_count = anomalies_qs.filter(
        severity=Anomaly.Severity.CRITICAL
    ).count()
    high_count = anomalies_qs.filter(
        severity=Anomaly.Severity.HIGH
    ).count()

    # Calculate success rate
    success_rate = 0
    if total_jobs > 0:
        success_rate = round((completed_jobs / total_jobs) * 100, 1)

    # Total samples analyzed
    total_samples = jobs_qs.aggregate(
        total=Sum("total_samples")
    )["total"] or 0

    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "total_anomalies": total_anomalies,
        "critical_count": critical_count,
        "high_count": high_count,
        "success_rate": success_rate,
        "total_samples": total_samples,
    }
