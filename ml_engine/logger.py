"""
ml_engine/logger.py
====================
Centralized logging factory for the entire ML Engine.

WHY THIS EXISTS:
  - Standardizes log format across all modules (parser, trainer, predictor, API).
  - Prevents every module from calling basicConfig() and overriding each other.
  - Makes it trivial to switch from console → file → cloud logging later.
  - One import instead of repeated boilerplate in every file.

USAGE:
  from logger import get_logger
  logger = get_logger(__name__)
  logger.info("Processing started")
  logger.error("Something failed", exc_info=True)
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# Import config lazily to avoid circular import issues
# We access LOG_LEVEL and LOG_FORMAT directly
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(
    name: str,
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """
    Create and configure a logger for a given module.

    Args:
        name:     The logger name, typically __name__ from the calling module.
        level:    Override log level string (e.g., "DEBUG", "INFO", "WARNING").
                  Falls back to the LOG_LEVEL env var, then defaults to "INFO".
        log_file: Optional path to a file handler. If None, logs go to stdout.

    Returns:
        A configured logging.Logger instance.

    Example:
        logger = get_logger(__name__)
        logger.info("Model loaded successfully")
    """
    # Resolve log level
    try:
        from config import Config
        default_level = Config.LOG_LEVEL
    except ImportError:
        default_level = "INFO"

    resolved_level_str = (level or default_level).upper()
    resolved_level = getattr(logging, resolved_level_str, logging.INFO)

    # Get or create logger (Python's logging is hierarchical by name)
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if get_logger() is called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(resolved_level)

    # --- Console Handler (stdout) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(resolved_level)
    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)
    # Force UTF-8 encoding on Windows to avoid cp1252 UnicodeEncodeError
    if hasattr(console_handler.stream, 'reconfigure'):
        try:
            console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # --- Optional File Handler ---
    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(resolved_level)
        file_handler.setFormatter(
            logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)
        )
        logger.addHandler(file_handler)

    # Prevent log records from propagating to the root logger
    # (avoids duplicate output when the root logger is also configured)
    logger.propagate = False

    return logger
