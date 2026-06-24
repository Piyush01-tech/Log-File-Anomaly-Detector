"""
scripts/download_dataset.py
============================
Dataset Acquisition Script for Phase 2.

PURPOSE:
  Downloads Windows Event Log attack samples (.evtx) from the
  sbousseaden/EVTX-ATTACK-SAMPLES GitHub repository.

WHY THIS EXISTS:
  - Reproducible dataset acquisition — any team member can re-run this
    to get the exact same files.
  - Organized by MITRE ATT&CK tactic — files land in named subdirectories
    so the parser can tag each record with its attack category.
  - Retry logic and proper error handling — robust enough for CI/CD pipelines.

USAGE:
  # From project root, with venv activated:
  python scripts/download_dataset.py

  # Download only specific tactics:
  python scripts/download_dataset.py --tactics CredentialAccess Execution

  # Dry run (list files without downloading):
  python scripts/download_dataset.py --dry-run

REQUIREMENTS:
  pip install requests python-dotenv
  A GitHub Personal Access Token is OPTIONAL but raises the API rate
  limit from 60 → 5000 requests/hour. Set GITHUB_TOKEN in your .env

OUTPUT:
  data/raw_logs/
  ├── CredentialAccess/
  │   ├── *.evtx
  ├── Execution/
  │   ├── *.evtx
  └── ...
"""

import argparse
import sys
import time
import hashlib
import json
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
import os

# ---------------------------------------------------------------------------
# Path Setup — works regardless of where the script is run from
# ---------------------------------------------------------------------------

# Project root is the parent of the 'scripts/' directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add ml_engine to sys.path so we can import our shared modules
sys.path.insert(0, str(PROJECT_ROOT / "ml_engine"))

from logger import get_logger  # noqa: E402  (after sys.path modification)
from config import Config      # noqa: E402

# Load environment variables from .env in project root
load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_API_BASE = "https://api.github.com"
REPO_OWNER = "sbousseaden"
REPO_NAME = "EVTX-ATTACK-SAMPLES"

# MITRE ATT&CK tactic folders present in the repository.
# Names match exactly what appears in the GitHub repo (spaces included).
# Each maps to a local subfolder inside data/raw_logs/ with the same name.
TACTIC_FOLDERS = [
    "Credential Access",
    "Defense Evasion",
    "Discovery",
    "Execution",
    "Lateral Movement",
    "Persistence",
    "Privilege Escalation",
    "AutomatedTestingTools",
    "Command and Control",
    "Other",
]

# Maximum files to download per tactic (keeps data/ manageable for dev).
# Set to None to download everything.
MAX_FILES_PER_TACTIC: Optional[int] = 5

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2  # Exponential backoff base

# Download chunk size for streaming large .evtx files
DOWNLOAD_CHUNK_SIZE = 8192  # 8 KB


# ---------------------------------------------------------------------------
# GitHub API Client
# ---------------------------------------------------------------------------


class GitHubAPIClient:
    """
    Lightweight GitHub REST API client for listing and downloading
    repository contents.

    Handles:
      - Optional Bearer token authentication
      - Rate limit detection with informative error messages
      - JSON response parsing

    Args:
        token: Optional GitHub Personal Access Token.
               Set GITHUB_TOKEN in .env to avoid unauthenticated rate limits.
    """

    def __init__(self, token: Optional[str] = None) -> None:
        self._token = token or os.getenv("GITHUB_TOKEN")
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Log-File-Anomaly-Detector/1.0",
        })
        if self._token:
            self._session.headers["Authorization"] = f"Bearer {self._token}"
            logger.info("GitHub API: Authenticated mode (5000 req/hr limit)")
        else:
            logger.warning(
                "GitHub API: Unauthenticated mode (60 req/hr limit). "
                "Set GITHUB_TOKEN in .env to increase this limit."
            )

    def list_contents(self, path: str = "") -> list[dict]:
        """
        List the contents of a directory in the repository.

        Args:
            path: Repository-relative path (e.g., "CredentialAccess").
                  Empty string returns root contents.

        Returns:
            List of GitHub content objects (dicts with name, type,
            download_url, sha, size fields).

        Raises:
            requests.HTTPError: On non-200 responses (including rate limits).
        """
        url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
        logger.debug(f"GET {url}")
        response = self._session.get(url, timeout=30)

        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining", "?")
            reset_time = response.headers.get("X-RateLimit-Reset", "?")
            logger.error(
                f"GitHub API rate limit hit. Remaining: {remaining}. "
                f"Resets at: {reset_time}. Set GITHUB_TOKEN in .env"
            )
            response.raise_for_status()

        response.raise_for_status()
        return response.json()

    def download_file(self, download_url: str, dest_path: Path) -> int:
        """
        Stream-download a file from a raw GitHub URL to a local path.

        Args:
            download_url: The raw content URL from the GitHub API response.
            dest_path:    Absolute local path to save the file.

        Returns:
            Number of bytes written.

        Raises:
            requests.HTTPError: On download failures.
            IOError: On filesystem write failures.
        """
        response = self._session.get(download_url, stream=True, timeout=60)
        response.raise_for_status()

        bytes_written = 0
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    bytes_written += len(chunk)

        return bytes_written

    def close(self) -> None:
        """Close the underlying requests session."""
        self._session.close()


