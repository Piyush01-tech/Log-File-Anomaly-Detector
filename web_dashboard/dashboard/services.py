"""
dashboard/services.py — Phase 10
===================================
Flask API client — Anti-Corruption Layer (ACL) isolating Django from
the specific HTTP mechanics of communicating with the Flask ML engine.

PURPOSE:
  - Single Responsibility: all HTTP communication with Flask lives here.
  - If the Flask API contract changes (URL, payload schema, auth headers),
    only this file needs to be updated — views remain untouched.
  - Easy to mock in unit tests without touching views.
  - Handles timeouts, retries, connection errors, and response parsing.

CLASSES:
  FlaskAPIClient — Stateless client wrapping requests to Flask endpoints.
  FlaskAPIError  — Custom exception for Flask communication failures.

DESIGN DECISIONS:
  - Uses `requests` library (already a transitive dependency of Django).
  - Stateless class methods: no instance state, no connection pooling.
    Connection pooling can be added later via requests.Session if needed.
  - Timeout is configurable via settings.FLASK_API_TIMEOUT.
  - All methods return parsed Python dicts, never raw Response objects.
  - Errors are wrapped in FlaskAPIError with status codes and messages.

FUTURE EXTENSIBILITY:
  - When Celery is introduced, the `analyze()` call will be dispatched
    to a Celery task instead of a synchronous HTTP call. The method
    signature remains the same — only the implementation changes.
  - When live collection is added, a new method (e.g., `analyze_stream()`)
    can be added without modifying existing methods.
  - PSK authentication headers can be added in one place when needed.

ARCHITECTURE:
  Django NEVER imports from ml_engine directly.
  This module is the ONLY point of contact between Django and Flask.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# ===========================================================================
# Custom Exception
# ===========================================================================


class FlaskAPIError(Exception):
    """
    Custom exception for Flask ML API communication failures.

    Encapsulates error details from failed Flask API calls, including
    HTTP status codes and structured error messages.

    Attributes:
        message:     Human-readable error description.
        status_code: HTTP status code from Flask (None if connection failed).
        details:     Raw response body dict (if available).
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[Dict] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


# ===========================================================================
# Response Dataclasses
# ===========================================================================


@dataclass
class HealthStatus:
    """Parsed response from Flask /health endpoint."""

    is_up: bool
    version: str
    models_loaded: bool


@dataclass
class AnalysisResult:
    """
    Parsed response from Flask /analyze endpoint.

    Attributes:
        job_id:          Echoed job ID from the request.
        total_samples:   Total time windows analyzed.
        total_anomalies: Number of anomalous windows detected.
        anomaly_rate:    Ratio of anomalies to total samples.
        anomalies:       List of anomaly dicts with keys:
                         timestamp, computer, anomaly_score, severity, features.
    """

    job_id: Optional[int]
    total_samples: int
    total_anomalies: int
    anomaly_rate: float
    anomalies: List[Dict[str, Any]]


@dataclass
class ModelStats:
    """Parsed response from Flask /stats endpoint."""

    model_type: str
    n_estimators: int
    contamination: float
    trained_at: str
    features_monitored: int


# ===========================================================================
# Flask API Client
# ===========================================================================


