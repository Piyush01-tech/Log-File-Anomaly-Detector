"""
dashboard/urls.py — Phase 9A
===============================
URL patterns for the dashboard Django application.

ROUTES:
  /          → home (dashboard landing page)
  /health/   → health_check (infrastructure monitoring)

FUTURE ROUTES (Phase 10+):
  /alerts/   → alerts (paginated anomaly list)
  /upload/   → upload (EVTX file upload)
  /history/  → history (analysis history)

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

    # Phase 10+ will add:
    # path("alerts/", views.alerts, name="alerts"),
    # path("upload/", views.upload, name="upload"),
    # path("history/", views.history, name="history"),
]
