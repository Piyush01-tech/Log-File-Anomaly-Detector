"""
ml_engine/config.py
====================
Centralized configuration for the ML Engine microservice.

WHY THIS EXISTS:
  - Avoids hardcoded paths and magic numbers scattered across modules.
  - A single file to change when deploying to different environments.
  - Reads from environment variables with sensible defaults (12-factor app).

USAGE:
  from config import Config
  model_path = Config.MODEL_PATH
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from ml_engine/)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


class Config:
    """
    Static configuration container for the ML Engine.

    All path attributes return absolute Path objects so callers
    never need to worry about relative-path resolution.
    """

    # ------------------------------------------------------------------
    # Directory Paths
    # ------------------------------------------------------------------

    # Root of the entire project
    PROJECT_ROOT: Path = _ROOT

    # Root of this microservice
    ML_ENGINE_DIR: Path = Path(__file__).resolve().parent

    # Where trained model artifacts are persisted
    MODELS_DIR: Path = ML_ENGINE_DIR / "models"

    # Raw .evtx uploads
    RAW_LOGS_DIR: Path = PROJECT_ROOT / "data" / "raw_logs"

    # Parsed and feature-engineered CSVs
    PROCESSED_DIR: Path = PROJECT_ROOT / "data" / "processed"

    # ------------------------------------------------------------------
    # Model File Names
    # ------------------------------------------------------------------

    MODEL_FILENAME: str = "isolation_model.joblib"
    SCALER_FILENAME: str = "scaler.joblib"

    MODEL_PATH: Path = MODELS_DIR / MODEL_FILENAME
    SCALER_PATH: Path = MODELS_DIR / SCALER_FILENAME

    # ------------------------------------------------------------------
    # Flask Server
    # ------------------------------------------------------------------

    FLASK_HOST: str = os.getenv("FLASK_HOST", "127.0.0.1")
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", 5000))
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "False").lower() == "true"

    # ------------------------------------------------------------------
    # Isolation Forest Hyperparameters
    # ------------------------------------------------------------------

    # Proportion of data expected to be anomalous.
    # 0.05 means we expect ~5% anomaly rate in training data.
    IF_CONTAMINATION: float = float(os.getenv("IF_CONTAMINATION", 0.05))

    # Number of estimators (trees). Higher = more stable, slower.
    IF_N_ESTIMATORS: int = int(os.getenv("IF_N_ESTIMATORS", 200))

    # Reproducibility seed
    IF_RANDOM_STATE: int = 42

    # ------------------------------------------------------------------
    # Feature Engineering
    # ------------------------------------------------------------------

    # Event IDs we care about — sourced from the project specification
    MONITORED_EVENT_IDS: list = [
        4624,   # Successful login
        4625,   # Failed login
        4672,   # Admin privilege assigned
        4688,   # Process creation
        4697,   # Service installed
        4720,   # User created
        4728,   # Group membership changed
        7045,   # Suspicious service creation
        1102,   # Audit log cleared
    ]

    # Standard filenames for inter-phase data exchange
    PARSED_EVENTS_FILENAME: str = "parsed_events.csv"
    FEATURES_FILENAME: str = "features.csv"

    # Behavioral window frequency for feature aggregation
    # 'h' = hourly windows; can be changed to '30min', '2h', etc.
    FEATURE_WINDOW_FREQ: str = "h"

    # Column names for the feature matrix (must match feature_engineering.py)
    # Phase 4 — 15 features: 12 counts + 3 ratios
    FEATURE_COLUMNS: list = [
        "total_events",
        "failed_logins",
        "successful_logins",
        "admin_events",
        "process_creation_events",
        "new_user_events",
        "service_install_events",
        "group_membership_changes",
        "audit_log_clears",
        "unique_users",
        "unique_processes",
        "unique_ips",
        "failure_rate",
        "admin_ratio",
        "process_ratio",
    ]

    # ------------------------------------------------------------------
    # Anomaly Severity Thresholds
    # ------------------------------------------------------------------
    # Isolation Forest scores range from -1 (most anomalous) to +1 (normal).
    # We map negative scores to human-readable severity levels.

    SEVERITY_CRITICAL_THRESHOLD: float = -0.3
    SEVERITY_HIGH_THRESHOLD: float = -0.1
    SEVERITY_MEDIUM_THRESHOLD: float = 0.0

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

    # ------------------------------------------------------------------
    # Ensure required directories exist at import time
    # ------------------------------------------------------------------

    @classmethod
    def ensure_directories(cls) -> None:
        """Create all required directories if they do not exist."""
        for directory in [
            cls.MODELS_DIR,
            cls.RAW_LOGS_DIR,
            cls.PROCESSED_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)
