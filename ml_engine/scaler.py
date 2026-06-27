"""
ml_engine/scaler.py
====================
Feature Scaler Module — StandardScaler wrapper with joblib persistence.

WHY THIS EXISTS (Critical Fix C2):
  Previously, FeatureScaler lived inside train.py.  predict.py imported
  it via 'from train import FeatureScaler', which:
    - Violated the project rule: "training and prediction must remain
      fully separated"
    - Forced predict.py to load all training-specific imports
      (IsolationForest constructor, etc.)
    - Created a hidden coupling between train and predict

  Now FeatureScaler lives in its own module.  Both train.py and
  predict.py import from scaler.py.  Neither depends on the other.

USAGE:
  # During training (Phase 5):
  from ml_engine.scaler import FeatureScaler
  scaler = FeatureScaler(feature_columns)
  scaled = scaler.fit_transform(df)
  scaler.save(path)

  # During prediction (Phase 6):
  from ml_engine.scaler import FeatureScaler
  scaler = FeatureScaler.load(path)
  scaled = scaler.transform(df)
"""

from pathlib import Path
from typing import List

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from .logger import get_logger

logger = get_logger(__name__)


class FeatureScaler:
    """
    Wrapper around sklearn StandardScaler with joblib persistence.

    WHY A WRAPPER:
      - Encapsulates fit + transform + save/load into a single cohesive API.
      - Adds logging and validation around the raw sklearn calls.
      - Both train.py and predict.py import this independently —
        neither depends on the other.

    The scaler must be fitted during training and reused IDENTICALLY
    during prediction.  Any mismatch in scaling between train and
    predict will cause the model to produce meaningless scores.

    Args:
        feature_columns: Ordered list of feature column names the
                         scaler was fitted on.
    """

    def __init__(self, feature_columns: List[str]) -> None:
        self._feature_columns = feature_columns
        self._scaler = StandardScaler()
        self._is_fitted = False

    @property
    def is_fitted(self) -> bool:
        """Whether the scaler has been fitted on training data."""
        return self._is_fitted

    @property
    def feature_columns(self) -> List[str]:
        """Return the feature columns this scaler was fitted on."""
        return list(self._feature_columns)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit_transform(self, df: pd.DataFrame) -> np.ndarray:
        """
        Fit the scaler on the feature matrix and return transformed data.

        This should be called ONLY during training.  For prediction,
        use transform() with a previously-fitted scaler loaded via load().

        Args:
            df: DataFrame containing at least the columns in
                ``self._feature_columns``.

        Returns:
            Scaled numpy array of shape (n_samples, n_features).

        Raises:
            ValueError: If required feature columns are missing.
        """
        self._validate_columns(df)

        feature_matrix = df[self._feature_columns].values
        logger.info(
            f"Fitting StandardScaler on {feature_matrix.shape[0]} samples "
            f"x {feature_matrix.shape[1]} features"
        )

        scaled = self._scaler.fit_transform(feature_matrix)
        self._is_fitted = True

        # Log scaling statistics for observability
        self._log_scaling_stats()

        return scaled

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """
        Transform new data using an already-fitted scaler.

        This is used during prediction (Phase 6).  The scaler must
        have been fitted first (via fit_transform or load).

        Args:
            df: DataFrame containing the same feature columns.

        Returns:
            Scaled numpy array.

        Raises:
            RuntimeError: If the scaler has not been fitted.
            ValueError:   If required feature columns are missing.
        """
        if not self._is_fitted:
            raise RuntimeError(
                "Scaler has not been fitted. Call fit_transform() first "
                "or load a previously fitted scaler via FeatureScaler.load()."
            )
        self._validate_columns(df)
        return self._scaler.transform(df[self._feature_columns].values)

    def save(self, path: Path) -> None:
        """
        Persist the fitted scaler to disk using joblib.

        Saves both the sklearn scaler object and the feature column
        list so that the prediction engine can reconstruct the exact
        same scaler.

        Args:
            path: Destination file path.

        Raises:
            RuntimeError: If the scaler has not been fitted.
        """
        if not self._is_fitted:
            raise RuntimeError("Cannot save an unfitted scaler.")

        path.parent.mkdir(parents=True, exist_ok=True)

        artifact = {
            "scaler": self._scaler,
            "feature_columns": self._feature_columns,
        }
        joblib.dump(artifact, path)
        logger.info(f"Scaler saved to: {path}")

    @classmethod
    def load(cls, path: Path) -> "FeatureScaler":
        """
        Load a previously fitted scaler from disk.

        This is the primary entry point for prediction.

        Args:
            path: Path to the saved scaler joblib file.

        Returns:
            A FeatureScaler instance with the fitted scaler restored.

        Raises:
            FileNotFoundError: If the scaler file does not exist.
        """
        if not path.exists():
            raise FileNotFoundError(
                f"Scaler file not found: {path}\n"
                f"Run training first:  python -m ml_engine.train"
            )

        artifact = joblib.load(path)
        instance = cls(feature_columns=artifact["feature_columns"])
        instance._scaler = artifact["scaler"]
        instance._is_fitted = True

        logger.info(f"Scaler loaded from: {path}")
        logger.info(f"  Feature columns: {instance._feature_columns}")
        return instance

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_columns(self, df: pd.DataFrame) -> None:
        """Verify that the DataFrame has all required feature columns."""
        required = set(self._feature_columns)
        present = set(df.columns)
        missing = required - present

        if missing:
            raise ValueError(
                f"DataFrame is missing required feature columns: "
                f"{sorted(missing)}. "
                f"Expected: {self._feature_columns}. "
                f"Got: {sorted(df.columns.tolist())}"
            )

    def _log_scaling_stats(self) -> None:
        """Log the per-feature mean and scale after fitting."""
        means = self._scaler.mean_
        scales = self._scaler.scale_

        logger.info("StandardScaler statistics:")
        for i, col in enumerate(self._feature_columns):
            logger.info(
                f"  {col:30s} | mean={means[i]:>12.4f}  scale={scales[i]:>12.4f}"
            )
