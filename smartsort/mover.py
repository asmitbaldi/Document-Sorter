"""Safe file movement and append-only undo journal."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .classifier import Classification
from .config import AppConfig
from .utils import unique_destination


@dataclass(frozen=True)
class MoveRecord:
    source: str
    destination: str
    classification: str
    confidence: float
    reason: str
    timestamp: str


class FileMover:
    """Move only to allow-listed targets, preserving all existing files."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def move(self, source: Path, classification: Classification) -> MoveRecord | None:
        destination_dir = self.config.destination_for(classification.destination)
        if destination_dir is None:
            return None
        source = source.resolve()
        if source.parent != self.config.downloads_folder:
            raise ValueError(f"Refusing to move file outside Downloads: {source}")
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = unique_destination(destination_dir, source.name)
        record = MoveRecord(
            source=str(source), destination=str(destination), classification=classification.destination,
            confidence=classification.confidence, reason=classification.reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        if self.config.dry_run:
            return record
        shutil.move(str(source), str(destination))
        with self.config.undo_log_path.open("a", encoding="utf-8") as journal:
            journal.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        return record

    def undo_last(self) -> MoveRecord | None:
        """Undo the most recent move if both paths are still safe and unambiguous."""
        journal_path = self.config.undo_log_path
        if not journal_path.exists():
            return None
        records = [line for line in journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not records:
            return None
        record = MoveRecord(**json.loads(records[-1]))
        source, destination = Path(record.source), Path(record.destination)
        if not destination.exists() or source.exists() or source.parent != self.config.downloads_folder:
            raise RuntimeError("Cannot undo: the file paths have changed or the original name is occupied")
        if self.config.dry_run:
            return record
        shutil.move(str(destination), str(source))
        journal_path.write_text("\n".join(records[:-1]) + ("\n" if len(records) > 1 else ""), encoding="utf-8")
        return record
