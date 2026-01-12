"""Logging configuration for Ditado."""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

# Log directory
LOG_DIR = Path.home() / ".ditado" / "logs"
LOG_FILE = LOG_DIR / "ditado.log"

# Log format
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Default settings
DEFAULT_LEVEL = logging.INFO
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 5  # Keep 5 log files

_initialized = False


def setup_logging(level: int = DEFAULT_LEVEL, debug: bool = False) -> None:
    """
    Set up the logging system.

    Args:
        level: Logging level (default INFO)
        debug: If True, enable DEBUG level and console output
    """
    global _initialized

    if _initialized:
        return

    # Create log directory
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Set level
    if debug:
        level = logging.DEBUG

    # Create root logger for Ditado
    root_logger = logging.getLogger("ditado")
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # File handler with rotation
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not create log file: {e}")

    # Console handler (only in debug mode or if no file handler)
    if debug or not root_logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        root_logger.addHandler(console_handler)

    _initialized = True
    root_logger.info("Ditado logging initialized")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Args:
        name: Module name (e.g., "ditado.app", "ditado.recorder")

    Returns:
        Logger instance
    """
    # Ensure logging is set up
    if not _initialized:
        setup_logging()

    # Prefix with ditado if not already
    if not name.startswith("ditado"):
        name = f"ditado.{name}"

    return logging.getLogger(name)


def set_debug_mode(enabled: bool) -> None:
    """Enable or disable debug mode."""
    logger = logging.getLogger("ditado")

    if enabled:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        for handler in logger.handlers:
            handler.setLevel(logging.INFO)
