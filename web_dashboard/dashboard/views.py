"""
dashboard/views.py  [PLACEHOLDER — Phase 8]
=============================================
Django view controllers for dashboard pages.

Pages (implemented in Phase 8):
  - Home dashboard    (summary cards + charts)
  - Alerts table      (paginated anomaly list)
  - Upload logs       (EVTX file upload)
  - Incident history  (search + filter)
  - Authentication    (Phase 11)
"""

from django.shortcuts import render
from django.http import HttpResponse


def health_check(request):
    """Temporary health check view to verify Django is running."""
    return HttpResponse(
        "Django Dashboard is running. Phase 8 will implement full views.",
        content_type="text/plain"
    )
