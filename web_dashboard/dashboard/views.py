"""
dashboard/views.py — Phase 9B
================================
Django view controllers for dashboard pages.

VIEWS:
  home         — Landing page / dashboard home (auth-aware, RBAC-enforced).
  health_check — System health check endpoint (public).

PHASE 9B CHANGES:
  - Added @login_required to home view to ensure only authenticated
    users can access the dashboard.
  - Added role-aware context to home view (Super Admins get system
    stats, Analysts get personal stats).
"""

import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import AnalysisJob, User
from .permissions import DashboardPermissions

logger = logging.getLogger(__name__)


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """
    Render the dashboard home page.

    Displays different content based on user role (Phase 9B):
      - Super Admins: System-wide statistics and management actions.
      - Analysts: Personal statistics and upload actions.

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
        context["failed_jobs"] = AnalysisJob.objects.filter(
            status=AnalysisJob.Status.FAILED
        ).count()
        logger.debug("Admin context loaded for user '%s'.", request.user.username)

    # Analyst context (personal stats)
    else:
        context["my_jobs_count"] = AnalysisJob.objects.filter(
            user=request.user
        ).count()
        context["my_failed_jobs"] = AnalysisJob.objects.filter(
            user=request.user, status=AnalysisJob.Status.FAILED
        ).count()
        logger.debug("Analyst context loaded for user '%s'.", request.user.username)

    return render(request, "dashboard/home.html", context)


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
        "Django Dashboard is running. Phase 9B RBAC active.",
        content_type="text/plain",
    )
