"""
ml_engine/app.py — Phase 7B
============================
Flask REST API — the ML Inference microservice entry point.

PURPOSE:
  Provides the HTTP interface between the Django web dashboard and the
  ML engine.  Django communicates with this service exclusively via
  REST calls — it NEVER imports ml_engine modules directly.

ARCHITECTURE:
  - Application Factory Pattern (``create_app()``) for testability
    and WSGI server compatibility (gunicorn, waitress).
  - Blueprint ``api_v1`` under ``/api/v1`` prefix for API versioning.
  - ``AnalysisPipeline`` is initialized ONCE at app startup and stored
    on ``app.config`` — reused across all requests to avoid reloading
    the model and scaler on every call.
  - Custom ``SafeJSONEncoder`` handles numpy types, NaN, Infinity,
    datetime, and Path objects that standard json.dumps() cannot serialize.

ENDPOINTS:
  GET  /api/v1/health   — Liveness probe (model load status, version).
  POST /api/v1/analyze   — Run full ML pipeline on a .evtx file.
  GET  /api/v1/stats     — Model metadata (hyperparameters, training info).

STARTUP:
  flask run --port=5000
  # or
  python -m ml_engine.app

SECURITY:
  This API is designed to run on an internal network, accessible only
  by the Django backend.  No authentication is implemented in this phase.
  Future: Pre-Shared Key (PSK) via Authorization header (see SECURITY_MODEL.md).
"""

import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from flask import Flask, Blueprint, Response, jsonify, request

from .config import Config
from .logger import get_logger
from .pipeline import AnalysisPipeline

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_VERSION: str = "v1"
APP_VERSION: str = "0.3.0"
API_PREFIX: str = f"/api/{API_VERSION}"


# ---------------------------------------------------------------------------
# Custom JSON Encoder
# ---------------------------------------------------------------------------


