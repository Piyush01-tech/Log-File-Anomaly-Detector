"""
dashboard/context_processors.py — Phase 11A
===============================================
Template context processors for the SOC Dashboard.

PURPOSE:
  Inject navigation metadata into every template so that
  sidebar and navbar active states can be computed without
  JavaScript or manual per-view context.

DESIGN:
  - Uses URL path matching to determine the current navigation item.
  - Returns a simple dict consumed by _sidebar.html and base.html.
  - Lightweight — no database queries, no I/O.

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

    return {
        "active_nav": active_nav,
        "current_path": path,
    }
