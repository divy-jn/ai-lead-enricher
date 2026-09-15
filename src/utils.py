"""
utils.py — Shared helper utilities.

Logging setup, retry decorators, and common helper functions
used across multiple modules.
"""

import logging
import sys

from src.config import settings


def get_logger(name: str) -> logging.Logger:
    """Create a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module).

    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(settings.log_level)
    return logger
