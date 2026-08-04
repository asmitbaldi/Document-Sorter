"""Application logging setup."""

from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """Configure console and rotating file logs without duplicate handlers."""
    from logging.handlers import RotatingFileHandler
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("smartsort")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    if logger.handlers:
        return logger
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    stream = logging.StreamHandler()
    stream.setLevel(logging.DEBUG if verbose else logging.INFO)
    stream.setFormatter(formatter)
    file_handler = RotatingFileHandler(log_dir / "smartsort.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(stream)
    logger.addHandler(file_handler)
    return logger
