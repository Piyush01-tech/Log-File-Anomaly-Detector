"""
ml_engine/feature_engineering.py
=================================
Phase 4 — Feature Engineering Module.

PURPOSE:
  Transforms raw parsed event records (from Phase 3) into a numeric
  feature matrix suitable for Isolation Forest training (Phase 5).

ARCHITECTURE:
  FeatureEngineeringConfig  — Immutable config dataclass (event-ID
                              mappings, window freq, column names).
  EventFeatureBuilder       — Pure computational core.  Groups events
                              by (hour, computer) and computes 15
                              behavioral features per window.
  FeatureEngineeringPipeline— Orchestrator.  Handles I/O, schema
                              validation, logging, and CSV export.

WHY THREE CLASSES:
  - Config is a data object: easy to override per-environment or test.
  - Builder is pure logic: can be unit-tested with synthetic DataFrames
    — no disk I/O, no side-effects.
  - Pipeline owns I/O: can be swapped for a streaming variant later
    without touching the feature math.

KEY DESIGN DECISIONS:
  - Hourly windows via pd.Grouper(freq='h') — balances noise
    suppression with spike visibility for SOC analysts.
  - Named aggregation in a single GroupBy pass — avoids N separate
    groupby calls and keeps the code declarative.
  - Division-by-zero handled via numpy.where (vectorised).
  - Schema validation on both INPUT (parsed_events.csv) and OUTPUT
    (features.csv) — fail-fast on missing columns.

INPUT:
  data/processed/parsed_events.csv   (Phase 3 output)

OUTPUT:
  data/processed/features.csv        (Phase 4 output)

USAGE (as a module):
  from feature_engineering import FeatureEngineeringPipeline
  pipeline = FeatureEngineeringPipeline()
  features_df = pipeline.run()

USAGE (as a script):
  python ml_engine/feature_engineering.py
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path Setup — allows running as both a module and a standalone script
# ---------------------------------------------------------------------------

_ML_ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_ML_ENGINE_DIR))

from config import Config       # noqa: E402
from logger import get_logger   # noqa: E402

logger = get_logger(__name__)


# ===========================================================================
# FeatureEngineeringConfig
# ===========================================================================


@dataclass(frozen=True)
class FeatureEngineeringConfig:
    """
    Immutable configuration for the feature engineering pipeline.

    WHY A DATACLASS:
      - Keeps all magic numbers in one inspectable, type-hinted object.
      - ``frozen=True`` prevents accidental mutation at runtime.
      - Can be overridden in unit tests without monkey-patching globals.

    Attributes:
        window_freq:                Pandas offset alias for time windowing.
        event_id_failed_login:      Event ID for failed login (4625).
        event_id_successful_login:  Event ID for successful login (4624).
        event_id_admin_privilege:   Event ID for admin privilege (4672).
        event_id_process_creation:  Event ID for process creation (4688).
        event_id_user_created:      Event ID for user created (4720).
        event_id_service_install:   Event IDs for service installation
                                    (4697, 7045).
        event_id_group_change:      Event ID for group membership change
                                    (4728).
        event_id_audit_clear:       Event ID for audit log cleared (1102).
        required_input_columns:     Columns that must exist in the input
                                    DataFrame for feature computation.
        feature_columns:            Ordered list of output feature names.
    """

    window_freq: str = Config.FEATURE_WINDOW_FREQ

    # Individual event-ID mappings
    event_id_failed_login: int = 4625
    event_id_successful_login: int = 4624
    event_id_admin_privilege: int = 4672
    event_id_process_creation: int = 4688
    event_id_user_created: int = 4720
    event_id_service_install: List[int] = field(
        default_factory=lambda: [4697, 7045]
    )
    event_id_group_change: int = 4728
    event_id_audit_clear: int = 1102

    # Minimum columns required from the parser output
    required_input_columns: List[str] = field(
        default_factory=lambda: [
            "timestamp",
            "event_id",
            "computer",
            "username",
            "process_name",
            "ip_address",
        ]
    )

    # Output feature names (order matters for CSV)
    feature_columns: List[str] = field(
        default_factory=lambda: list(Config.FEATURE_COLUMNS)
    )


# ===========================================================================
# EventFeatureBuilder
# ===========================================================================


class EventFeatureBuilder:
    """
    Pure computational engine for feature extraction.

    Takes a validated DataFrame of parsed event records and produces
    a DataFrame of behavioral features — one row per (hour, computer)
    window.

    NO I/O.  NO SIDE-EFFECTS.  This class is designed for easy unit
    testing with synthetic DataFrames.

    Args:
        config: A FeatureEngineeringConfig instance.
    """

    def __init__(self, config: Optional[FeatureEngineeringConfig] = None) -> None:
        self._config = config or FeatureEngineeringConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform raw parsed events into behavioural feature rows.

        Workflow:
          1. Floor timestamps to the configured window frequency.
          2. GroupBy (hour, computer).
          3. Compute 12 count features via named aggregation.
          4. Compute 3 ratio features with safe division.
          5. Reorder columns to match config.feature_columns.

        Args:
            df: DataFrame with at least the columns listed in
                ``config.required_input_columns``.

        Returns:
            DataFrame with columns ``['hour', 'computer'] + config.feature_columns``.
            Empty DataFrame if the input is empty.

        Raises:
            ValueError: If required input columns are missing.
        """
        if df.empty:
            logger.warning("Input DataFrame is empty — returning empty features.")
            return self._empty_features()

        # Ensure timestamp is datetime
        df = self._ensure_datetime(df)

        # Create the hour column by flooring timestamp
        df = df.copy()
        df["hour"] = df["timestamp"].dt.floor(self._config.window_freq)

        logger.info(
            f"Building features with window_freq='{self._config.window_freq}' "
            f"across {df['hour'].nunique()} time windows "
            f"and {df['computer'].nunique()} computers"
        )

        # GroupBy and aggregate
        grouped = df.groupby(["hour", "computer"], observed=True)
        features_df = self._compute_count_features(grouped, df)
        features_df = self._compute_ratio_features(features_df)

        # Reorder columns
        output_cols = ["hour", "computer"] + self._config.feature_columns
        features_df = features_df[output_cols]

        logger.info(
            f"Feature matrix: {features_df.shape[0]} rows × "
            f"{features_df.shape[1]} columns"
        )

        return features_df

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_datetime(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Guarantee the 'timestamp' column is datetime64.

        Phase 3 outputs datetime64[ns, UTC], but if the CSV was
        re-read without parse_dates the column may be a string.
        This method handles both cases gracefully.

        Args:
            df: Input DataFrame.

        Returns:
            DataFrame with timestamp as datetime64.
        """
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            logger.info("Converting 'timestamp' column to datetime64")
            df = df.copy()
            df["timestamp"] = pd.to_datetime(
                df["timestamp"], utc=True, errors="coerce"
            )

            null_count = df["timestamp"].isna().sum()
            if null_count > 0:
                logger.warning(
                    f"{null_count} records had unparseable timestamps "
                    f"— they will be excluded from feature computation."
                )
                df = df.dropna(subset=["timestamp"])

        return df

    def _compute_count_features(
        self, grouped: pd.core.groupby.DataFrameGroupBy, df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Compute all 12 count-based features in a single GroupBy pass.

        Uses named aggregation for clarity and performance.  Each feature
        is a lambda applied to the grouped columns.

        Args:
            grouped: The GroupBy object keyed by (hour, computer).
            df:      The original DataFrame (used for isin() checks).

        Returns:
            DataFrame indexed by (hour, computer) with 12 count columns.
        """
        cfg = self._config

        # Pre-compute boolean masks on the full DataFrame.
        # These will be grouped alongside the other columns.
        df_work = df.copy()
        df_work["_is_failed_login"] = (
            df_work["event_id"] == cfg.event_id_failed_login
        ).astype(int)
        df_work["_is_successful_login"] = (
            df_work["event_id"] == cfg.event_id_successful_login
        ).astype(int)
        df_work["_is_admin"] = (
            df_work["event_id"] == cfg.event_id_admin_privilege
        ).astype(int)
        df_work["_is_process_creation"] = (
            df_work["event_id"] == cfg.event_id_process_creation
        ).astype(int)
        df_work["_is_new_user"] = (
            df_work["event_id"] == cfg.event_id_user_created
        ).astype(int)
        df_work["_is_service_install"] = (
            df_work["event_id"].isin(cfg.event_id_service_install)
        ).astype(int)
        df_work["_is_group_change"] = (
            df_work["event_id"] == cfg.event_id_group_change
        ).astype(int)
        df_work["_is_audit_clear"] = (
            df_work["event_id"] == cfg.event_id_audit_clear
        ).astype(int)

        # Re-group with the added boolean columns
        grouped_work = df_work.groupby(["hour", "computer"], observed=True)

        features = grouped_work.agg(
            total_events=("event_id", "size"),
            failed_logins=("_is_failed_login", "sum"),
            successful_logins=("_is_successful_login", "sum"),
            admin_events=("_is_admin", "sum"),
            process_creation_events=("_is_process_creation", "sum"),
            new_user_events=("_is_new_user", "sum"),
            service_install_events=("_is_service_install", "sum"),
            group_membership_changes=("_is_group_change", "sum"),
            audit_log_clears=("_is_audit_clear", "sum"),
            unique_users=("username", "nunique"),
            unique_processes=("process_name", "nunique"),
            unique_ips=("ip_address", "nunique"),
        ).reset_index()

        # Ensure integer types for count columns
        count_cols = [
            "total_events", "failed_logins", "successful_logins",
            "admin_events", "process_creation_events", "new_user_events",
            "service_install_events", "group_membership_changes",
            "audit_log_clears", "unique_users", "unique_processes",
            "unique_ips",
        ]
        for col in count_cols:
            features[col] = features[col].astype(int)

        return features

    def _compute_ratio_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute 3 ratio features with safe division-by-zero handling.

        Uses numpy.where for vectorised conditional logic:
          - If total_events > 0 → compute ratio
          - If total_events == 0 → return 0.0

        Args:
            df: DataFrame with count features already computed.

        Returns:
            Same DataFrame with 3 additional ratio columns.
        """
        total = df["total_events"].values

        df["failure_rate"] = np.where(
            total > 0,
            df["failed_logins"].values / total,
            0.0,
        )
        df["admin_ratio"] = np.where(
            total > 0,
            df["admin_events"].values / total,
            0.0,
        )
        df["process_ratio"] = np.where(
            total > 0,
            df["process_creation_events"].values / total,
            0.0,
        )

        # Round ratios to 6 decimal places for clean CSV output
        for col in ("failure_rate", "admin_ratio", "process_ratio"):
            df[col] = df[col].round(6)

        return df

    def _empty_features(self) -> pd.DataFrame:
        """Return an empty DataFrame with the correct output schema."""
        cols = ["hour", "computer"] + self._config.feature_columns
        return pd.DataFrame(columns=cols)


# ===========================================================================
# FeatureEngineeringPipeline
# ===========================================================================


class FeatureEngineeringPipeline:
    """
    Orchestrator for the feature engineering workflow.

    Responsibilities:
      - Load parsed events CSV from disk.
      - Validate the input schema against Phase 3 expectations.
      - Delegate feature computation to EventFeatureBuilder.
      - Validate the output schema.
      - Export the feature matrix to CSV.
      - Log summary statistics for operator observability.

    This class owns ALL I/O.  EventFeatureBuilder is kept pure.

    Args:
        config:       FeatureEngineeringConfig instance.
        builder:      EventFeatureBuilder instance (injectable for testing).
        input_path:   Path to parsed_events.csv.  Defaults to
                      Config.PROCESSED_DIR / Config.PARSED_EVENTS_FILENAME.
        output_path:  Path for features.csv.  Defaults to
                      Config.PROCESSED_DIR / Config.FEATURES_FILENAME.
    """

    def __init__(
        self,
        config: Optional[FeatureEngineeringConfig] = None,
        builder: Optional[EventFeatureBuilder] = None,
        input_path: Optional[Path] = None,
        output_path: Optional[Path] = None,
    ) -> None:
        self._config = config or FeatureEngineeringConfig()
        self._builder = builder or EventFeatureBuilder(self._config)
        self._input_path = input_path or (
            Config.PROCESSED_DIR / Config.PARSED_EVENTS_FILENAME
        )
        self._output_path = output_path or (
            Config.PROCESSED_DIR / Config.FEATURES_FILENAME
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> pd.DataFrame:
        """
        Execute the full feature engineering pipeline.

        Workflow:
          1. Load parsed_events.csv
          2. Validate input schema
          3. Build features via EventFeatureBuilder
          4. Validate output schema
          5. Save features.csv
          6. Log summary statistics

        Returns:
            The feature matrix DataFrame.

        Raises:
            FileNotFoundError: If parsed_events.csv does not exist.
            ValueError:        If input schema validation fails.
        """
        logger.info("=" * 60)
        logger.info("PHASE 4 — Feature Engineering Pipeline")
        logger.info("=" * 60)
        logger.info(f"Input  : {self._input_path}")
        logger.info(f"Output : {self._output_path}")
        logger.info(f"Window : {self._config.window_freq}")

        # Step 1: Load
        raw_df = self._load_input()

        # Step 2: Validate input
        self._validate_input(raw_df)

        # Step 3: Build features
        features_df = self._builder.build_features(raw_df)

        if features_df.empty:
            logger.error(
                "Feature builder returned an empty DataFrame. "
                "Check that parsed_events.csv contains valid records."
            )
            return features_df

        # Step 4: Validate output
        self._validate_output(features_df)

        # Step 5: Save
        self._save_output(features_df)

        # Step 6: Log summary
        self._log_summary(features_df)

        logger.info("=" * 60)
        logger.info("PHASE 4 COMPLETE")
        logger.info("=" * 60)

        return features_df

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_input(self) -> pd.DataFrame:
        """
        Load parsed_events.csv from disk.

        Handles the common case where timestamp needs re-parsing
        after a CSV round-trip.

        Returns:
            DataFrame with parsed event records.

        Raises:
            FileNotFoundError: If the input file does not exist.
        """
        if not self._input_path.exists():
            raise FileNotFoundError(
                f"Parsed events file not found: {self._input_path}\n"
                f"Run Phase 3 first:  python ml_engine/parser.py"
            )

        logger.info(f"Loading parsed events from: {self._input_path}")

        df = pd.read_csv(
            self._input_path,
            encoding="utf-8",
            parse_dates=["timestamp"],
        )

        logger.info(
            f"Loaded {len(df):,} records with {df.columns.tolist()} columns"
        )

        # Ensure event_id is nullable integer (survives CSV round-trip)
        if "event_id" in df.columns:
            df["event_id"] = pd.to_numeric(
                df["event_id"], errors="coerce"
            ).astype("Int64")

        return df

    def _validate_input(self, df: pd.DataFrame) -> None:
        """
        Validate that the input DataFrame has all required columns.

        Fails fast with a clear error message listing exactly which
        columns are missing — far better than a cryptic KeyError
        deep inside GroupBy logic.

        Args:
            df: The loaded DataFrame.

        Raises:
            ValueError: If any required columns are missing.
        """
        required = set(self._config.required_input_columns)
        present = set(df.columns)
        missing = required - present

        if missing:
            raise ValueError(
                f"Input DataFrame is missing required columns: {sorted(missing)}. "
                f"Expected columns from Phase 3 parser: "
                f"{self._config.required_input_columns}. "
                f"Got: {sorted(df.columns.tolist())}"
            )

        # Log data quality metrics
        logger.info("Input validation passed:")
        logger.info(f"  Total records    : {len(df):,}")
        logger.info(f"  Null timestamps  : {df['timestamp'].isna().sum():,}")
        logger.info(f"  Null event_ids   : {df['event_id'].isna().sum():,}")
        logger.info(
            f"  Unique computers : {df['computer'].nunique()}"
        )
        logger.info(
            f"  Date range       : "
            f"{df['timestamp'].min()} → {df['timestamp'].max()}"
        )

    def _validate_output(self, df: pd.DataFrame) -> None:
        """
        Validate the output feature matrix for completeness and sanity.

        Checks:
          - All expected feature columns are present.
          - No NaN values in ratio columns (division-by-zero should
            produce 0.0, not NaN).
          - total_events >= 0 for all rows.

        Args:
            df: The feature matrix DataFrame.

        Raises:
            ValueError: If output validation fails.
        """
        expected_features = set(self._config.feature_columns)
        present = set(df.columns) - {"hour", "computer"}
        missing = expected_features - present

        if missing:
            raise ValueError(
                f"Output DataFrame is missing expected feature columns: "
                f"{sorted(missing)}"
            )

        # Check ratio columns for NaN (indicates a division-by-zero bug)
        ratio_cols = ["failure_rate", "admin_ratio", "process_ratio"]
        for col in ratio_cols:
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                logger.error(
                    f"VALIDATION FAILURE: {col} has {nan_count} NaN values. "
                    f"Division-by-zero handling may be broken."
                )
                raise ValueError(
                    f"Ratio column '{col}' contains {nan_count} NaN values."
                )

        # Sanity: total_events must be non-negative
        neg_count = (df["total_events"] < 0).sum()
        if neg_count > 0:
            raise ValueError(
                f"Found {neg_count} rows with negative total_events."
            )

        logger.info("Output validation passed — all 15 features present, no NaN in ratios.")

    def _save_output(self, df: pd.DataFrame) -> None:
        """
        Save the feature matrix to CSV.

        Args:
            df: The feature matrix DataFrame.
        """
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self._output_path, index=False, encoding="utf-8")
        logger.info(f"Feature matrix saved to: {self._output_path}")
        logger.info(f"  Rows    : {len(df):,}")
        logger.info(f"  Columns : {df.columns.tolist()}")

    def _log_summary(self, df: pd.DataFrame) -> None:
        """
        Log human-readable summary statistics for operator observability.

        This gives SOC engineers a quick sanity check without opening
        the CSV file.

        Args:
            df: The feature matrix DataFrame.
        """
        logger.info("")
        logger.info("--- Feature Summary Statistics ---")
        logger.info(f"  Total windows (rows)     : {len(df):,}")
        logger.info(
            f"  Unique computers         : {df['computer'].nunique()}"
        )
        logger.info(
            f"  Time range               : "
            f"{df['hour'].min()} → {df['hour'].max()}"
        )

        # Per-feature summary
        logger.info("")
        logger.info("--- Per-Feature Statistics ---")
        feature_stats = df[self._config.feature_columns].describe()
        for col in self._config.feature_columns:
            stats = feature_stats[col]
            logger.info(
                f"  {col:30s} | "
                f"min={stats['min']:>10.4f}  "
                f"mean={stats['mean']:>10.4f}  "
                f"max={stats['max']:>10.4f}  "
                f"std={stats['std']:>10.4f}"
            )

        # High-value alert counts
        logger.info("")
        logger.info("--- Security-Relevant Totals ---")
        logger.info(
            f"  Total failed logins      : "
            f"{df['failed_logins'].sum():,}"
        )
        logger.info(
            f"  Total admin events       : "
            f"{df['admin_events'].sum():,}"
        )
        logger.info(
            f"  Total service installs   : "
            f"{df['service_install_events'].sum():,}"
        )
        logger.info(
            f"  Total audit log clears   : "
            f"{df['audit_log_clears'].sum():,}"
        )
        logger.info(
            f"  Total new users created  : "
            f"{df['new_user_events'].sum():,}"
        )
        logger.info(
            f"  Total group changes      : "
            f"{df['group_membership_changes'].sum():,}"
        )


# ===========================================================================
# Synthetic Test Data Generator (for verification without real EVTX files)
# ===========================================================================


def _generate_synthetic_parsed_events(output_path: Path) -> pd.DataFrame:
    """
    Generate a synthetic parsed_events.csv for pipeline verification.

    Creates realistic-looking event data across multiple computers
    and time windows so the feature engineering pipeline can be tested
    end-to-end without requiring real EVTX files.

    This function is ONLY called when parsed_events.csv does not exist
    and the user explicitly opts in via the ``--synthetic`` flag.

    Args:
        output_path: Where to write the synthetic CSV.

    Returns:
        The generated DataFrame.
    """
    logger.info("Generating synthetic parsed events for testing...")

    np.random.seed(42)

    computers = ["HOST01", "HOST02", "DC01", "WEB-SERVER", "DB-SERVER"]
    usernames = ["admin", "jdoe", "svc_backup", "SYSTEM", "attacker01", "guest"]
    processes = [
        "C:\\Windows\\System32\\svchost.exe",
        "C:\\Windows\\System32\\cmd.exe",
        "C:\\Program Files\\app.exe",
        "C:\\temp\\malware.exe",
        "C:\\Windows\\System32\\powershell.exe",
    ]
    ips = ["192.168.1.10", "10.0.0.5", "172.16.0.100", "8.8.8.8", "203.0.113.50"]
    event_ids = [4624, 4625, 4672, 4688, 4697, 4720, 4728, 7045, 1102]

    n_records = 5000
    base_time = pd.Timestamp("2025-01-01 00:00:00", tz="UTC")

    records = []
    for _ in range(n_records):
        eid = np.random.choice(event_ids, p=[0.30, 0.15, 0.10, 0.20, 0.05, 0.03, 0.05, 0.05, 0.07])
        ts = base_time + pd.Timedelta(hours=np.random.randint(0, 72))
        ts += pd.Timedelta(minutes=np.random.randint(0, 60))

        records.append({
            "timestamp": ts,
            "event_id": int(eid),
            "computer": np.random.choice(computers),
            "channel": "Security",
            "provider": "Microsoft-Windows-Security-Auditing",
            "username": np.random.choice(usernames),
            "process_name": np.random.choice(processes),
            "ip_address": np.random.choice(ips),
            "logon_type": str(np.random.choice([2, 3, 10, ""])),
            "tactic": np.random.choice([
                "Initial_Access", "Execution", "Persistence",
                "Privilege_Escalation", "Defense_Evasion",
            ]),
            "source_file": "synthetic_test.evtx",
        })

    df = pd.DataFrame(records)
    df = df.sort_values("timestamp").reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")

    logger.info(f"Synthetic data saved: {output_path}")
    logger.info(f"  Records   : {len(df):,}")
    logger.info(f"  Computers : {df['computer'].nunique()}")
    logger.info(f"  Date range: {df['timestamp'].min()} → {df['timestamp'].max()}")

    return df


# ===========================================================================
# Standalone Script Entry Point
# ===========================================================================


def main() -> None:
    """
    Run the feature engineering pipeline as a standalone script.

    Usage:
        python ml_engine/feature_engineering.py
        python ml_engine/feature_engineering.py --synthetic

    Flags:
        --synthetic   Generate synthetic test data if parsed_events.csv
                      does not exist.  Useful for verifying the pipeline
                      without running Phase 3 on real EVTX files.

    Output:
        data/processed/features.csv
    """
    Config.ensure_directories()

    input_path = Config.PROCESSED_DIR / Config.PARSED_EVENTS_FILENAME
    output_path = Config.PROCESSED_DIR / Config.FEATURES_FILENAME

    # Handle --synthetic flag
    use_synthetic = "--synthetic" in sys.argv

    if not input_path.exists():
        if use_synthetic:
            logger.info("parsed_events.csv not found — generating synthetic data.")
            _generate_synthetic_parsed_events(input_path)
        else:
            logger.error(
                f"Input file not found: {input_path}\n"
                f"Options:\n"
                f"  1. Run Phase 3 first:  python ml_engine/parser.py\n"
                f"  2. Generate test data: python ml_engine/feature_engineering.py --synthetic"
            )
            sys.exit(1)

    # Run the pipeline
    pipeline = FeatureEngineeringPipeline(
        input_path=input_path,
        output_path=output_path,
    )

    try:
        features_df = pipeline.run()
    except (FileNotFoundError, ValueError) as exc:
        logger.error(f"Pipeline failed: {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}", exc_info=True)
        sys.exit(1)

    if features_df.empty:
        logger.error("Pipeline produced an empty feature matrix.")
        sys.exit(1)

    # Print sample rows for quick verification
    logger.info("")
    logger.info("--- Sample Output (first 5 rows) ---")
    sample = features_df.head(5).to_string(index=False)
    for line in sample.split("\n"):
        logger.info(f"  {line}")

    logger.info(f"\nFeature matrix saved to: {output_path}")


if __name__ == "__main__":
    main()
