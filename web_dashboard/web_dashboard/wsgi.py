"""
web_dashboard/web_dashboard/wsgi.py
======================================
WSGI entry point for the Django application.

Used by:
  - Django development server: python manage.py runserver
  - Production WSGI servers: gunicorn, uWSGI

In production, point gunicorn to this module:
  gunicorn web_dashboard.wsgi:application
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web_dashboard.settings")

application = get_wsgi_application()
