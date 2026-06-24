"""
dashboard/services.py  [PLACEHOLDER — Phase 8]
================================================
Flask API client — handles all HTTP communication from
Django to the Flask ML inference microservice.

WHY THIS EXISTS:
  - Isolates HTTP call logic from views (single responsibility).
  - One place to handle timeouts, retries, and auth headers.
  - Easy to mock in unit tests without touching views.

Phase 8 will implement:
  - FlaskAPIClient.analyze(features: dict) -> dict
  - FlaskAPIClient.health() -> bool
  - FlaskAPIClient.stats() -> dict
"""

# Phase 8 will implement the full FlaskAPIClient class
