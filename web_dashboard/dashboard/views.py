"""
dashboard/views.py — Phase 9A
================================
Django view controllers for dashboard pages.

VIEWS:
  home         — Landing page / dashboard home (auth-aware).
  health_check — System health check endpoint (public).

FUTURE VIEWS (Phase 10+):
  alerts       — Paginated anomaly list.
  upload       — EVTX file upload.
  history      — Analysis history with search/filter.

DESIGN DECISIONS:
  - Home view renders different content for authenticated vs
    unauthenticated users (via template logic in home.html).
  - Health check remains public for infrastructure monitoring.
"""

import logging

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)


def home(request: HttpRequest) -> HttpResponse:
    """
    Render the dashboard home page.

    Displays different content based on authentication status:
      - Authenticated: Dashboard with stats and quick actions.
      - Unauthenticated: Landing page with sign-in/register CTAs.

    Args:
        request: The HTTP request.

    Returns:
        Rendered home page.
    """
    return render(request, "dashboard/home.html")


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
        "Django Dashboard is running. Phase 9A auth active.",
        content_type="text/plain",
    )
