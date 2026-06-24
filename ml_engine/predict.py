"""
ml_engine/predict.py
=====================
Phase 6 — Prediction Engine.

PURPOSE:
  Loads the trained Isolation Forest model and fitted StandardScaler
  from Phase 5 artifacts, scores new feature vectors, and classifies
  each observation into a SOC-friendly severity level.

ARCHITECTURE:
  PredictionConfig   — Immutable dataclass holding model/scaler paths,
                       severity thresholds, and feature column names.
  PredictionResult   — Structured output dataclass containing per-row
                       predictions, summary statistics, and metadata.
  AnomalyPredictor   — The prediction engine.  Loads model + scaler,
                       validates input, scores features, classifies
                       severity.  Has NO fit() or train() method.

STRUCTURAL SEPARATION FROM TRAINING:
  - AnomalyPredictor has NO fit() and NO train() method.
  - It imports FeatureScaler from train.py ONLY for the .load()
    classmethod — never calls fit_transform().
  - It loads the model via joblib.load() — never instantiates
    IsolationForest directly.
  - This separation is STRUCTURAL, not just by convention.

SEVERITY CLASSIFICATION:
  Isolation Forest decision_function() returns a continuous score.
  We map it to SOC-friendly labels using Config thresholds:
    score <= -0.3   → CRITICAL  (immediate investigation)
    -0.3 < score <= -0.1  → HIGH      (priority review)
    -0.1 < score <=  0.0  → MEDIUM    (scheduled review)
    score >  0.0           → LOW       (monitor)

INPUT:
  ml_engine/models/isolation_model.joblib   (Phase 5 output)
  ml_engine/models/scaler.joblib            (Phase 5 output)
  A DataFrame with 15 feature columns       (from Phase 4 or API)

OUTPUT:
  PredictionResult dataclass containing:
    - predictions_df:  Per-row scores, labels, and severity
    - summary:         Aggregate statistics
    - metadata:        Model info and thresholds used

USAGE (as a module):
  from predict import AnomalyPredictor
  predictor = AnomalyPredictor()
  predictor.load_artifacts()
  result = predictor.predict(features_df)

USAGE (as a script):
  python ml_engine/predict.py
  → Scores data/processed/features.csv and prints results
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path Setup — allows running as both a module and a standalone script
# ---------------------------------------------------------------------------

_ML_ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_ML_ENGINE_DIR))

from config import Config       # noqa: E402
from logger import get_logger   # noqa: E402
from train import FeatureScaler  # noqa: E402  — reuse, never re-fit

logger = get_logger(__name__)


# ===========================================================================
# Severity Enum Constants
# ===========================================================================

# String constants for severity levels — used throughout the prediction
# results and by downstream consumers (Flask API, Django Dashboard).
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"

# Ordered from most to least severe (used for sorting)
SEVERITY_ORDER = [SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW]


# ===========================================================================
# PredictionConfig
# ===========================================================================


@dataclass(frozen=True)
class PredictionConfig:
    """
    Immutable configuration for the prediction engine.

    WHY A DATACLASS:
      - Keeps paths and thresholds in one inspectable, type-hinted object.
      - ``frozen=True`` prevents accidental mutation at runtime.
      - Can be overridden in unit tests without monkey-patching globals.

    Attributes:
        model_path:              Path to the trained Isolation Forest joblib.
        scaler_path:             Path to the fitted StandardScaler joblib.
        metadata_path:           Path to the training metadata JSON.
        feature_columns:         Ordered list of numeric feature column names.
        non_feature_cols:        Columns in features.csv that are NOT model
                                 inputs (preserved for attribution).
        severity_critical:       Decision score threshold for CRITICAL.
        severity_high:           Decision score threshold for HIGH.
        severity_medium:         Decision score threshold for MEDIUM.
    """

    # Artifact paths
    model_path: Path = field(default_factory=lambda: Config.MODEL_PATH)
    scaler_path: Path = field(default_factory=lambda: Config.SCALER_PATH)
    metadata_path: Path = field(
        default_factory=lambda: Config.MODELS_DIR / "training_metadata.json"
    )

    # Feature columns (must match training)
    feature_columns: List[str] = field(
        default_factory=lambda: list(Config.FEATURE_COLUMNS)
    )

    # Non-feature columns to preserve for attribution
    non_feature_cols: List[str] = field(
        default_factory=lambda: ["hour", "computer"]
    )

    # Severity thresholds (from Config)
    severity_critical: float = Config.SEVERITY_CRITICAL_THRESHOLD
    severity_high: float = Config.SEVERITY_HIGH_THRESHOLD
    severity_medium: float = Config.SEVERITY_MEDIUM_THRESHOLD


# ===========================================================================
# PredictionResult
# ===========================================================================


@dataclass
class PredictionResult:
    """
    Structured output from the prediction engine.

    This dataclass encapsulates all prediction outputs in a single
    object, making it easy to pass around and inspect.

    Attributes:
        predictions_df: DataFrame with per-row prediction results.
                        Columns: hour, computer, [15 features],
                        anomaly_score, is_anomaly, severity.
        summary:        Aggregate statistics dict including total
                        samples, anomaly counts, per-severity counts,
                        and score distribution.
        metadata:       Dict with model information, prediction
                        timestamp, and thresholds used.
    """

    predictions_df: pd.DataFrame
    summary: Dict
    metadata: Dict

    def get_anomalies(self, min_severity: str = SEVERITY_LOW) -> pd.DataFrame:
        """
        Filter predictions to return only anomalies at or above
        a given severity level.

        Args:
            min_severity: Minimum severity to include.  One of
                          CRITICAL, HIGH, MEDIUM, LOW.

        Returns:
            Filtered DataFrame sorted by anomaly_score (most
            anomalous first).

        Raises:
            ValueError: If min_severity is not a valid level.
        """
        if min_severity not in SEVERITY_ORDER:
            raise ValueError(
                f"Invalid severity level: '{min_severity}'. "
                f"Must be one of: {SEVERITY_ORDER}"
            )

        # Include this level and all levels more severe
        cutoff_index = SEVERITY_ORDER.index(min_severity)
        included_levels = SEVERITY_ORDER[: cutoff_index + 1]

        filtered = self.predictions_df[
            self.predictions_df["severity"].isin(included_levels)
        ].copy()

        return filtered.sort_values("anomaly_score", ascending=True)

    def get_critical_alerts(self) -> pd.DataFrame:
        """Return only CRITICAL severity anomalies."""
        return self.get_anomalies(min_severity=SEVERITY_CRITICAL)

    def to_dict(self) -> Dict:
        """
        Serialize the entire prediction result to a dictionary.

        Useful for JSON API responses (Phase 7 Flask API).

        Returns:
            Dict with 'predictions', 'summary', and 'metadata' keys.
        """
        return {
            "predictions": self.predictions_df.to_dict(orient="records"),
            "summary": self.summary,
            "metadata": self.metadata,
        }


# ===========================================================================
# AnomalyPredictor
# ===========================================================================


class AnomalyPredictor:
    """
    Prediction engine for anomaly scoring.

    Loads the trained Isolation Forest model and fitted StandardScaler
    from Phase 5 artifacts, scores new feature vectors, and classifies
    each observation into a SOC-friendly severity level.

    THIS CLASS HAS NO fit() OR train() METHOD.
    Training and prediction are STRUCTURALLY separated.

    Typical usage:
        predictor = AnomalyPredictor()
        predictor.load_artifacts()
        result = predictor.predict(features_df)

    Args:
        config: PredictionConfig instance (injectable for testing).
    """

    def __init__(self, config: Optional[PredictionConfig] = None) -> None:
        self._config = config or PredictionConfig()
        self._model = None
        self._scaler: Optional[FeatureScaler] = None
        self._training_metadata: Optional[Dict] = None
        self._is_loaded = False

    @property
    def is_loaded(self) -> bool:
        """Whether model and scaler have been loaded from disk."""
        return self._is_loaded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_artifacts(self) -> None:
        """
        Load the trained model, scaler, and metadata from disk.

        Must be called before predict().  This is intentionally
        separate from __init__ to allow lazy loading and to make
        the loading step explicit and testable.

        Raises:
            FileNotFoundError: If model or scaler files do not exist.
        """
        logger.info("Loading prediction artifacts...")

        # Load model
        self._load_model()

        # Load scaler (using FeatureScaler.load() from train.py)
        self._load_scaler()

        # Load training metadata (optional — for observability)
        self._load_training_metadata()

        self._is_loaded = True
        logger.info("All prediction artifacts loaded successfully.")

    def predict(self, df: pd.DataFrame) -> PredictionResult:
        """
        Score a feature DataFrame and classify anomaly severity.

        Workflow:
          1. Validate that artifacts are loaded
          2. Validate input schema (15 feature columns required)
          3. Extract and scale numeric features
          4. Compute anomaly scores via decision_function()
          5. Compute binary labels via predict()
          6. Classify severity levels
          7. Build PredictionResult with predictions, summary, metadata

        Args:
            df: DataFrame with at least the 15 feature columns from
                Phase 4.  May also include 'hour' and 'computer'
                columns (preserved for attribution).

        Returns:
            PredictionResult containing per-row predictions, summary
            statistics, and prediction metadata.

        Raises:
            RuntimeError:  If artifacts have not been loaded.
            ValueError:    If required feature columns are missing.
        """
        if not self._is_loaded:
            raise RuntimeError(
                "Prediction artifacts not loaded. "
                "Call load_artifacts() before predict()."
            )

        logger.info(f"Scoring {len(df):,} feature rows...")

        # Step 1: Validate input
        self._validate_input(df)

        # Step 2: Preserve attribution columns
        attribution_cols = self._extract_attribution(df)

        # Step 3: Scale features
        scaled_data = self._scaler.transform(df)

        # Step 4: Score
        raw_scores = self._model.decision_function(scaled_data)
        predictions = self._model.predict(scaled_data)

        # Step 5: Classify severity
        severity_labels = self._classify_severity(raw_scores)

        # Step 6: Build result DataFrame
        predictions_df = self._build_predictions_df(
            df, attribution_cols, raw_scores, predictions, severity_labels
        )

        # Step 7: Build summary and metadata
        summary = self._build_summary(predictions_df)
        metadata = self._build_metadata()

        result = PredictionResult(
            predictions_df=predictions_df,
            summary=summary,
            metadata=metadata,
        )

        logger.info(
            f"Prediction complete: {summary['total_samples']} samples, "
            f"{summary['total_anomalies']} anomalies "
            f"({summary['anomaly_rate'] * 100:.1f}%)"
        )

        return result

    # ------------------------------------------------------------------
    # Private helpers — Loading
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """
        Load the trained Isolation Forest model from disk.

        Raises:
            FileNotFoundError: If the model file does not exist.
        """
        path = self._config.model_path

        if not path.exists():
            raise FileNotFoundError(
                f"Model file not found: {path}\n"
                f"Run training first:  python ml_engine/train.py"
            )

        self._model = joblib.load(path)

        params = self._model.get_params()
        logger.info(f"Model loaded from: {path}")
        logger.info(
            f"  IsolationForest: n_estimators={params['n_estimators']}, "
            f"contamination={params['contamination']}"
        )

    def _load_scaler(self) -> None:
        """
        Load the fitted StandardScaler from disk.

        Uses FeatureScaler.load() from train.py to ensure the
        exact same wrapper class and feature column ordering.

        Raises:
            FileNotFoundError: If the scaler file does not exist.
        """
        self._scaler = FeatureScaler.load(self._config.scaler_path)

        # Verify feature columns match config
        scaler_cols = self._scaler.feature_columns
        config_cols = self._config.feature_columns

        if scaler_cols != config_cols:
            logger.warning(
                f"Feature column mismatch between scaler and config!\n"
                f"  Scaler columns: {scaler_cols}\n"
                f"  Config columns: {config_cols}\n"
                f"Using scaler columns (they were used during training)."
            )

    def _load_training_metadata(self) -> None:
        """
        Load training metadata JSON for observability.

        This is optional — prediction works without it, but the
        metadata enriches the PredictionResult with training context.
        """
        path = self._config.metadata_path

        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._training_metadata = json.load(f)
                logger.info(f"Training metadata loaded from: {path}")
                logger.info(
                    f"  Trained at: "
                    f"{self._training_metadata.get('training_timestamp', 'unknown')}"
                )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    f"Could not load training metadata: {exc}. "
                    f"Prediction will proceed without it."
                )
                self._training_metadata = None
        else:
            logger.warning(
                f"Training metadata not found: {path}. "
                f"Prediction will proceed without it."
            )
            self._training_metadata = None

    # ------------------------------------------------------------------
    # Private helpers — Validation
    # ------------------------------------------------------------------

    def _validate_input(self, df: pd.DataFrame) -> None:
        """
        Validate that the input DataFrame has all required feature columns.

        Args:
            df: The input DataFrame.

        Raises:
            ValueError: If required feature columns are missing.
        """
        required = set(self._config.feature_columns)
        present = set(df.columns)
        missing = required - present

        if missing:
            raise ValueError(
                f"Input DataFrame is missing required feature columns: "
                f"{sorted(missing)}. "
                f"Expected: {self._config.feature_columns}. "
                f"Got: {sorted(df.columns.tolist())}"
            )

        # Check for NaN in feature columns
        nan_counts = df[self._config.feature_columns].isna().sum()
        total_nans = nan_counts.sum()
        if total_nans > 0:
            logger.warning(
                f"Input contains {total_nans} NaN values across feature columns. "
                f"Rows with NaN will produce unreliable scores."
            )

        logger.info(f"Input validation passed: {len(df):,} rows, 0 missing columns.")

    def _extract_attribution(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract non-feature columns (hour, computer) for result attribution.

        These columns let SOC analysts trace anomaly scores back to
        specific time windows and machines.

        Args:
            df: The input DataFrame.

        Returns:
            DataFrame with only the attribution columns that exist.
        """
        available_cols = [
            col for col in self._config.non_feature_cols
            if col in df.columns
        ]

        if available_cols:
            return df[available_cols].copy()
        else:
            return pd.DataFrame(index=df.index)

    # ------------------------------------------------------------------
    # Private helpers — Scoring & Classification
    # ------------------------------------------------------------------

    def _classify_severity(self, scores: np.ndarray) -> np.ndarray:
        """
        Map continuous anomaly scores to SOC-friendly severity labels.

        Uses numpy vectorised operations for performance.

        Thresholds (from Config):
          score <= -0.3         → CRITICAL
          -0.3 < score <= -0.1  → HIGH
          -0.1 < score <=  0.0  → MEDIUM
          score >  0.0          → LOW

        Args:
            scores: Array of decision_function scores.

        Returns:
            Array of severity label strings.
        """
        severity = np.full(len(scores), SEVERITY_LOW, dtype=object)

        severity[scores <= self._config.severity_critical] = SEVERITY_CRITICAL
        severity[
            (scores > self._config.severity_critical)
            & (scores <= self._config.severity_high)
        ] = SEVERITY_HIGH
        severity[
            (scores > self._config.severity_high)
            & (scores <= self._config.severity_medium)
        ] = SEVERITY_MEDIUM
        # Remaining are already SEVERITY_LOW

        return severity

    def _build_predictions_df(
        self,
        original_df: pd.DataFrame,
        attribution: pd.DataFrame,
        scores: np.ndarray,
        predictions: np.ndarray,
        severity: np.ndarray,
    ) -> pd.DataFrame:
        """
        Build the final predictions DataFrame with all columns.

        Args:
            original_df:  Original input DataFrame (for feature values).
            attribution:  DataFrame with hour/computer columns.
            scores:       Raw decision_function scores.
            predictions:  Binary predictions (1=normal, -1=anomaly).
            severity:     Severity label array.

        Returns:
            DataFrame with attribution + features + score columns,
            sorted by anomaly_score ascending (most anomalous first).
        """
        result = attribution.copy()

        # Add feature columns
        for col in self._config.feature_columns:
            if col in original_df.columns:
                result[col] = original_df[col].values

        # Add prediction columns
        result["anomaly_score"] = np.round(scores, 6)
        result["is_anomaly"] = predictions == -1
        result["severity"] = severity

        # Sort by score ascending (most anomalous first)
        result = result.sort_values("anomaly_score", ascending=True)
        result = result.reset_index(drop=True)

        return result

    def _build_summary(self, predictions_df: pd.DataFrame) -> Dict:
        """
        Build aggregate summary statistics from predictions.

        Args:
            predictions_df: The final predictions DataFrame.

        Returns:
            Dict with total counts, anomaly rate, per-severity
            breakdowns, and score distribution.
        """
        total = len(predictions_df)
        n_anomalies = int(predictions_df["is_anomaly"].sum())
        n_normal = total - n_anomalies
        anomaly_rate = n_anomalies / total if total > 0 else 0.0

        # Per-severity counts
        severity_counts = (
            predictions_df["severity"]
            .value_counts()
            .to_dict()
        )
        # Ensure all levels are present
        for level in SEVERITY_ORDER:
            severity_counts.setdefault(level, 0)

        # Score distribution
        scores = predictions_df["anomaly_score"]
        score_distribution = {
            "min": round(float(scores.min()), 6),
            "max": round(float(scores.max()), 6),
            "mean": round(float(scores.mean()), 6),
            "std": round(float(scores.std()), 6),
            "median": round(float(scores.median()), 6),
        }

        return {
            "total_samples": total,
            "total_anomalies": n_anomalies,
            "total_normal": n_normal,
            "anomaly_rate": round(anomaly_rate, 4),
            "severity_counts": severity_counts,
            "score_distribution": score_distribution,
        }

    def _build_metadata(self) -> Dict:
        """
        Build prediction metadata for the result.

        Includes model info, prediction timestamp, thresholds,
        and training context if available.

        Returns:
            Dict with prediction metadata.
        """
        metadata = {
            "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
            "model_path": str(self._config.model_path),
            "scaler_path": str(self._config.scaler_path),
            "feature_columns": self._config.feature_columns,
            "severity_thresholds": {
                "critical": self._config.severity_critical,
                "high": self._config.severity_high,
                "medium": self._config.severity_medium,
            },
        }

        # Enrich with training context if available
        if self._training_metadata:
            metadata["training_info"] = {
                "trained_at": self._training_metadata.get(
                    "training_timestamp", "unknown"
                ),
                "hyperparameters": self._training_metadata.get(
                    "hyperparameters", {}
                ),
                "training_samples": self._training_metadata.get(
                    "dataset", {}
                ).get("total_rows", "unknown"),
            }

        return metadata


