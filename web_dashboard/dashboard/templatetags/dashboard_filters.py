"""
dashboard/templatetags/dashboard_filters.py — Phase 11B
==========================================================
Custom template tags and filters for the SOC Dashboard.

TAGS:
  query_transform — Preserves existing GET parameters while updating
                    specific ones (e.g., page number during pagination).

PURPOSE:
  When paginating filtered/searched results, clicking "Next Page" must
  preserve the current search query and filter values. Django's built-in
  pagination doesn't handle this. This tag builds a query string that
  merges existing GET parameters with new ones.

USAGE:
  {% load dashboard_filters %}
  <a href="?{% query_transform page=2 %}">Page 2</a>

  If the current URL is /alerts/?q=test&severity=HIGH&page=1,
  the above renders: <a href="?q=test&severity=HIGH&page=2">Page 2</a>
"""

import logging

from django import template

logger = logging.getLogger(__name__)

register = template.Library()


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """
    Build a query string preserving existing GET parameters.

    Takes the current request's GET parameters, updates them with
    any keyword arguments provided, and returns the resulting
    URL-encoded query string (without the leading '?').

    Args:
        context: Template context (must contain 'request').
        **kwargs: Key-value pairs to update in the query string.

    Returns:
        URL-encoded query string (e.g., 'q=test&severity=HIGH&page=2').

    Example:
        Current URL: /alerts/?q=test&severity=HIGH&page=1
        {% query_transform page=3 %}
        Result: q=test&severity=HIGH&page=3
    """
    request = context.get("request")
    if not request:
        logger.debug("query_transform: No request in context.")
        return ""

    # Copy current GET params (QueryDict is immutable by default)
    query = request.GET.copy()

    # Update with provided kwargs
    for key, value in kwargs.items():
        if value is not None and value != "":
            query[key] = str(value)
        elif key in query:
            del query[key]

    return query.urlencode()