# ---------------------------------------------------------------------------
# Dataset Downloader
# ---------------------------------------------------------------------------


class DatasetDownloader:
    """
    Orchestrates the discovery and download of EVTX attack samples.

    Responsibilities:
      - Iterate over configured tactic folders
      - Filter for .evtx files
      - Download with retry and exponential backoff
      - Record a download manifest (JSON) for audit and reproducibility
      - Skip already-downloaded files (idempotent)

    Args:
        output_dir:         Root directory to write files into.
        tactics:            List of tactic folder names to download.
                            Defaults to all TACTIC_FOLDERS.
        max_per_tactic:     Cap on files per tactic. None = unlimited.
        dry_run:            If True, list files but do not download.
        github_client:      Injected GitHubAPIClient instance.
    """

    def __init__(
        self,
        output_dir: Path,
        tactics: list[str],
        max_per_tactic: Optional[int],
        dry_run: bool,
        github_client: GitHubAPIClient,
    ) -> None:
        self._output_dir = output_dir
        self._tactics = tactics
        self._max_per_tactic = max_per_tactic
        self._dry_run = dry_run
        self._client = github_client

        # Manifest: records every file encountered and its download status
        self._manifest: list[dict] = []

    def run(self) -> None:
        """
        Main entry point. Iterates all tactics and downloads EVTX files.
        Writes a manifest JSON file on completion.
        """
        logger.info("=" * 60)
        logger.info("EVTX Dataset Downloader — Phase 2")
        logger.info(f"Repository  : {REPO_OWNER}/{REPO_NAME}")
        logger.info(f"Output dir  : {self._output_dir}")
        logger.info(f"Tactics     : {self._tactics}")
        logger.info(f"Max/tactic  : {self._max_per_tactic or 'unlimited'}")
        logger.info(f"Dry run     : {self._dry_run}")
        logger.info("=" * 60)

        total_downloaded = 0
        total_skipped = 0
        total_errors = 0

        for tactic in self._tactics:
            logger.info(f"\n[TACTIC] {tactic}")
            downloaded, skipped, errors = self._process_tactic(tactic)
            total_downloaded += downloaded
            total_skipped += skipped
            total_errors += errors

        # Write manifest
        self._write_manifest()

        logger.info("\n" + "=" * 60)
        logger.info("DOWNLOAD COMPLETE")
        logger.info(f"  Downloaded : {total_downloaded} files")
        logger.info(f"  Skipped    : {total_skipped} files (already existed)")
        logger.info(f"  Errors     : {total_errors} files")
        logger.info(f"  Manifest   : {self._output_dir / 'download_manifest.json'}")
        logger.info("=" * 60)

        if total_errors > 0:
            logger.warning(
                f"{total_errors} file(s) failed to download. "
                "Check logs above and re-run to retry."
            )

    def _process_tactic(self, tactic: str) -> tuple[int, int, int]:
        """
        List and download all EVTX files for a single tactic folder.

        Args:
            tactic: Tactic folder name (e.g., "CredentialAccess").

        Returns:
            Tuple of (downloaded_count, skipped_count, error_count).
        """
        downloaded = skipped = errors = 0

        try:
            contents = self._client.list_contents(path=tactic)
        except requests.HTTPError as exc:
            logger.error(f"  Failed to list contents of '{tactic}': {exc}")
            return 0, 0, 1
        except Exception as exc:
            logger.error(f"  Unexpected error listing '{tactic}': {exc}", exc_info=True)
            return 0, 0, 1

        # Filter to .evtx files only
        evtx_files = [
            item for item in contents
            if item.get("type") == "file"
            and item.get("name", "").lower().endswith(".evtx")
        ]

        if not evtx_files:
            logger.warning(f"  No .evtx files found in '{tactic}'")
            return 0, 0, 0

        # Apply per-tactic cap
        if self._max_per_tactic is not None:
            evtx_files = evtx_files[: self._max_per_tactic]

        logger.info(f"  Found {len(evtx_files)} .evtx file(s) to process")

        tactic_dir = self._output_dir / tactic

        for item in evtx_files:
            filename = item["name"]
            download_url = item.get("download_url")
            file_size = item.get("size", 0)
            dest_path = tactic_dir / filename

            record = {
                "tactic": tactic,
                "filename": filename,
                "size_bytes": file_size,
                "dest_path": str(dest_path),
                "status": None,
            }

            if self._dry_run:
                logger.info(f"  [DRY RUN] Would download: {filename} ({file_size:,} bytes)")
                record["status"] = "dry_run"
                self._manifest.append(record)
                continue

            # Skip already-downloaded files (idempotent)
            if dest_path.exists():
                logger.info(f"  [SKIP] {filename} — already exists")
                record["status"] = "skipped"
                self._manifest.append(record)
                skipped += 1
                continue

            if not download_url:
                logger.error(f"  [ERROR] No download_url for {filename}")
                record["status"] = "error_no_url"
                self._manifest.append(record)
                errors += 1
                continue

            # Download with retry
            success = self._download_with_retry(filename, download_url, dest_path)

            if success:
                record["status"] = "downloaded"
                record["sha256"] = self._sha256(dest_path)
                downloaded += 1
            else:
                record["status"] = "error_download_failed"
                errors += 1

            self._manifest.append(record)

        return downloaded, skipped, errors

    def _download_with_retry(
        self,
        filename: str,
        download_url: str,
        dest_path: Path,
    ) -> bool:
        """
        Download a file with exponential backoff retry.

        Args:
            filename:     Display name for logging.
            download_url: GitHub raw content URL.
            dest_path:    Absolute path to write the file.

        Returns:
            True on success, False after all retries exhausted.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                bytes_written = self._client.download_file(download_url, dest_path)
                logger.info(
                    f"  [OK] {filename} — {bytes_written:,} bytes "
                    f"(attempt {attempt}/{MAX_RETRIES})"
                )
                return True

            except requests.HTTPError as exc:
                logger.warning(
                    f"  [RETRY {attempt}/{MAX_RETRIES}] {filename} — HTTP error: {exc}"
                )
            except requests.RequestException as exc:
                logger.warning(
                    f"  [RETRY {attempt}/{MAX_RETRIES}] {filename} — Network error: {exc}"
                )
            except IOError as exc:
                logger.error(f"  [ERROR] {filename} — Filesystem error: {exc}")
                return False  # Don't retry filesystem errors

            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY_SECONDS * (2 ** (attempt - 1))  # Exponential backoff
                logger.debug(f"  Waiting {delay}s before retry...")
                time.sleep(delay)

        logger.error(f"  [FAILED] {filename} — all {MAX_RETRIES} attempts exhausted")

        # Remove partially downloaded file to avoid corrupt data
        if dest_path.exists():
            dest_path.unlink()
            logger.debug(f"  Removed partial file: {dest_path}")

        return False

    def _write_manifest(self) -> None:
        """Write the download manifest as a JSON file for audit purposes."""
        manifest_path = self._output_dir / "download_manifest.json"
        try:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "repository": f"{REPO_OWNER}/{REPO_NAME}",
                        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "total_files": len(self._manifest),
                        "files": self._manifest,
                    },
                    f,
                    indent=2,
                )
            logger.info(f"Manifest written: {manifest_path}")
        except IOError as exc:
            logger.error(f"Failed to write manifest: {exc}")

    @staticmethod
    def _sha256(file_path: Path) -> str:
        """Compute SHA-256 hash of a file for integrity verification."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Download EVTX attack samples from sbousseaden/EVTX-ATTACK-SAMPLES",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/download_dataset.py
  python scripts/download_dataset.py --dry-run
  python scripts/download_dataset.py --tactics CredentialAccess Execution
  python scripts/download_dataset.py --max-per-tactic 10
        """,
    )
    parser.add_argument(
        "--tactics",
        nargs="+",
        default=TACTIC_FOLDERS,
        choices=TACTIC_FOLDERS,
        help="Tactic folders to download. Defaults to all.",
        metavar="TACTIC",
    )
    parser.add_argument(
        "--max-per-tactic",
        type=int,
        default=MAX_FILES_PER_TACTIC,
        help=f"Maximum files per tactic folder (default: {MAX_FILES_PER_TACTIC}). "
             "Use 0 for unlimited.",
        dest="max_per_tactic",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files without downloading.",
        dest="dry_run",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Ensure the output directory exists
    Config.ensure_directories()

    max_per_tactic = args.max_per_tactic if args.max_per_tactic != 0 else None

    client = GitHubAPIClient()
    try:
        downloader = DatasetDownloader(
            output_dir=Config.RAW_LOGS_DIR,
            tactics=args.tactics,
            max_per_tactic=max_per_tactic,
            dry_run=args.dry_run,
            github_client=client,
        )
        downloader.run()
    finally:
        client.close()


if __name__ == "__main__":
    main()
