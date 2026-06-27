"""
ml_engine/train.py
===================
Phase 5 — Model Training Module.

PURPOSE:
  Trains an Isolation Forest anomaly detection model on the feature
  matrix produced by Phase 4, then persists the model, scaler, and
  training metadata to disk using joblib.

ARCHITECTURE:
  TrainingConfig       — Immutable dataclass holding hyperparameters,
                         paths, and feature column names.
  FeatureScaler        — Wraps sklearn StandardScaler with fit/transform
                         and joblib persistence.  Reusable by Phase 6.
  AnomalyModelTrainer  — Orchestrator.  Loads features, validates,
                         delegates scaling, trains the model, persists
                         all artifacts, and logs training metrics.

WHY THREE CLASSES:
  - Config is a data object: overridable per-environment or per-test.
  - Scaler is separate: Phase 6 (predict.py) must load the SAME scaler
    without importing the trainer.  This keeps training ↔ prediction
    fully decoupled.
  - Trainer is the orchestrator: owns the workflow, delegates maths.

KEY DESIGN DECISIONS:
  - StandardScaler before Isolation Forest: ensures comparable feature
    ranges across count (0–27) and ratio (0–0.5) features.
  - joblib for persistence: sklearn-recommended, optimised for numpy
    arrays, already in requirements.txt.
  - training_metadata.json: audit trail for SOC compliance — records
    timestamp, hyperparams, dataset stats, and artifact checksums.
  - AnomalyModelTrainer has NO predict() method.  Training and
    prediction are STRUCTURALLY separated, not just by convention.

INPUT:
  data/processed/features.csv        (Phase 4 output)

OUTPUT:
  ml_engine/models/isolation_model.joblib
  ml_engine/models/scaler.joblib
  ml_engine/models/training_metadata.json

USAGE (as a module):
  from ml_engine.train import AnomalyModelTrainer
  trainer = AnomalyModelTrainer()
  trainer.run()

USAGE (as a script):
  python -m ml_engine.train
"""

import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from .config import Config
from .logger import get_logger
from .scaler import FeatureScaler

logger = get_logger(__name__)


# ===========================================================================
# TrainingConfig
# ===========================================================================


@dataclass(frozen=True)
class TrainingConfig:
    """
    Immutable configuration for the model training pipeline.

    WHY A DATACLASS:
      - Keeps all hyperparameters and paths in one inspectable object.
      - ``frozen=True`` prevents accidental mutation at runtime.
      - Can be overridden in unit tests without monkey-patching globals.

    Attributes:
        n_estimators:       Number of trees in the Isolation Forest.
        contamination:      Expected proportion of anomalies in training data.
        random_state:       Seed for reproducibility.
        feature_columns:    Ordered list of numeric feature column names
                            (must match Phase 4 output).
        non_feature_cols:   Columns present in features.csv that are NOT
                            numeric features (will be dropped before training).
        features_path:      Path to the input features.csv file.
        model_path:         Path to save the trained Isolation Forest.
        scaler_path:        Path to save the fitted StandardScaler.
        metadata_path:      Path to save the training metadata JSON.
    """

    # Isolation Forest hyperparameters
    n_estimators: int = Config.IF_N_ESTIMATORS
    contamination: float = Config.IF_CONTAMINATION
    random_state: int = Config.IF_RANDOM_STATE

    # Feature columns from Phase 4
    feature_columns: List[str] = field(
        default_factory=lambda: list(Config.FEATURE_COLUMNS)
    )

    # Non-feature columns to drop before training
    non_feature_cols: List[str] = field(
        default_factory=lambda: ["hour", "computer"]
    )

    # File paths
    features_path: Path = field(
        default_factory=lambda: Config.PROCESSED_DIR / Config.FEATURES_FILENAME
    )
    model_path: Path = field(default_factory=lambda: Config.MODEL_PATH)
    scaler_path: Path = field(default_factory=lambda: Config.SCALER_PATH)
    metadata_path: Path = field(
        default_factory=lambda: Config.MODELS_DIR / "training_metadata.json"
    )


