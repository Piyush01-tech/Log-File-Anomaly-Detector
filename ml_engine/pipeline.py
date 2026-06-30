"""
ml_engine/pipeline.py
======================
Analysis Pipeline — single-file orchestrator for the ML workflow.

WHY THIS EXISTS (High Fix H3):
  The existing modules (parser, feature_engineering, predict) are designed
  for batch processing via CSV intermediates.  The Flask API and Django
  upload workflow need to process a SINGLE .evtx file end-to-end:
    upload → parse → feature engineering → prediction → results

  AnalysisPipeline chains the three steps in memory (no intermediate
  CSV writes required), making it suitable for API-driven analysis.

ARCHITECTURE:
  AnalysisPipeline chains:
    1. EVTXFileParser.parse_file(path)         → raw events DataFrame
    2. EventFeatureBuilder.build_features(df)   → feature matrix DataFrame
    3. AnomalyPredictor.predict(features_df)    → PredictionResult

  The pipeline is stateless — each call to analyze() is independent.
  The AnomalyPredictor's model and scaler are loaded once at
  construction time and reused across calls.

USAGE:
  from ml_engine.pipeline import AnalysisPipeline
  pipeline = AnalysisPipeline()       # loads model + scaler
  result = pipeline.analyze(evtx_path) # parse → features → predict
  print(result.summary)
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import Config
from .logger import get_logger
from .feature_engineering import EventFeatureBuilder, FeatureEngineeringConfig
from .parser import EVTXFileParser
from .predict import AnomalyPredictor, PredictionConfig, PredictionResult

logger = get_logger(__name__)


@dataclass(frozen=True)
class PipelineConfig:
    """
    Configuration for the end-to-end analysis pipeline.

    Combines parser, feature engineering, and prediction config
    into a single injectable configuration object.

    Attributes:
        model_path:      Path to the trained Isolation Forest model.
        scaler_path:     Path to the fitted StandardScaler.
        feature_columns: Ordered list of numeric feature column names.
        window_freq:     Time window for feature aggregation (e.g. 'h').
    """

    model_path: Path = field(default_factory=lambda: Config.MODEL_PATH)
    scaler_path: Path = field(default_factory=lambda: Config.SCALER_PATH)
    feature_columns: list = field(
        default_factory=lambda: list(Config.FEATURE_COLUMNS)
    )
    window_freq: str = Config.FEATURE_WINDOW_FREQ
    monitored_event_ids: list = field(
        default_factory=lambda: list(Config.MONITORED_EVENT_IDS)
    )


class AnalysisPipeline:
    """
    End-to-end analysis pipeline for single .evtx files.

    Chains: parse → feature engineering → anomaly prediction.

    This is the primary entry point for the Flask API and Django
    upload workflow.  It replaces the batch-oriented CSV-to-CSV
    workflow with an in-memory, single-file analysis.

    The pipeline is stateless per call — each analyze() invocation
    is independent.  The model and scaler are loaded once at
    construction time and reused for all subsequent calls.

    Args:
        config: Optional PipelineConfig for dependency injection.

    Example:
        pipeline = AnalysisPipeline()
        result = pipeline.analyze(Path("data/raw_logs/suspicious.evtx"))
        print(result.summary["total_anomalies"])
    """

    def __init__(self, config: Optional[PipelineConfig] = None) -> None:
        self._config = config or PipelineConfig()
        self._parser = EVTXFileParser()
        self._feature_builder = EventFeatureBuilder(
            FeatureEngineeringConfig(
                feature_columns=self._config.feature_columns,
                window_freq=self._config.window_freq,
            )
        )

        # Initialize predictor and load artifacts once
        prediction_config = PredictionConfig(
            model_path=self._config.model_path,
            scaler_path=self._config.scaler_path,
            feature_columns=self._config.feature_columns,
        )
        self._predictor = AnomalyPredictor(config=prediction_config)
        self._predictor.load_artifacts()

        logger.info("AnalysisPipeline initialized — model and scaler loaded.")

    def analyze(self, evtx_path: Path) -> PredictionResult:
        """
        Run the full analysis pipeline on a single .evtx file.

        Workflow:
          1. Parse .evtx file → raw events DataFrame
          2. Build features from raw events → feature matrix
          3. Score features with Isolation Forest → PredictionResult

        Args:
            evtx_path: Absolute path to the .evtx file to analyze.

        Returns:
            PredictionResult containing per-row predictions,
            summary statistics, and prediction metadata.

        Raises:
            FileNotFoundError: If the .evtx file does not exist.
            ValueError:        If parsing produces no events or
                               feature engineering produces no rows.
            RuntimeError:      If the model/scaler are not loaded.
        """
        evtx_path = Path(evtx_path)

        if not evtx_path.exists():
            raise FileNotFoundError(f"EVTX file not found: {evtx_path}")

        if not evtx_path.suffix.lower() == ".evtx":
            raise ValueError(
                f"Expected .evtx file, got: {evtx_path.suffix}"
            )

        logger.info(f"Analyzing: {evtx_path.name}")

        # Step 1: Parse
        logger.info("  Step 1/3: Parsing EVTX file...")
        raw_events_df = self._parser.parse(evtx_path)

        if raw_events_df.empty:
            raise ValueError(
                f"Parsing produced no events from: {evtx_path.name}. "
                f"The file may be empty or contain no parseable records."
            )

        logger.info(f"  Parsed {len(raw_events_df):,} raw events")

        # Step 2: Feature Engineering
        logger.info("  Step 2/3: Building feature matrix...")
        features_df = self._feature_builder.build_features(raw_events_df)

        if features_df.empty:
            raise ValueError(
                f"Feature engineering produced no rows from "
                f"{len(raw_events_df):,} raw events. "
                f"Check if monitored event IDs are present in the log."
            )

        logger.info(f"  Built {len(features_df):,} feature rows")

        # Step 3: Prediction
        logger.info("  Step 3/3: Running anomaly detection...")
        result = self._predictor.predict(features_df)

        logger.info(
            f"  Analysis complete: {result.summary['total_anomalies']} "
            f"anomalies in {result.summary['total_samples']} windows"
        )

        return result

    def analyze_dataframe(self, raw_events_df: pd.DataFrame) -> PredictionResult:
        """
        Run feature engineering + prediction on an already-parsed DataFrame.

        Useful when events come from a non-EVTX source (future live
        ingestion, API input, etc.).

        Args:
            raw_events_df: DataFrame with parsed event columns
                           (timestamp, event_id, computer, user, etc.)

        Returns:
            PredictionResult

        Raises:
            ValueError: If the DataFrame is empty or feature engineering
                        produces no rows.
        """
        if raw_events_df.empty:
            raise ValueError("Input DataFrame is empty.")

        logger.info(f"Analyzing {len(raw_events_df):,} pre-parsed events...")

        # Feature Engineering
        features_df = self._feature_builder.build_features(raw_events_df)

        if features_df.empty:
            raise ValueError(
                f"Feature engineering produced no rows from "
                f"{len(raw_events_df):,} events."
            )

        # Prediction
        result = self._predictor.predict(features_df)

        logger.info(
            f"Analysis complete: {result.summary['total_anomalies']} anomalies"
        )

        return result


# ===========================================================================
# Standalone Script Entry Point
# ===========================================================================


def main() -> None:
    """
    Run the analysis pipeline as a standalone script.

    Processes all .evtx files in data/raw_logs/ and prints results.

    Usage:
        python -m ml_engine.pipeline

    Prerequisites:
        - Phase 5 must have been executed (model + scaler must exist)
        - EVTX files must exist in data/raw_logs/
    """
    Config.ensure_directories()

    logger.info("=" * 60)
    logger.info("Analysis Pipeline — End-to-End Test")
    logger.info("=" * 60)

    # Find all .evtx files
    evtx_files = list(Config.RAW_LOGS_DIR.rglob("*.evtx"))

    if not evtx_files:
        logger.error(
            f"No .evtx files found in: {Config.RAW_LOGS_DIR}\n"
            f"Add .evtx files and try again."
        )
        sys.exit(1)

    logger.info(f"Found {len(evtx_files)} .evtx files")

    try:
        pipeline = AnalysisPipeline()
    except (FileNotFoundError, RuntimeError) as exc:
        logger.error(f"Pipeline initialization failed: {exc}")
        sys.exit(1)

    total_anomalies = 0
    total_files_processed = 0

    for evtx_path in evtx_files[:5]:  # Limit to 5 for testing
        try:
            result = pipeline.analyze(evtx_path)
            total_anomalies += result.summary["total_anomalies"]
            total_files_processed += 1
            logger.info(
                f"  {evtx_path.name}: "
                f"{result.summary['total_samples']} windows, "
                f"{result.summary['total_anomalies']} anomalies"
            )
        except (ValueError, RuntimeError) as exc:
            logger.warning(f"  {evtx_path.name}: Skipped — {exc}")

    logger.info("")
    logger.info(f"Files processed: {total_files_processed}")
    logger.info(f"Total anomalies: {total_anomalies}")
    logger.info("=" * 60)
    logger.info("Pipeline test complete.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