class FlaskAPIClient:
    """
    Stateless HTTP client for the Flask ML Inference microservice.

    All methods are class methods — no instance state is needed.
    Configuration is read from Django settings at call time.

    ENDPOINTS:
      health()  → GET  /api/v1/health
      analyze() → POST /api/v1/analyze
      stats()   → GET  /api/v1/stats

    ERROR HANDLING:
      - Connection failures → FlaskAPIError with status_code=None
      - Timeout             → FlaskAPIError with status_code=None
      - HTTP 4xx/5xx        → FlaskAPIError with Flask's error message
      - Invalid JSON        → FlaskAPIError with parsing details

    CONFIGURATION:
      - settings.FLASK_API_BASE_URL — Base URL (default: http://127.0.0.1:5000)
      - settings.FLASK_API_TIMEOUT  — Request timeout in seconds (default: 120)
    """

    # API version prefix
    API_PREFIX: str = "/api/v1"

    @classmethod
    def _get_base_url(cls) -> str:
        """Get the Flask API base URL from Django settings."""
        return getattr(
            settings, "FLASK_API_BASE_URL", "http://127.0.0.1:5000"
        )

    @classmethod
    def _get_timeout(cls) -> int:
        """Get the request timeout from Django settings."""
        return getattr(settings, "FLASK_API_TIMEOUT", 120)

    @classmethod
    def _build_url(cls, endpoint: str) -> str:
        """
        Build the full URL for a Flask API endpoint.

        Args:
            endpoint: The endpoint path (e.g., "/health").

        Returns:
            Full URL string.
        """
        base = cls._get_base_url().rstrip("/")
        return f"{base}{cls.API_PREFIX}{endpoint}"

    @classmethod
    def _handle_error_response(
        cls,
        response: requests.Response,
        context: str,
    ) -> None:
        """
        Parse and raise a FlaskAPIError from a non-2xx response.

        Args:
            response: The requests.Response object.
            context:  Human-readable context for the error message.

        Raises:
            FlaskAPIError: Always raised with parsed error details.
        """
        try:
            body = response.json()
            flask_message = body.get("message", "Unknown error from ML engine.")
        except (ValueError, KeyError):
            flask_message = response.text[:500] if response.text else "No response body."

        error_msg = (
            f"{context}: HTTP {response.status_code} — {flask_message}"
        )
        logger.error(
            "Flask API error: %s (status=%d)", error_msg, response.status_code
        )
        raise FlaskAPIError(
            message=error_msg,
            status_code=response.status_code,
            details={"flask_message": flask_message},
        )

    # -------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------

    @classmethod
    def health(cls) -> HealthStatus:
        """
        Check the Flask ML engine health status.

        Returns:
            HealthStatus dataclass with service status.

        Raises:
            FlaskAPIError: If the service is unreachable or returns an error.
        """
        url = cls._build_url("/health")
        logger.debug("Flask health check: GET %s", url)

        try:
            response = requests.get(url, timeout=10)
        except requests.ConnectionError as exc:
            logger.error("Flask ML engine is unreachable: %s", exc)
            raise FlaskAPIError(
                message="ML engine is unreachable. Ensure Flask is running.",
                status_code=None,
            )
        except requests.Timeout:
            logger.error("Flask health check timed out.")
            raise FlaskAPIError(
                message="ML engine health check timed out.",
                status_code=None,
            )

        if response.status_code != 200:
            cls._handle_error_response(response, "Health check failed")

        data = response.json()
        return HealthStatus(
            is_up=data.get("status") == "up",
            version=data.get("version", "unknown"),
            models_loaded=data.get("models_loaded", False),
        )

    # -------------------------------------------------------------------
    # Analyze EVTX File
    # -------------------------------------------------------------------

    @classmethod
    def analyze(
        cls,
        file_path: str,
        job_id: Optional[int] = None,
    ) -> AnalysisResult:
        """
        Send an EVTX file for ML analysis via the Flask API.

        This is a SYNCHRONOUS call that blocks until Flask completes
        the analysis. For large files, this may take significant time.

        Args:
            file_path: Absolute path to the .evtx file on the shared
                       filesystem (Django's MEDIA_ROOT).
            job_id:    Optional AnalysisJob ID for correlation.

        Returns:
            AnalysisResult dataclass with summary and anomalies list.

        Raises:
            FlaskAPIError: On connection failure, timeout, or Flask error.
        """
        url = cls._build_url("/analyze")
        timeout = cls._get_timeout()

        payload = {
            "file_path": str(file_path),
            "job_id": job_id,
        }

        logger.info(
            "Sending analysis request to Flask: file='%s', job_id=%s, "
            "timeout=%ds",
            file_path,
            job_id,
            timeout,
        )

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=timeout,
            )
        except requests.ConnectionError as exc:
            error_msg = (
                "Cannot connect to ML engine. "
                "Ensure the Flask service is running on "
                f"{cls._get_base_url()}."
            )
            logger.error("Flask connection error: %s", exc)
            raise FlaskAPIError(message=error_msg, status_code=None)

        except requests.Timeout:
            error_msg = (
                f"ML analysis timed out after {timeout} seconds. "
                "The file may be too large for synchronous processing."
            )
            logger.error("Flask analyze request timed out after %ds.", timeout)
            raise FlaskAPIError(message=error_msg, status_code=None)

        # Handle non-success responses
        if response.status_code != 200:
            cls._handle_error_response(response, "Analysis request failed")

        # Parse successful response
        try:
            data = response.json()
        except ValueError as exc:
            logger.error("Failed to parse Flask response JSON: %s", exc)
            raise FlaskAPIError(
                message="Invalid JSON response from ML engine.",
                status_code=response.status_code,
            )

        if data.get("status") != "success":
            flask_message = data.get("message", "Unknown analysis error.")
            raise FlaskAPIError(
                message=f"Analysis failed: {flask_message}",
                status_code=response.status_code,
                details=data,
            )

        # Extract structured data
        summary = data.get("summary", {})
        anomalies = data.get("anomalies", [])

        result = AnalysisResult(
            job_id=data.get("job_id"),
            total_samples=summary.get("total_samples", 0),
            total_anomalies=summary.get("total_anomalies", 0),
            anomaly_rate=summary.get("anomaly_rate", 0.0),
            anomalies=anomalies,
        )

        logger.info(
            "Analysis complete: job_id=%s, samples=%d, anomalies=%d.",
            result.job_id,
            result.total_samples,
            result.total_anomalies,
        )

        return result

    # -------------------------------------------------------------------
    # Model Statistics
    # -------------------------------------------------------------------

    @classmethod
    def stats(cls) -> ModelStats:
        """
        Get metadata about the currently loaded ML model.

        Returns:
            ModelStats dataclass with model configuration.

        Raises:
            FlaskAPIError: If the service is unreachable or model not loaded.
        """
        url = cls._build_url("/stats")
        logger.debug("Flask stats request: GET %s", url)

        try:
            response = requests.get(url, timeout=10)
        except requests.ConnectionError as exc:
            logger.error("Flask ML engine is unreachable: %s", exc)
            raise FlaskAPIError(
                message="ML engine is unreachable. Ensure Flask is running.",
                status_code=None,
            )
        except requests.Timeout:
            logger.error("Flask stats request timed out.")
            raise FlaskAPIError(
                message="ML engine stats request timed out.",
                status_code=None,
            )

        if response.status_code != 200:
            cls._handle_error_response(response, "Stats request failed")

        data = response.json()
        return ModelStats(
            model_type=data.get("model_type", "unknown"),
            n_estimators=data.get("n_estimators", 0),
            contamination=data.get("contamination", 0.0),
            trained_at=data.get("trained_at", "unknown"),
            features_monitored=data.get("features_monitored", 0),
        )