class SafeJSONEncoder:
    """
    Sanitize Python/numpy objects into JSON-safe primitives.

    WHY THIS EXISTS:
      The ML pipeline produces numpy int64, float64, NaN, and Infinity
      values.  Python's default ``json.dumps()`` raises ``ValueError``
      on NaN/Inf and ``TypeError`` on numpy scalars.  This encoder
      converts them before Flask serialises the response.

    DESIGN DECISION:
      Rather than subclassing ``flask.json.provider.JSONProvider``
      (which couples us to Flask internals), we apply a recursive
      sanitization pass on the response dict.  This is framework-
      agnostic and trivially testable.
    """

    @staticmethod
    def sanitize(obj: Any) -> Any:
        """
        Recursively convert non-JSON-safe types to JSON primitives.

        Handles:
          - numpy integers   → Python int
          - numpy floats     → Python float (NaN/Inf → None)
          - numpy booleans   → Python bool
          - numpy arrays     → Python list
          - datetime         → ISO 8601 string
          - Path             → string
          - dict/list        → recursive descent
          - float NaN/Inf    → None (JSON has no NaN/Inf literal)

        Args:
            obj: Any Python object to sanitize.

        Returns:
            A JSON-serializable equivalent.
        """
        # --- numpy scalars ---
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            val = float(obj)
            if math.isnan(val) or math.isinf(val):
                return None
            return val
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return [SafeJSONEncoder.sanitize(item) for item in obj.tolist()]

        # --- Python floats with NaN/Inf ---
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj

        # --- datetime ---
        if isinstance(obj, datetime):
            return obj.isoformat()

        # --- pathlib.Path ---
        if isinstance(obj, Path):
            return str(obj)

        # --- Recursive containers ---
        if isinstance(obj, dict):
            return {key: SafeJSONEncoder.sanitize(val) for key, val in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [SafeJSONEncoder.sanitize(item) for item in obj]

        # --- Pass-through for str, int, bool, None ---
        return obj


# ---------------------------------------------------------------------------
# Blueprint: api_v1
# ---------------------------------------------------------------------------

api_v1 = Blueprint("api_v1", __name__, url_prefix=API_PREFIX)


@api_v1.route("/health", methods=["GET"])
def health_check() -> tuple[Response, int]:
    """
    Liveness probe — verify the ML engine is operational.

    Returns model load status so orchestrators (Docker, K8s) and the
    Django backend can determine if the service is ready to accept
    analysis requests.

    Returns:
        200 OK with status payload.
    """
    pipeline: Optional[AnalysisPipeline] = (
        api_v1.app_pipeline if hasattr(api_v1, "app_pipeline") else None
    )
    models_loaded = pipeline is not None

    payload = {
        "status": "up",
        "version": APP_VERSION,
        "models_loaded": models_loaded,
    }
    return jsonify(payload), 200


@api_v1.route("/analyze", methods=["POST"])
def analyze_file() -> tuple[Response, int]:
    """
    Run the full ML pipeline on a .evtx file.

    Expects JSON body:
      {
        "file_path": "/absolute/path/to/file.evtx",
        "job_id": 123   (optional — echoed back for Django correlation)
      }

    Response (200 OK):
      {
        "status": "success",
        "job_id": 123,
        "summary": { ... },
        "anomalies": [ ... ]
      }

    Error Responses:
      400 — Missing/invalid request body, file not found, bad extension.
      503 — Model not loaded (training has not been run).
      500 — Internal pipeline error.
    """
    # --- Guard: model must be loaded ---
    pipeline: Optional[AnalysisPipeline] = (
        api_v1.app_pipeline if hasattr(api_v1, "app_pipeline") else None
    )

    if pipeline is None:
        logger.error("Analyze request rejected — model not loaded.")
        return jsonify({
            "status": "error",
            "message": (
                "ML model is not loaded. Training must be run before "
                "analysis requests can be served. "
                "Run: python -m ml_engine.train"
            ),
        }), 503

    # --- Parse request body ---
    if not request.is_json:
        return jsonify({
            "status": "error",
            "message": "Request Content-Type must be application/json.",
        }), 400

    body: Dict = request.get_json(silent=True) or {}

    file_path_str: Optional[str] = body.get("file_path")
    job_id: Optional[int] = body.get("job_id")

    # --- Validate required fields ---
    if not file_path_str:
        return jsonify({
            "status": "error",
            "message": "Missing required field: 'file_path'.",
        }), 400

    file_path = Path(file_path_str)

    # --- Validate file exists ---
    if not file_path.exists():
        logger.warning(f"Analyze request — file not found: {file_path}")
        return jsonify({
            "status": "error",
            "message": f"EVTX file not found at provided path: {file_path_str}",
        }), 400

    # --- Validate file extension ---
    if file_path.suffix.lower() != ".evtx":
        return jsonify({
            "status": "error",
            "message": (
                f"Invalid file type: '{file_path.suffix}'. "
                f"Only .evtx files are supported."
            ),
        }), 400

    # --- Run analysis pipeline ---
    try:
        logger.info(
            f"Analyze request received — file: {file_path.name}, "
            f"job_id: {job_id}"
        )
        result = pipeline.analyze(file_path)

    except ValueError as exc:
        # Raised by parser/feature engineering for empty/invalid data
        logger.warning(f"Analysis validation error: {exc}")
        return jsonify({
            "status": "error",
            "message": str(exc),
        }), 400

    except Exception as exc:
        # Catch-all for unexpected errors (never leak stack traces)
        logger.error(f"Analysis pipeline error: {exc}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Internal server error during analysis. Check ML engine logs.",
        }), 500

    # --- Build response ---
    result_dict = result.to_dict()

    # Filter anomalies: only include rows flagged as anomalies
    anomalies_list = [
        row for row in result_dict.get("predictions", [])
        if row.get("is_anomaly", False)
    ]

    # Format each anomaly to match API_SPECIFICATION.md contract
    formatted_anomalies = []
    for anomaly in anomalies_list:
        formatted = {
            "timestamp": anomaly.get("hour", "unknown"),
            "computer": anomaly.get("computer", "unknown"),
            "anomaly_score": anomaly.get("anomaly_score"),
            "severity": anomaly.get("severity"),
            "features": {
                col: anomaly.get(col)
                for col in Config.FEATURE_COLUMNS
                if col in anomaly
            },
        }
        formatted_anomalies.append(formatted)

    response_payload = {
        "status": "success",
        "job_id": job_id,
        "summary": {
            "total_samples": result_dict["summary"]["total_samples"],
            "total_anomalies": result_dict["summary"]["total_anomalies"],
            "anomaly_rate": result_dict["summary"]["anomaly_rate"],
        },
        "anomalies": formatted_anomalies,
    }

    # Sanitize numpy types and NaN values before JSON serialization
    safe_payload = SafeJSONEncoder.sanitize(response_payload)

    logger.info(
        f"Analyze response — job_id: {job_id}, "
        f"anomalies: {len(formatted_anomalies)}"
    )

    return jsonify(safe_payload), 200


