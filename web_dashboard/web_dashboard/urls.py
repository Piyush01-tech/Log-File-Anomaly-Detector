"""
web_dashboard/web_dashboard/urls.py — Phase 9A
=================================================
Root URL dispatcher for the Django frontend service.

ROUTES:
  /          → dashboard app (home, alerts, upload, history)
  /admin/    → Django built-in admin panel
  /auth/     → Authentication (login, logout, register, profile)

URL NAMESPACES:
  dashboard  → Dashboard feature routes (dashboard/urls.py)
  auth       → Authentication routes (dashboard/auth_urls.py)
  admin      → Django admin
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django admin — useful for direct DB inspection during development
    path("admin/", admin.site.urls),

    # Authentication routes (Phase 9A)
    path("auth/", include("dashboard.auth_urls")),

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
