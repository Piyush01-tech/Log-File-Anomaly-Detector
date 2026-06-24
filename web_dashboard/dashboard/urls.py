"""
dashboard/urls.py
==================
URL patterns for the dashboard Django application.

Phase 8 will expand this with all dashboard routes.
Currently includes only a health check for Phase 1 verification.
"""

from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    # Phase 1 verification endpoint
    path("health/", views.health_check, name="health_check"),

    # Phase 8 will add:
    # path("", views.home, name="home"),
    # path("alerts/", views.alerts, name="alerts"),
    # path("upload/", views.upload, name="upload"),
    # path("history/", views.history, name="history"),
]
