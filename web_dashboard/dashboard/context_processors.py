"""
dashboard/context_processors.py — RC Stabilization
===============================================
Template context processors for the SOC Dashboard.

PURPOSE:
  Inject navigation metadata and alert counts into every template
  so that sidebar active states and navbar notification badges
  can be computed without JavaScript or manual per-view context.

DESIGN:
  - Uses URL path matching to determine the current navigation item.
  - Queries critical/high alert counts for the navbar bell badge.
  - Returns a simple dict consumed by _sidebar.html and base.html.
  - Lightweight — navigation is path-only, alert counts are cached
    per request.

REGISTRATION:
  Add to settings.py TEMPLATES → OPTIONS → context_processors:
    "dashboard.context_processors.dashboard_context"
"""

import logging
from typing import Any

from django.http import HttpRequest

logger = logging.getLogger(__name__)


def dashboard_context(request: HttpRequest) -> dict[str, Any]:
    """
    Inject dashboard-wide context variables into every template.

    Variables injected:
      - active_nav: String identifying the current navigation item.
        Used by _sidebar.html to highlight the active link.
      - current_path: The current request path for URL matching.
      - navbar_alert_count: Total critical + high alerts for bell badge.
      - navbar_critical_count: Critical alert count for dropdown.
      - navbar_high_count: High alert count for dropdown.

    The active_nav value is determined by matching the request path
    against known URL prefixes. Order matters — more specific paths
    must come first.

    Args:
        request: The current HTTP request.

    Returns:
        Dictionary of context variables.
    """
    path = request.path

    # Map URL prefixes to navigation item identifiers.
    # Order: most specific first to avoid false matches.
    nav_map = [
        ("/alerts/", "alerts"),
        ("/upload/", "upload"),
        ("/analysis/", "analysis"),
        ("/history/", "history"),
        ("/profile/", "profile"),
        ("/auth/profile/", "profile"),
        ("/admin/", "admin"),
    ]

    active_nav = "dashboard"  # Default: home page

    for prefix, nav_id in nav_map:
        if path.startswith(prefix):
            active_nav = nav_id
            break

    # Root path is the dashboard home
    if path == "/":
        active_nav = "dashboard"

    context = {
        "active_nav": active_nav,
        "current_path": path,
    }

    # Alert counts for navbar notification bell (authenticated users only)
    if hasattr(request, "user") and request.user.is_authenticated:
        try:
            from .models import Anomaly
            from .permissions import DashboardPermissions

            is_admin = request.user.has_perm(
                DashboardPermissions.VIEW_SYSTEM_STATS
            )

            if is_admin:
                anomalies_qs = Anomaly.objects.all()
            else:
                anomalies_qs = Anomaly.objects.filter(
                    job__user=request.user
                )

            critical = anomalies_qs.filter(
                severity=Anomaly.Severity.CRITICAL
            ).count()
            high = anomalies_qs.filter(
                severity=Anomaly.Severity.HIGH
            ).count()

            context["navbar_critical_count"] = critical
            context["navbar_high_count"] = high
            context["navbar_alert_count"] = critical + high

        except Exception:
            # Graceful degradation — bell simply shows no badge
            context["navbar_critical_count"] = 0
            context["navbar_high_count"] = 0
            context["navbar_alert_count"] = 0

    return context