@api_v1.route("/stats", methods=["GET"])
def model_stats() -> tuple[Response, int]:
    """
    Return metadata about the currently loaded Isolation Forest model.

    Provides hyperparameters, training timestamp, and feature count
    for observability and monitoring.

    Returns:
        200 OK with model metadata.
        503 Service Unavailable if model is not loaded.
    """
    pipeline: Optional[AnalysisPipeline] = (
        api_v1.app_pipeline if hasattr(api_v1, "app_pipeline") else None
    )

    if pipeline is None:
        return jsonify({
            "status": "error",
            "message": "ML model is not loaded. Run training first.",
        }), 503

    # Access the predictor's internals for metadata
    predictor = pipeline._predictor
    model = predictor._model

    # Extract model hyperparameters
    model_params = model.get_params() if model else {}

    # Extract training metadata if available
    training_meta = predictor._training_metadata or {}
    trained_at = training_meta.get("training_timestamp", "unknown")

    stats_payload = {
        "model_type": "IsolationForest",
        "n_estimators": model_params.get("n_estimators", "unknown"),
        "contamination": model_params.get("contamination", "unknown"),
        "trained_at": trained_at,
        "features_monitored": len(Config.FEATURE_COLUMNS),
    }

    safe_payload = SafeJSONEncoder.sanitize(stats_payload)

    return jsonify(safe_payload), 200


# ---------------------------------------------------------------------------
# Global Error Handlers
# ---------------------------------------------------------------------------


def _register_error_handlers(app: Flask) -> None:
    """
    Register global error handlers for structured JSON error responses.

    Ensures the API never returns HTML error pages — all errors are
    returned as JSON with a consistent schema:
      {"status": "error", "message": "..."}

    Args:
        app: The Flask application instance.
    """

    @app.errorhandler(404)
    def not_found(error: Exception) -> tuple[Response, int]:
        """Handle requests to undefined routes."""
        return jsonify({
            "status": "error",
            "message": f"Endpoint not found: {request.path}",
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error: Exception) -> tuple[Response, int]:
        """Handle requests with wrong HTTP method."""
        return jsonify({
            "status": "error",
            "message": (
                f"Method {request.method} not allowed for {request.path}. "
                f"Check API documentation."
            ),
        }), 405

    @app.errorhandler(500)
    def internal_server_error(error: Exception) -> tuple[Response, int]:
        """Handle unhandled exceptions — never leak stack traces."""
        logger.error(f"Unhandled server error: {error}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": "Internal server error. Check ML engine logs.",
        }), 500


# ---------------------------------------------------------------------------
# Application Factory
# ---------------------------------------------------------------------------


def create_app() -> Flask:
    """
    Application factory for the Flask ML Inference microservice.

    Creates and configures the Flask application, registers the API
    blueprint, initialises the ``AnalysisPipeline`` (loading model and
    scaler from disk), and registers global error handlers.

    This factory pattern is required for:
      - WSGI deployment (gunicorn, waitress)
      - Clean testing (create fresh app per test)
      - Avoiding circular imports

    Returns:
        A configured Flask application instance.

    Example:
        app = create_app()
        app.run(host="127.0.0.1", port=5000)
    """
    app = Flask(__name__)

    # Load configuration from Config
    app.config["SECRET_KEY"] = os.getenv(
        "FLASK_SECRET_KEY", "dev-secret-change-in-production"
    )

    # --- Initialize ML Pipeline ---
    # The pipeline (and its model/scaler) is loaded ONCE at startup.
    # If loading fails (e.g., model not yet trained), the app still
    # starts — /health will report models_loaded=false and /analyze
    # will return 503.
    pipeline: Optional[AnalysisPipeline] = None

    try:
        logger.info("Initializing AnalysisPipeline...")
        pipeline = AnalysisPipeline()
        logger.info("AnalysisPipeline initialized successfully — models loaded.")
    except FileNotFoundError as exc:
        logger.warning(
            f"ML model artifacts not found: {exc}. "
            f"The /analyze endpoint will return 503 until training is run. "
            f"Run: python -m ml_engine.train"
        )
    except Exception as exc:
        logger.error(
            f"Failed to initialize AnalysisPipeline: {exc}. "
            f"The /analyze endpoint will return 503.",
            exc_info=True,
        )

    # Store pipeline reference on the blueprint for endpoint access
    api_v1.app_pipeline = pipeline

    # --- Register Blueprint ---
    app.register_blueprint(api_v1)

    # --- Register Error Handlers ---
    _register_error_handlers(app)

    logger.info(
        f"Flask ML Engine v{APP_VERSION} ready — "
        f"listening on {Config.FLASK_HOST}:{Config.FLASK_PORT}"
    )

    return app


# ---------------------------------------------------------------------------
# Standalone Entry Point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG,
    )
