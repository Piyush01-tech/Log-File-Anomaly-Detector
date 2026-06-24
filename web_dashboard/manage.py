#!/usr/bin/env python
"""
web_dashboard/manage.py
========================
Django's command-line utility for administrative tasks.

Common commands:
  python manage.py runserver          — Start dev server on :8000
  python manage.py migrate            — Apply DB migrations
  python manage.py createsuperuser    — Create admin account
  python manage.py makemigrations     — Generate migration files
  python manage.py collectstatic      — Gather static files for production
"""

import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web_dashboard.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
