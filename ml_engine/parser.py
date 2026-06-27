"""
ml_engine/parser.py
====================
EVTX Parser Module — Phase 3 Implementation.

PURPOSE:
  Converts binary Windows Event Log (.evtx) files into structured
  Pandas DataFrames ready for feature engineering.

ARCHITECTURE:
  EVTXRecordParser  — Parses a single XML event record string → dict
  EVTXFileParser    — Parses a single .evtx file → pd.DataFrame
  EVTXBatchParser   — Iterates all files in raw_logs/ → merged DataFrame

WHY THREE CLASSES:
  Each class has a single responsibility and can be unit-tested
  independently. EVTXFileParser can be used standalone by the Flask API
  (upload + parse on demand). EVTXBatchParser is used for training.

KEY DESIGN DECISIONS:
  - XML namespace is handled explicitly — Windows Event Log XML has a
    default namespace that must be declared for ElementTree queries.
  - Both Security (4624, 4625, ...) and Sysmon (1, 3, 7, ...) events
    are supported via a field extraction priority system.
  - Corrupt/unreadable records are skipped with a warning — one bad
    record must never abort an entire file.
  - Output CSV is deterministically sorted by timestamp for reproducibility.

USAGE (as a module):
  from parser import EVTXBatchParser
  from config import Config
  parser = EVTXBatchParser()
  df = parser.parse_all(Config.RAW_LOGS_DIR)

USAGE (as a script):
  python -m ml_engine.parser
  → writes data/processed/parsed_events.csv
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
import pandas as pd

from .config import Config
from .logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Try importing python-evtx
# ---------------------------------------------------------------------------

try:
    import Evtx.Evtx as evtx
    EVTX_AVAILABLE = True
except ImportError:
    EVTX_AVAILABLE = False
    logger.error(
        "python-evtx is not installed. Install with: pip install python-evtx"
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Windows Event Log XML default namespace.
# ALL element queries must be prefixed with this.
_NS = "http://schemas.microsoft.com/win/2004/08/events/event"
_NSP = f"{{{_NS}}}"  # Shorthand: "{http://...}"

# Regex to extract EventID from both formats:
#   <EventID>4624</EventID>
#   <EventID Qualifiers="">4624</EventID>
_EVENT_ID_RE = re.compile(r'<EventID[^>]*>(\d+)</EventID>')

# Columns in the final output DataFrame (order matters for CSV)
OUTPUT_COLUMNS = [
    "timestamp",
    "event_id",
    "computer",
    "channel",
    "provider",
    "username",
    "process_name",
    "ip_address",
    "logon_type",
    "tactic",
    "source_file",
]


# ---------------------------------------------------------------------------
# EVTXRecordParser
# ---------------------------------------------------------------------------


class EVTXRecordParser:
    """
    Parses a single EVTX XML record string into a flat Python dict.

    WHY STANDALONE:
      Isolating record-level parsing allows unit testing with raw XML
      strings without needing a real .evtx file. The Flask API can
      also parse individual records sent as JSON payloads.

    Supports both:
      - Windows Security Auditing events (channel: Security)
      - Microsoft-Windows-Sysmon events (channel: Sysmon/Operational)

    Args:
        tactic:      MITRE ATT&CK tactic label for this record's file.
        source_file: Filename the record originated from.
    """

    def __init__(self, tactic: str = "Unknown", source_file: str = "") -> None:
        self._tactic = tactic
        self._source_file = source_file

    def parse(self, xml_str: str) -> Optional[dict]:
        """
        Parse one XML event record into a flat dict.

        Args:
            xml_str: Raw XML string from python-evtx record.xml().

        Returns:
            Dict with keys matching OUTPUT_COLUMNS, or None on parse failure.
        """
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as exc:
            logger.debug(f"XML parse failed: {exc}")
            return None

        system = root.find(f"{_NSP}System")
        if system is None:
            logger.debug("Record missing <System> element — skipping")
            return None

        # ------------------------------------------------------------------
        # System fields — present in every well-formed event record
        # ------------------------------------------------------------------

        event_id = self._extract_event_id(xml_str)
        timestamp = self._extract_timestamp(system)
        computer = self._get_text(system, f"{_NSP}Computer")
        channel = self._get_text(system, f"{_NSP}Channel")
        provider_el = system.find(f"{_NSP}Provider")
        provider = provider_el.get("Name", "") if provider_el is not None else ""

        # ------------------------------------------------------------------
        # EventData fields — vary by event source and ID
        # ------------------------------------------------------------------

        event_data = root.find(f"{_NSP}EventData")
        data_map = self._build_data_map(event_data)

        username = self._extract_username(data_map)
        process_name = self._extract_process_name(data_map)
        ip_address = self._extract_ip_address(data_map)
        logon_type = data_map.get("LogonType", "")

        return {
            "timestamp":    timestamp,
            "event_id":     event_id,
            "computer":     computer,
            "channel":      channel,
            "provider":     provider,
            "username":     username,
            "process_name": process_name,
            "ip_address":   ip_address,
            "logon_type":   logon_type,
            "tactic":       self._tactic,
            "source_file":  self._source_file,
        }

    # ------------------------------------------------------------------
    # Private extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_event_id(xml_str: str) -> Optional[int]:
        """
        Extract Event ID using regex — handles Qualifiers attribute.

        The EVTX XML format uses two forms:
          <EventID>4624</EventID>            (Security log)
          <EventID Qualifiers="">4624</EventID>  (System/Application logs)

        A plain string search on '<EventID>' misses the second form.
        """
        match = _EVENT_ID_RE.search(xml_str)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_timestamp(system: ET.Element) -> Optional[str]:
        """
        Extract ISO 8601 timestamp from <TimeCreated SystemTime="..."/>.

        Returns:
            Timestamp string in the form "2019-11-18T11:47:59.000000Z",
            or None if the element is absent.
        """
        tc = system.find(f"{_NSP}TimeCreated")
        if tc is not None:
            return tc.get("SystemTime", None)
        return None

    @staticmethod
    def _get_text(parent: ET.Element, tag: str, default: str = "") -> str:
        """Safely get text content of a child element."""
        el = parent.find(tag)
        if el is not None and el.text:
            return el.text.strip()
        return default

    @staticmethod
    def _build_data_map(event_data: Optional[ET.Element]) -> dict:
        """
        Build a Name → Value dict from <EventData><Data Name="...">...</Data>.

        This is the standard structure for both Security and Sysmon events.
        The field names differ by provider, so we return all of them and
        let the extraction methods pick what they need.

        Args:
            event_data: The <EventData> element, or None if absent.

        Returns:
            Dict mapping Data/@Name → Data.text (empty string if no text).
        """
        if event_data is None:
            return {}

        data_map = {}
        for data_el in event_data.findall(f"{_NSP}Data"):
            name = data_el.get("Name", "")
            value = data_el.text or ""
            if name:
                data_map[name] = value.strip()

        return data_map

    @staticmethod
    def _extract_username(data_map: dict) -> str:
        """
        Extract username, trying multiple field names in priority order.

        Priority:
          1. TargetUserName  — Security events (4624: who logged in)
          2. SubjectUserName — Security events (actor who performed action)
          3. User            — Sysmon events (e.g., Event ID 1, 3, 10)

        Filters out system accounts and empty values:
          - "-" or "ANONYMOUS LOGON" are not meaningful usernames
          - Machine accounts ending in "$" are kept (may indicate lateral move)
        """
        for field in ("TargetUserName", "SubjectUserName", "User"):
            value = data_map.get(field, "").strip()
            if value and value not in ("-", "", "ANONYMOUS LOGON"):
                return value
        return ""

    @staticmethod
    def _extract_process_name(data_map: dict) -> str:
        """
        Extract process name, trying multiple field names in priority order.

        Priority:
          1. NewProcessName   — Security Event 4688 (process creation)
          2. Image            — Sysmon Event 1 (process creation)
          3. ProcessName      — Generic fallback
          4. Application      — Some application log sources

        Returns the full executable path as logged.
        """
        for field in ("NewProcessName", "Image", "ProcessName", "Application"):
            value = data_map.get(field, "").strip()
            if value and value != "-":
                return value
        return ""

    @staticmethod
    def _extract_ip_address(data_map: dict) -> str:
        """
        Extract IP address, trying multiple field names.

        Priority:
          1. IpAddress         — Security events (4624, 4625: source IP)
          2. SourceIp          — Sysmon Event 3 (network connect)
          3. DestinationIp     — Sysmon Event 3 (outbound connections)

        Filters out loopback and empty values.
        """
        for field in ("IpAddress", "SourceIp", "DestinationIp"):
            value = data_map.get(field, "").strip()
            if value and value not in ("-", "", "::1", "127.0.0.1"):
                return value
        return ""


# ---------------------------------------------------------------------------
# EVTXFileParser
# ---------------------------------------------------------------------------


class EVTXFileParser:
    """
    Parses a single .evtx file into a Pandas DataFrame.

    Responsibilities:
      - Open the binary EVTX file using python-evtx
      - Iterate all records, delegating XML parsing to EVTXRecordParser
      - Handle corrupt/unreadable records gracefully (skip, don't abort)
      - Tag each record with its tactic (derived from parent folder name)
      - Return a clean DataFrame with typed columns

    Args:
        record_parser_class: Injectable parser class for testability.
                             Defaults to EVTXRecordParser.
    """

    def __init__(self, record_parser_class=None) -> None:
        self._record_parser_class = record_parser_class or EVTXRecordParser

    def parse(self, file_path: Path) -> pd.DataFrame:
        """
        Parse a single .evtx file into a DataFrame.

        Args:
            file_path: Absolute path to the .evtx file.

        Returns:
            DataFrame with OUTPUT_COLUMNS. Empty DataFrame on failure.

        Raises:
            ValueError: If python-evtx is not installed.
        """
        if not EVTX_AVAILABLE:
            raise ValueError(
                "python-evtx is not installed. "
                "Install with: pip install python-evtx"
            )

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return self._empty_dataframe()

        # Derive tactic label from the parent directory name
        tactic = file_path.parent.name
        source_file = file_path.name

        record_parser = self._record_parser_class(
            tactic=tactic,
            source_file=source_file,
        )

        records = []
        total_records = 0
        skipped_records = 0

        logger.info(f"Parsing: {file_path.name} (tactic: {tactic})")

        try:
            with evtx.Evtx(str(file_path)) as log:
                for record in log.records():
                    total_records += 1
                    try:
                        xml_str = record.xml()
                        parsed = record_parser.parse(xml_str)
                        if parsed is not None:
                            records.append(parsed)
                        else:
                            skipped_records += 1
                    except Exception as exc:
                        skipped_records += 1
                        logger.debug(
                            f"Skipped record {total_records} in "
                            f"{source_file}: {exc}"
                        )
                        continue

        except Exception as exc:
            logger.error(f"Failed to open {file_path}: {exc}", exc_info=True)
            return self._empty_dataframe()

        logger.info(
            f"  Parsed {len(records)} records "
            f"({skipped_records} skipped) from {source_file}"
        )

        if not records:
            logger.warning(f"  No records extracted from {source_file}")
            return self._empty_dataframe()

        df = pd.DataFrame(records, columns=OUTPUT_COLUMNS)
        return self._cast_types(df)

    @staticmethod
    def _empty_dataframe() -> pd.DataFrame:
        """Return an empty DataFrame with the correct schema."""
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    @staticmethod
    def _cast_types(df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply correct dtypes to the DataFrame.

        WHY:
          - timestamp as datetime enables time-based grouping in Phase 4
          - event_id as Int64 (nullable int) allows NaN without dtype issues
          - String columns as object (Pandas default) for now
        """
        try:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        except Exception as exc:
            logger.warning(f"Timestamp conversion warning: {exc}")

        try:
            df["event_id"] = pd.to_numeric(df["event_id"], errors="coerce").astype("Int64")
        except Exception as exc:
            logger.warning(f"Event ID type conversion warning: {exc}")

        # Replace truly empty strings with NaN for cleaner downstream handling
        string_cols = ["computer", "channel", "provider", "username",
                       "process_name", "ip_address", "logon_type",
                       "tactic", "source_file"]
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].replace("", pd.NA)

        return df


