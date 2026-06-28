"""
dashboard/apps.py — Phase 9B
==============================
Django application configuration for the dashboard app.

WHY THIS EXISTS:
  - Required for Django to discover the app and its models.
  - Sets the default primary key field type for all models.
  - Provides a human-readable verbose name for the admin interface.
  - Critical for AUTH_USER_MODEL resolution — Django needs the
    AppConfig to locate our custom User model.
  - Registers signals in ready() for RBAC user-group sync (Phase 9B).
"""

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """
    Application configuration for the SOC Dashboard.

    Attributes:
        default_auto_field: BigAutoField for future-proof primary keys.
        name:              Python import path for the app.
        verbose_name:      Human-readable name shown in Django admin.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "dashboard"
    verbose_name = "SOC Dashboard"

    def ready(self):
        """
        Import signals when the app is ready.

        This ensures the post_save signal for User-Group sync
        (Phase 9B) is connected at Django startup. The import
        triggers the @receiver decorator registration.
        """
        import dashboard.signals  # noqa: F401
