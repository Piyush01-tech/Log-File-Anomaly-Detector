"""
scripts/validate_dataset.py
============================
Dataset Validation Script for Phase 2.

PURPOSE:
  After downloading .evtx files, this script validates every file in
  data/raw_logs/ and produces a structured inventory report.

WHAT IT CHECKS:
  1. File can be opened as a valid EVTX binary
  2. File contains at least one event record
  3. File size is non-zero
  4. Reports Event ID distribution per file

WHY THIS EXISTS:
  - EVTX files can be truncated or corrupted during download.
  - We need to know BEFORE training which files are healthy.
  - The inventory CSV becomes the input to the parser in Phase 3.
  - Gives you visibility into how many events of each monitored
    Event ID are present in your dataset.

USAGE:
  python scripts/validate_dataset.py

OUTPUT:
  data/processed/dataset_inventory.csv  ← One row per .evtx file
  Console summary of Event ID coverage

REQUIREMENTS:
  pip install python-evtx pandas
"""

import sys
import csv
from pathlib import Path
from typing import Optional
from collections import Counter
from datetime import datetime

# ---------------------------------------------------------------------------
# Path Setup
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "ml_engine"))

from logger import get_logger  # noqa: E402
from config import Config      # noqa: E402

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Try importing python-evtx
# ---------------------------------------------------------------------------

try:
    import Evtx.Evtx as evtx
    import Evtx.Views as e_views
    EVTX_AVAILABLE = True
except ImportError:
    EVTX_AVAILABLE = False
    logger.warning(
        "python-evtx is not installed. File structure checks will run, "
        "but Event ID extraction will be skipped.\n"
        "Install with: pip install python-evtx"
    )

# ---------------------------------------------------------------------------
# EVTX File Validator
# ---------------------------------------------------------------------------


class EVTXFileValidator:
    """
    Validates a single .evtx file and extracts summary statistics.

    Responsibilities:
      - Check file is readable and non-empty
      - Attempt to open as valid EVTX binary
      - Count total records
      - Count monitored Event IDs (defined in Config)
      - Return a structured result dict

    Args:
        file_path: Absolute path to the .evtx file.
        monitored_event_ids: Set of Event IDs to count specifically.
    """

    def __init__(
        self,
        file_path: Path,
        monitored_event_ids: Optional[set] = None,
    ) -> None:
        self._path = file_path
        self._monitored_ids = monitored_event_ids or set(Config.MONITORED_EVENT_IDS)

    def validate(self) -> dict:
        """
        Perform all validation checks and return a result record.

        Returns:
            A dict with keys:
              filename, tactic, size_bytes, is_valid, total_records,
              error_message, <one key per monitored Event ID>
        """
        result = {
            "filename": self._path.name,
            "tactic": self._path.parent.name,
            "relative_path": str(self._path.relative_to(Config.RAW_LOGS_DIR)),
            "size_bytes": 0,
            "is_valid": False,
            "total_records": 0,
            "error_message": "",
        }

        # Initialize Event ID columns to 0
        for eid in sorted(self._monitored_ids):
            result[f"event_{eid}"] = 0

        # --- Check 1: File exists and is non-empty ---
        try:
            if not self._path.exists():
                result["error_message"] = "File does not exist"
                return result

            size = self._path.stat().st_size
            result["size_bytes"] = size

            if size == 0:
                result["error_message"] = "File is empty (0 bytes)"
                return result

        except OSError as exc:
            result["error_message"] = f"OS error: {exc}"
            return result

        # --- Check 2: EVTX parsing ---
        if not EVTX_AVAILABLE:
            # Mark as structurally valid based on file size alone
            result["is_valid"] = True
            result["error_message"] = "python-evtx not installed — skipped parse check"
            return result

        try:
            event_id_counter = Counter()
            total_records = 0

            with evtx.Evtx(str(self._path)) as log:
                for record in log.records():
                    try:
                        # Parse the XML record to extract Event ID
                        xml_str = record.xml()
                        event_id = self._extract_event_id(xml_str)
                        if event_id is not None:
                            event_id_counter[event_id] += 1
                        total_records += 1
                    except Exception:
                        # Some records may be corrupt — count them but skip
                        total_records += 1
                        continue

            result["total_records"] = total_records
            result["is_valid"] = total_records > 0

            # Fill in monitored Event ID counts
            for eid in self._monitored_ids:
                result[f"event_{eid}"] = event_id_counter.get(eid, 0)

            if total_records == 0:
                result["error_message"] = "File opened but contains 0 records"

        except Exception as exc:
            result["error_message"] = f"EVTX parse error: {exc}"
            result["is_valid"] = False

        return result

    @staticmethod
    def _extract_event_id(xml_str: str) -> Optional[int]:
        """
        Extract the EventID value from an EVTX record's XML string.

        WHY REGEX:
          python-evtx renders EventID tags in two forms depending on the
          log source:
            - <EventID>4624</EventID>           (Security log)
            - <EventID Qualifiers="">4624</EventID>  (Application/System logs)
          A plain string search for '<EventID>' misses the second form.
          A regex pattern '<EventID[^>]*>' handles both safely.

        Args:
            xml_str: Raw XML string from python-evtx.

        Returns:
            Integer Event ID, or None if extraction fails.
        """
        import re
        try:
            # Matches both <EventID> and <EventID Qualifiers="...">
            match = re.search(r'<EventID[^>]*>(\d+)</EventID>', xml_str)
            if match:
                return int(match.group(1))
            return None
        except (ValueError, AttributeError):
            return None