# ===========================================================================
# Standalone Script Entry Point
# ===========================================================================


def main() -> None:
    """
    Run the prediction engine as a standalone script.

    Loads features.csv, scores all rows using the trained model,
    and prints a comprehensive summary of predictions.

    Usage:
        python ml_engine/predict.py

    Prerequisites:
        - Phase 4 must have been executed (features.csv must exist)
        - Phase 5 must have been executed (model + scaler must exist)

    Output:
        Console output with prediction summary and sample anomalies.
    """
    Config.ensure_directories()

    features_path = Config.PROCESSED_DIR / Config.FEATURES_FILENAME

    logger.info("=" * 60)
    logger.info("PHASE 6 — Prediction Engine")
    logger.info("=" * 60)
    logger.info(f"Features: {features_path}")
    logger.info(f"Model   : {Config.MODEL_PATH}")
    logger.info(f"Scaler  : {Config.SCALER_PATH}")

    # Load features
    if not features_path.exists():
        logger.error(
            f"Features file not found: {features_path}\n"
            f"Run Phase 4 first:  python ml_engine/feature_engineering.py"
        )
        sys.exit(1)

    features_df = pd.read_csv(features_path, encoding="utf-8")
    logger.info(f"Loaded {len(features_df):,} feature rows")

    # Initialize predictor
    predictor = AnomalyPredictor()

    try:
        predictor.load_artifacts()
        result = predictor.predict(features_df)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        logger.error(f"Prediction failed: {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Prediction failed — unexpected error: {exc}", exc_info=True)
        sys.exit(1)

    # Log comprehensive results
    _log_prediction_results(result)

    logger.info("=" * 60)
    logger.info("PHASE 6 COMPLETE")
    logger.info("=" * 60)