# ---------------------------------------------------------------------------
# EVTXBatchParser
# ---------------------------------------------------------------------------


class EVTXBatchParser:
    """
    Iterates all .evtx files under a root directory and combines them
    into a single unified DataFrame.

    WHY SEPARATE FROM EVTXFileParser:
      - Single responsibility: file discovery is distinct from file parsing
      - Enables parallel parsing in the future (multiprocessing.Pool)
      - Allows the training pipeline to call parse_all() with one line

    Args:
        file_parser_class: Injectable parser class for testability.
    """

    def __init__(self, file_parser_class=None) -> None:
        self._file_parser_class = file_parser_class or EVTXFileParser

    def parse_all(self, raw_logs_dir: Path) -> pd.DataFrame:
        """
        Discover and parse all .evtx files under raw_logs_dir.

        Args:
            raw_logs_dir: Root directory to recursively scan.

        Returns:
            Combined DataFrame of all parsed records, sorted by timestamp.
            Empty DataFrame if no files are found or all fail.
        """
        evtx_files = sorted(raw_logs_dir.rglob("*.evtx"))

        if not evtx_files:
            logger.error(
                f"No .evtx files found under {raw_logs_dir}. "
                "Run scripts/download_dataset.py first."
            )
            return EVTXFileParser._empty_dataframe()

        logger.info("=" * 60)
        logger.info(f"Batch parsing {len(evtx_files)} .evtx files")
        logger.info(f"Root directory: {raw_logs_dir}")
        logger.info("=" * 60)

        file_parser = self._file_parser_class()
        dataframes = []
        parse_errors = 0

        for i, file_path in enumerate(evtx_files, start=1):
            logger.info(f"[{i:3d}/{len(evtx_files)}] {file_path.relative_to(raw_logs_dir)}")
            try:
                df = file_parser.parse(file_path)
                if not df.empty:
                    dataframes.append(df)
                else:
                    logger.warning(f"  Empty result for {file_path.name}")
            except Exception as exc:
                parse_errors += 1
                logger.error(f"  Failed to parse {file_path.name}: {exc}", exc_info=True)

        if not dataframes:
            logger.error("No data extracted from any file.")
            return EVTXFileParser._empty_dataframe()

        logger.info("Combining all parsed DataFrames...")
        combined = pd.concat(dataframes, ignore_index=True)

        # Sort by timestamp for deterministic ordering
        if "timestamp" in combined.columns:
            combined = combined.sort_values("timestamp", na_position="last")
            combined = combined.reset_index(drop=True)

        logger.info("=" * 60)
        logger.info("BATCH PARSE COMPLETE")
        logger.info(f"  Total files     : {len(evtx_files)}")
        logger.info(f"  Files succeeded : {len(dataframes)}")
        logger.info(f"  Files failed    : {parse_errors}")
        logger.info(f"  Total records   : {len(combined):,}")
        logger.info(f"  Unique Event IDs: {combined['event_id'].nunique()}")
        logger.info(f"  Unique computers: {combined['computer'].nunique()}")
        logger.info(f"  Tactics covered : {combined['tactic'].nunique()}")
        logger.info("=" * 60)

        return combined

    def parse_and_save(
        self,
        raw_logs_dir: Path,
        output_path: Path,
    ) -> pd.DataFrame:
        """
        Parse all files and save the result to a CSV file.

        Args:
            raw_logs_dir: Root directory of .evtx files.
            output_path:  Destination CSV path.

        Returns:
            The combined DataFrame (also saved to disk).
        """
        df = self.parse_all(raw_logs_dir)

        if df.empty:
            logger.error("Nothing to save — DataFrame is empty.")
            return df

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, encoding="utf-8")
        logger.info(f"Saved parsed events: {output_path}")
        logger.info(f"  Rows    : {len(df):,}")
        logger.info(f"  Columns : {list(df.columns)}")

        return df