# ---------------------------------------------------------------------------
# Dataset Inventory Builder
# ---------------------------------------------------------------------------


class DatasetInventoryBuilder:
    """
    Discovers all .evtx files under the raw_logs directory,
    validates each one, and writes a CSV inventory report.

    Args:
        raw_logs_dir:  Root directory containing tactic subdirectories.
        output_dir:    Directory to write the inventory CSV.
    """

    def __init__(self, raw_logs_dir: Path, output_dir: Path) -> None:
        self._raw_logs_dir = raw_logs_dir
        self._output_dir = output_dir

    def run(self) -> None:
        """
        Discover all .evtx files, validate them, and write the inventory.
        """
        logger.info("=" * 60)
        logger.info("EVTX Dataset Validator — Phase 2")
        logger.info(f"Scanning: {self._raw_logs_dir}")
        logger.info("=" * 60)

        evtx_files = sorted(self._raw_logs_dir.rglob("*.evtx"))

        if not evtx_files:
            logger.error(
                f"No .evtx files found in {self._raw_logs_dir}.\n"
                "Run scripts/download_dataset.py first."
            )
            return

        logger.info(f"Found {len(evtx_files)} .evtx files. Validating...\n")

        results = []
        valid_count = 0
        invalid_count = 0

        for i, file_path in enumerate(evtx_files, start=1):
            logger.info(f"[{i:3d}/{len(evtx_files)}] {file_path.relative_to(self._raw_logs_dir)}")
            validator = EVTXFileValidator(file_path)
            result = validator.validate()
            results.append(result)

            if result["is_valid"]:
                valid_count += 1
                logger.info(
                    f"         [OK] VALID -- {result['total_records']:,} records, "
                    f"{result['size_bytes']:,} bytes"
                )
            else:
                invalid_count += 1
                logger.warning(f"         [INVALID] -- {result['error_message']}")

        # Write CSV inventory
        inventory_path = self._write_inventory(results)

        # Print Event ID coverage summary
        self._print_coverage_summary(results)

        logger.info("\n" + "=" * 60)
        logger.info("VALIDATION COMPLETE")
        logger.info(f"  Valid files   : {valid_count}")
        logger.info(f"  Invalid files : {invalid_count}")
        logger.info(f"  Inventory CSV : {inventory_path}")
        logger.info("=" * 60)

        if invalid_count > 0:
            logger.warning(
                f"{invalid_count} invalid file(s) found. These will be "
                "excluded from parsing in Phase 3."
            )

    def _write_inventory(self, results: list[dict]) -> Path:
        """
        Write validation results to a CSV file.

        Args:
            results: List of result dicts from EVTXFileValidator.validate().

        Returns:
            Path to the written CSV file.
        """
        if not results:
            logger.warning("No results to write.")
            return self._output_dir / "dataset_inventory.csv"

        self._output_dir.mkdir(parents=True, exist_ok=True)
        inventory_path = self._output_dir / "dataset_inventory.csv"

        fieldnames = list(results[0].keys())

        try:
            with open(inventory_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)
            logger.info(f"Inventory written: {inventory_path}")
        except IOError as exc:
            logger.error(f"Failed to write inventory CSV: {exc}")

        return inventory_path

    def _print_coverage_summary(self, results: list[dict]) -> None:
        """
        Print a table showing how many files contain each monitored Event ID.

        Args:
            results: List of result dicts from EVTXFileValidator.validate().
        """
        valid_results = [r for r in results if r["is_valid"]]

        if not valid_results:
            logger.warning("No valid files — cannot generate coverage summary.")
            return

        logger.info("\n--- Monitored Event ID Coverage (valid files only) ---")
        logger.info(f"{'Event ID':<12} {'Files Containing It':<22} {'Total Records':<15}")
        logger.info("-" * 52)

        for eid in sorted(Config.MONITORED_EVENT_IDS):
            col = f"event_{eid}"
            files_with_event = sum(1 for r in valid_results if r.get(col, 0) > 0)
            total_records = sum(r.get(col, 0) for r in valid_results)
            logger.info(f"{eid:<12} {files_with_event:<22} {total_records:<15,}")

        logger.info("")
        total_events = sum(r.get("total_records", 0) for r in valid_results)
        logger.info(f"Total event records across all valid files: {total_events:,}")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main entry point."""
    Config.ensure_directories()

    builder = DatasetInventoryBuilder(
        raw_logs_dir=Config.RAW_LOGS_DIR,
        output_dir=Config.PROCESSED_DIR,
    )
    builder.run()


if __name__ == "__main__":
    main()