def _log_prediction_results(result: PredictionResult) -> None:
    """
    Log a comprehensive summary of prediction results.

    Args:
        result: The PredictionResult from the predictor.
    """
    summary = result.summary

    logger.info("")
    logger.info("--- Prediction Summary ---")
    logger.info(f"  Total samples    : {summary['total_samples']:,}")
    logger.info(f"  Total anomalies  : {summary['total_anomalies']:,}")
    logger.info(f"  Total normal     : {summary['total_normal']:,}")
    logger.info(
        f"  Anomaly rate     : {summary['anomaly_rate'] * 100:.1f}%"
    )

    logger.info("")
    logger.info("--- Severity Breakdown ---")
    for level in SEVERITY_ORDER:
        count = summary["severity_counts"].get(level, 0)
        bar = "█" * count + "░" * max(0, 10 - count)
        logger.info(f"  {level:10s} : {count:>4d}  {bar}")

    logger.info("")
    logger.info("--- Score Distribution ---")
    dist = summary["score_distribution"]
    logger.info(f"  Min    : {dist['min']:.6f}")
    logger.info(f"  Max    : {dist['max']:.6f}")
    logger.info(f"  Mean   : {dist['mean']:.6f}")
    logger.info(f"  Std    : {dist['std']:.6f}")
    logger.info(f"  Median : {dist['median']:.6f}")

    # Show top anomalies
    anomalies = result.get_anomalies(min_severity=SEVERITY_MEDIUM)
    if not anomalies.empty:
        logger.info("")
        logger.info(
            f"--- Top Anomalies (MEDIUM severity and above): "
            f"{len(anomalies)} found ---"
        )
        display_cols = ["hour", "computer", "anomaly_score", "severity"]
        available_cols = [c for c in display_cols if c in anomalies.columns]

        for _, row in anomalies.head(15).iterrows():
            parts = []
            for col in available_cols:
                parts.append(f"{col}={row[col]}")
            logger.info(f"  {' | '.join(parts)}")
    else:
        logger.info("")
        logger.info("--- No anomalies at MEDIUM severity or above ---")

    # Show critical alerts specifically
    critical = result.get_critical_alerts()
    if not critical.empty:
        logger.info("")
        logger.info(
            f"⚠  CRITICAL ALERTS: {len(critical)} observations "
            f"require immediate investigation!"
        )


if __name__ == "__main__":
    main()