# ---------------------------------------------------------------------------
# Standalone Script Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Run the batch parser as a standalone script.

    Usage:
        python -m ml_engine.parser

    Output:
        data/processed/parsed_events.csv
    """
    Config.ensure_directories()

    output_path = Config.PROCESSED_DIR / "parsed_events.csv"

    logger.info("EVTX Batch Parser — Phase 3")
    logger.info(f"Input  : {Config.RAW_LOGS_DIR}")
    logger.info(f"Output : {output_path}")

    batch_parser = EVTXBatchParser()
    df = batch_parser.parse_and_save(
        raw_logs_dir=Config.RAW_LOGS_DIR,
        output_path=output_path,
    )

    if df.empty:
        logger.error("Parsing produced no output. Check logs above.")
        sys.exit(1)

    # Print a quick preview of event ID distribution
    logger.info("\n--- Event ID Distribution (top 15) ---")
    eid_counts = (
        df["event_id"]
        .value_counts()
        .head(15)
        .reset_index()
    )
    eid_counts.columns = ["event_id", "count"]
    for _, row in eid_counts.iterrows():
        logger.info(f"  Event {int(row['event_id']):5d} : {int(row['count']):>6,} records")

    logger.info("\n--- Tactic Distribution ---")
    tactic_counts = df["tactic"].value_counts()
    for tactic, count in tactic_counts.items():
        logger.info(f"  {tactic:<35} : {count:>5,} records")

    logger.info(f"\nParsed events saved to: {output_path}")


if __name__ == "__main__":
    main()