# NOTE: FeatureScaler has been extracted to ml_engine/scaler.py (Phase 7A).
# It is imported above via 'from .scaler import FeatureScaler'.
# Both train.py and predict.py import from scaler.py independently.


# ===========================================================================
# AnomalyModelTrainer
# ===========================================================================


class AnomalyModelTrainer:
    """
    Orchestrator for the Isolation Forest training pipeline.

    Responsibilities:
      - Load features.csv from disk
      - Validate the feature schema against Phase 4 expectations
      - Delegate feature scaling to FeatureScaler
      - Train the Isolation Forest model
      - Persist model, scaler, and metadata to disk via joblib
      - Log comprehensive training metrics for observability

    This class has NO predict() method.  Training and prediction
    are STRUCTURALLY separated — not just by convention.

    Args:
        config: TrainingConfig instance (injectable for testing).
        scaler: FeatureScaler instance (injectable for testing).
    """

    def __init__(
        self,
        config: Optional[TrainingConfig] = None,
        scaler: Optional[FeatureScaler] = None,
    ) -> None:
        self._config = config or TrainingConfig()
        self._scaler = scaler or FeatureScaler(self._config.feature_columns)
        self._model: Optional[IsolationForest] = None
        self._training_metadata: Dict = {}

    @property
    def model(self) -> Optional[IsolationForest]:
        """The trained Isolation Forest model, or None if not yet trained."""
        return self._model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> IsolationForest:
        """
        Execute the full training pipeline.

        Workflow:
          1. Load features.csv
          2. Validate input schema
          3. Extract numeric feature matrix
          4. Fit StandardScaler + transform
          5. Train Isolation Forest
          6. Compute training-time scores for diagnostics
          7. Persist model, scaler, and metadata
          8. Log comprehensive summary

        Returns:
            The trained IsolationForest model instance.

        Raises:
            FileNotFoundError: If features.csv does not exist.
            ValueError:        If input schema validation fails.
        """
        logger.info("=" * 60)
        logger.info("PHASE 5 — Model Training Pipeline")
        logger.info("=" * 60)
        logger.info(f"Input     : {self._config.features_path}")
        logger.info(f"Model out : {self._config.model_path}")
        logger.info(f"Scaler out: {self._config.scaler_path}")
        logger.info(
            f"Hyperparams: n_estimators={self._config.n_estimators}, "
            f"contamination={self._config.contamination}, "
            f"random_state={self._config.random_state}"
        )

        # Step 1: Load
        features_df = self._load_features()

        # Step 2: Validate
        self._validate_features(features_df)

        # Step 3: Extract numeric matrix
        numeric_df = self._extract_numeric_features(features_df)

        # Step 4: Scale
        scaled_data = self._scaler.fit_transform(numeric_df)

        # Step 5: Train
        self._train_model(scaled_data)

        # Step 6: Compute training-time diagnostics
        train_scores = self._compute_training_scores(scaled_data)

        # Step 7: Persist everything
        self._save_model()
        self._scaler.save(self._config.scaler_path)
        self._save_metadata(features_df, train_scores)

        # Step 8: Log summary
        self._log_training_summary(features_df, train_scores)

        logger.info("=" * 60)
        logger.info("PHASE 5 COMPLETE")
        logger.info("=" * 60)

        return self._model

    # ------------------------------------------------------------------
    # Private helpers — Load & Validate
    # ------------------------------------------------------------------

    def _load_features(self) -> pd.DataFrame:
        """
        Load features.csv from disk.

        Returns:
            DataFrame with feature matrix rows.

        Raises:
            FileNotFoundError: If the features file does not exist.
        """
        path = self._config.features_path

        if not path.exists():
            raise FileNotFoundError(
                f"Features file not found: {path}\n"
                f"Run Phase 4 first:  python ml_engine/feature_engineering.py"
            )

        logger.info(f"Loading features from: {path}")
        df = pd.read_csv(path, encoding="utf-8")
        logger.info(f"Loaded {len(df):,} feature rows")

        return df

    def _validate_features(self, df: pd.DataFrame) -> None:
        """
        Validate that features.csv has the expected schema.

        Checks:
          - All expected feature columns are present
          - No NaN values in feature columns
          - Minimum row count for meaningful training

        Args:
            df: The loaded features DataFrame.

        Raises:
            ValueError: If validation fails.
        """
        # Check required columns
        required = set(self._config.feature_columns)
        present = set(df.columns)
        missing = required - present

        if missing:
            raise ValueError(
                f"Features file is missing required columns: {sorted(missing)}. "
                f"Expected: {self._config.feature_columns}. "
                f"Got: {sorted(df.columns.tolist())}"
            )

        # Check for NaN in feature columns
        feature_df = df[self._config.feature_columns]
        nan_counts = feature_df.isna().sum()
        nan_cols = nan_counts[nan_counts > 0]
        if not nan_cols.empty:
            logger.warning(
                f"NaN values found in feature columns:\n{nan_cols.to_string()}"
            )
            logger.warning(
                "NaN rows will be dropped before training. "
                "This may indicate a Phase 4 data quality issue."
            )

        # Minimum row count
        min_rows = 10
        if len(df) < min_rows:
            raise ValueError(
                f"Insufficient training data: {len(df)} rows. "
                f"Minimum required: {min_rows}. "
                f"Add more EVTX files to data/raw_logs/ and re-run Phases 3-4."
            )

        logger.info("Feature validation passed:")
        logger.info(f"  Rows            : {len(df):,}")
        logger.info(f"  Feature columns : {len(self._config.feature_columns)}")
        logger.info(f"  NaN total       : {feature_df.isna().sum().sum()}")

    def _extract_numeric_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract only the numeric feature columns for model training.

        Drops non-feature columns (hour, computer) that are present
        for attribution but are not model inputs.

        Args:
            df: Full features DataFrame.

        Returns:
            DataFrame with only the 15 numeric feature columns.
        """
        numeric_df = df[self._config.feature_columns].copy()

        # Drop any rows with NaN (should be 0, but safety first)
        initial_rows = len(numeric_df)
        numeric_df = numeric_df.dropna()
        dropped = initial_rows - len(numeric_df)

        if dropped > 0:
            logger.warning(
                f"Dropped {dropped} rows with NaN values before training."
            )

        logger.info(
            f"Numeric feature matrix: {numeric_df.shape[0]} rows "
            f"× {numeric_df.shape[1]} features"
        )

        return numeric_df

    # ------------------------------------------------------------------
    # Private helpers — Training
    # ------------------------------------------------------------------

    def _train_model(self, scaled_data: np.ndarray) -> None:
        """
        Train the Isolation Forest model on scaled feature data.

        Args:
            scaled_data: Scaled numpy array from FeatureScaler.
        """
        logger.info(
            f"Training Isolation Forest "
            f"(n_estimators={self._config.n_estimators}, "
            f"contamination={self._config.contamination})..."
        )

        self._model = IsolationForest(
            n_estimators=self._config.n_estimators,
            contamination=self._config.contamination,
            random_state=self._config.random_state,
            n_jobs=-1,          # Use all CPU cores
            verbose=0,
        )

        self._model.fit(scaled_data)
        logger.info("Isolation Forest training complete.")

    def _compute_training_scores(self, scaled_data: np.ndarray) -> Dict:
        """
        Compute anomaly scores on the training data itself.

        These scores are for DIAGNOSTICS ONLY — they help verify that
        the model learned meaningful patterns and that the contamination
        parameter is reasonable.

        Args:
            scaled_data: The same scaled data used for training.

        Returns:
            Dict with score statistics and anomaly counts.
        """
        logger.info("Computing training-time anomaly scores...")

        # decision_function: higher = more normal, lower = more anomalous
        raw_scores = self._model.decision_function(scaled_data)

        # predict: 1 = normal, -1 = anomaly
        predictions = self._model.predict(scaled_data)

        n_anomalies = int((predictions == -1).sum())
        n_normal = int((predictions == 1).sum())
        anomaly_rate = n_anomalies / len(predictions) if len(predictions) > 0 else 0.0

        scores_info = {
            "n_samples": int(len(predictions)),
            "n_anomalies": n_anomalies,
            "n_normal": n_normal,
            "anomaly_rate": round(anomaly_rate, 4),
            "score_min": round(float(raw_scores.min()), 6),
            "score_max": round(float(raw_scores.max()), 6),
            "score_mean": round(float(raw_scores.mean()), 6),
            "score_std": round(float(raw_scores.std()), 6),
            "score_median": round(float(np.median(raw_scores)), 6),
        }

        return scores_info

    # ------------------------------------------------------------------
    # Private helpers — Persistence
    # ------------------------------------------------------------------

    def _save_model(self) -> None:
        """
        Persist the trained Isolation Forest model to disk using joblib.

        Raises:
            RuntimeError: If the model has not been trained.
        """
        if self._model is None:
            raise RuntimeError("Cannot save — model has not been trained.")

        path = self._config.model_path
        path.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump(self._model, path)

        file_size = path.stat().st_size
        logger.info(f"Model saved to: {path}")
        logger.info(f"  File size: {file_size:,} bytes")

    def _save_metadata(
        self, features_df: pd.DataFrame, train_scores: Dict
    ) -> None:
        """
        Save training metadata as a JSON file for audit and observability.

        The metadata includes:
          - Training timestamp
          - Hyperparameters
          - Feature column list
          - Dataset statistics
          - Training-time anomaly score distribution
          - Artifact file checksums (SHA-256)

        Args:
            features_df: The original features DataFrame.
            train_scores: Score statistics from training diagnostics.
        """
        metadata = {
            "training_timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "Phase 5 — Model Training",
            "hyperparameters": {
                "algorithm": "IsolationForest",
                "n_estimators": self._config.n_estimators,
                "contamination": self._config.contamination,
                "random_state": self._config.random_state,
                "n_jobs": -1,
            },
            "feature_columns": self._config.feature_columns,
            "dataset": {
                "source_file": str(self._config.features_path),
                "total_rows": len(features_df),
                "n_features": len(self._config.feature_columns),
            },
            "training_scores": train_scores,
            "artifacts": {
                "model_file": str(self._config.model_path),
                "model_sha256": self._compute_file_hash(self._config.model_path),
                "model_size_bytes": self._config.model_path.stat().st_size,
                "scaler_file": str(self._config.scaler_path),
                "scaler_sha256": self._compute_file_hash(self._config.scaler_path),
                "scaler_size_bytes": self._config.scaler_path.stat().st_size,
            },
        }

        # Add per-feature dataset statistics
        feature_stats = {}
        for col in self._config.feature_columns:
            if col in features_df.columns:
                series = features_df[col]
                feature_stats[col] = {
                    "min": round(float(series.min()), 6),
                    "max": round(float(series.max()), 6),
                    "mean": round(float(series.mean()), 6),
                    "std": round(float(series.std()), 6),
                }
        metadata["dataset"]["feature_statistics"] = feature_stats

        # Write JSON
        path = self._config.metadata_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, default=str)

        logger.info(f"Training metadata saved to: {path}")

    @staticmethod
    def _compute_file_hash(file_path: Path) -> str:
        """
        Compute SHA-256 hash of a file for integrity verification.

        Args:
            file_path: Path to the file.

        Returns:
            Hex-encoded SHA-256 hash string.
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    # ------------------------------------------------------------------
    # Private helpers — Logging
    # ------------------------------------------------------------------

    def _log_training_summary(
        self, features_df: pd.DataFrame, train_scores: Dict
    ) -> None:
        """
        Log a comprehensive human-readable training summary.

        Args:
            features_df: The original features DataFrame.
            train_scores: Score statistics from training diagnostics.
        """
        logger.info("")
        logger.info("--- Training Summary ---")
        logger.info(f"  Algorithm        : Isolation Forest")
        logger.info(f"  n_estimators     : {self._config.n_estimators}")
        logger.info(f"  contamination    : {self._config.contamination}")
        logger.info(f"  random_state     : {self._config.random_state}")
        logger.info(f"  Training samples : {train_scores['n_samples']:,}")
        logger.info(f"  Features         : {len(self._config.feature_columns)}")

        logger.info("")
        logger.info("--- Training-Time Anomaly Detection ---")
        logger.info(
            f"  Anomalies detected : {train_scores['n_anomalies']} "
            f"({train_scores['anomaly_rate'] * 100:.1f}%)"
        )
        logger.info(
            f"  Normal samples     : {train_scores['n_normal']} "
            f"({(1 - train_scores['anomaly_rate']) * 100:.1f}%)"
        )

        logger.info("")
        logger.info("--- Decision Function Scores ---")
        logger.info(f"  Min    : {train_scores['score_min']:.6f}")
        logger.info(f"  Max    : {train_scores['score_max']:.6f}")
        logger.info(f"  Mean   : {train_scores['score_mean']:.6f}")
        logger.info(f"  Std    : {train_scores['score_std']:.6f}")
        logger.info(f"  Median : {train_scores['score_median']:.6f}")

        logger.info("")
        logger.info("--- Persisted Artifacts ---")
        logger.info(
            f"  Model  : {self._config.model_path} "
            f"({self._config.model_path.stat().st_size:,} bytes)"
        )
        logger.info(
            f"  Scaler : {self._config.scaler_path} "
            f"({self._config.scaler_path.stat().st_size:,} bytes)"
        )
        logger.info(f"  Metadata: {self._config.metadata_path}")


