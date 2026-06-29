"""
dashboard/urls.py — Phase 10
===============================
URL patterns for the dashboard Django application.

ROUTES:
  /                      → home (dashboard landing page)
  /health/               → health_check (infrastructure monitoring)
  /upload/               → upload_view (EVTX file upload) [Phase 10]
  /analysis/<int:pk>/    → AnalysisDetailView (job results) [Phase 10]
  /history/              → AnalysisHistoryView (analysis history) [Phase 10]

NOTE: Authentication routes are in auth_urls.py under /auth/ prefix.
"""

from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    # Dashboard home page
    path("", views.home, name="home"),

    # Infrastructure health check (public)
    path("health/", views.health_check, name="health_check"),

    # Phase 10: Upload & Analysis Workflow
    path("upload/", views.upload_view, name="upload"),
    path(
        "analysis/<int:pk>/",
        views.AnalysisDetailView.as_view(),
        name="analysis_detail",
    ),
    path(
        "history/",
        views.AnalysisHistoryView.as_view(),
        name="analysis_history",
    ),
]
