"""
web_dashboard/web_dashboard/urls.py
======================================
Root URL dispatcher for the Django frontend service.

Routes:
  /          → dashboard app (home, alerts, upload, history)
  /admin/    → Django built-in admin panel
  /auth/     → Authentication (Phase 11)

Phase 8 will expand the dashboard URL patterns.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django admin — useful for direct DB inspection during development
    path("admin/", admin.site.urls),

    # Main dashboard app (all user-facing pages)
    path("", include("dashboard.urls")),
]

# Serve uploaded media files during development
# In production, this is handled by nginx/Apache.
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