# ===========================================================================
# Standalone Script Entry Point
# ===========================================================================


def main() -> None:
    """
    Run the model training pipeline as a standalone script.

    Usage:
        python ml_engine/train.py

    Prerequisites:
        - Phase 4 must have been executed (features.csv must exist)
        - Or run with synthetic data:
            python -m ml_engine.feature_engineering --synthetic
            python -m ml_engine.train

    Output:
        ml_engine/models/isolation_model.joblib
        ml_engine/models/scaler.joblib
        ml_engine/models/training_metadata.json
    """
    Config.ensure_directories()

    logger.info("Model Training — Phase 5")
    logger.info(f"Features input : {Config.PROCESSED_DIR / Config.FEATURES_FILENAME}")
    logger.info(f"Model output   : {Config.MODEL_PATH}")

    trainer = AnomalyModelTrainer()

    try:
        model = trainer.run()
    except FileNotFoundError as exc:
        logger.error(f"Training failed — missing input: {exc}")
        sys.exit(1)
    except ValueError as exc:
        logger.error(f"Training failed — validation error: {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Training failed — unexpected error: {exc}", exc_info=True)
        sys.exit(1)

    # Quick verification: load the model back and check it
    logger.info("")
    logger.info("--- Post-Training Verification ---")
    try:
        loaded_model = joblib.load(Config.MODEL_PATH)
        params = loaded_model.get_params()
        logger.info(f"  Model loaded successfully from: {Config.MODEL_PATH}")
        logger.info(f"  n_estimators  : {params['n_estimators']}")
        logger.info(f"  contamination : {params['contamination']}")
        logger.info(f"  random_state  : {params['random_state']}")

        loaded_scaler = FeatureScaler.load(Config.SCALER_PATH)
        logger.info(f"  Scaler loaded successfully from: {Config.SCALER_PATH}")
        logger.info(f"  Scaler features: {loaded_scaler.feature_columns}")

        logger.info("  ✓ All artifacts verified — ready for Phase 6 (Prediction)")
    except Exception as exc:
        logger.error(
            f"  ✗ Post-training verification failed: {exc}", exc_info=True
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
