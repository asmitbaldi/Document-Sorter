"""Small, side-effect-minimising filesystem helpers."""

from __future__ import annotations

import hashlib
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import SUPPORTED_EXTENSIONS

TEMPORARY_SUFFIXES = (".download", ".crdownload", ".part", ".tmp", ".temp")


def is_supported_document(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def should_ignore(path: Path) -> bool:
    """Identify dotfiles and browser/application temporary files."""
    name = path.name.lower()
    return path.name.startswith(".") or name.endswith(TEMPORARY_SUFFIXES) or name.startswith("~$")


def is_file_locked(path: Path) -> bool:
    """Best-effort advisory lock probe for macOS/POSIX producers."""
    try:
        import fcntl
        with path.open("rb") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                return False
            except BlockingIOError:
                return True
    except (OSError, PermissionError):
        return True


@contextmanager
def processing_lock(lock_root: Path, source: Path) -> Iterator[bool]:
    """Acquire a non-blocking, cross-process lock for one downloaded file.

    Watchdog may deliver overlapping events and a user can also run ``--once``.
    The lock lives outside Downloads so it neither triggers nor disrupts file events.
    """
    import fcntl

    lock_dir = lock_root / ".smartsort-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(str(source).encode("utf-8")).hexdigest()
    lock_path = lock_dir / f"{fingerprint}.lock"
    with lock_path.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def wait_until_ready(path: Path, settle_seconds: float, attempts: int = 20) -> bool:
    """Wait for a stable, readable, unlocked file before processing it."""
    stable_observations, previous_size = 0, -1
    interval = max(settle_seconds / 2, 0.5)
    for _ in range(attempts):
        if not path.exists() or not path.is_file() or should_ignore(path):
            return False
        try:
            size = path.stat().st_size
        except OSError:
            return False
        if size == previous_size and not is_file_locked(path):
            stable_observations += 1
            if stable_observations >= 2:
                return True
        else:
            stable_observations = 0
        previous_size = size
        time.sleep(interval)
    return False


def unique_destination(directory: Path, source_name: str) -> Path:
    """Choose a non-overwriting destination path."""
    candidate = directory / source_name
    if not candidate.exists():
        return candidate
    stem, suffix, timestamp = Path(source_name).stem, Path(source_name).suffix, time.strftime("%Y%m%d-%H%M%S")
    for counter in range(1, 10_000):
        candidate = directory / f"{stem} ({timestamp}-{counter}){suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not generate a unique destination for {source_name}")
