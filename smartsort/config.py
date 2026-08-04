"""Configuration loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VALID_DESTINATIONS = frozenset({"ML", "AI", "OS", "IVP", "SWE", "SET", "MAD", "Other", "Downloads"})
SUPPORTED_EXTENSIONS = frozenset({".pdf", ".docx", ".pptx", ".txt"})


@dataclass(frozen=True)
class AppConfig:
    """Runtime settings for the sorter."""

    downloads_folder: Path
    root_folder: Path
    confidence_threshold: float = 0.90
    gemini_model: str = "gemini-3.5-flash-lite"
    dry_run: bool = False
    verbose_logging: bool = False
    settle_seconds: float = 3.0
    max_gemini_retries: int = 3

    @property
    def undo_log_path(self) -> Path:
        return self.root_folder / ".smartsort-undo.jsonl"

    def destination_for(self, destination: str) -> Path | None:
        """Return the permitted target directory, or None for Downloads."""
        if destination not in VALID_DESTINATIONS:
            raise ValueError(f"Unsupported destination: {destination}")
        if destination == "Downloads":
            return None
        return self.root_folder / "ML" if destination == "ML" else self.root_folder / "Sem_V" / destination


def _as_path(data: dict[str, Any], key: str) -> Path:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"config.json requires a non-empty '{key}' string")
    return Path(value).expanduser().resolve()


def load_config(path: Path) -> AppConfig:
    """Load a JSON config file and fail early on unsafe configuration."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Configuration not found: {path}. Copy config.json.example to config.json.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("config.json must contain a JSON object")
    threshold = float(raw.get("confidence_threshold", 0.90))
    if not 0 <= threshold <= 1:
        raise ValueError("confidence_threshold must be between 0 and 1")
    config = AppConfig(
        downloads_folder=_as_path(raw, "downloads_folder"),
        root_folder=_as_path(raw, "root_folder"),
        confidence_threshold=threshold,
        gemini_model=str(raw.get("gemini_model", "gemini-3.5-flash-lite")),
        dry_run=bool(raw.get("dry_run", False)),
        verbose_logging=bool(raw.get("verbose_logging", False)),
        settle_seconds=float(raw.get("settle_seconds", 3.0)),
        max_gemini_retries=int(raw.get("max_gemini_retries", 3)),
    )
    if config.settle_seconds < 0 or config.max_gemini_retries < 1:
        raise ValueError("settle_seconds must be non-negative and max_gemini_retries must be at least 1")
    return config
