"""Centralised logging configuration for the IoT platform."""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root 'iot_platform' logger with a human-readable console format."""
    logger = logging.getLogger("iot_platform")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
