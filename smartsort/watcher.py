"""Download event handling and application orchestration."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .classifier import BaseClassifier, FilenameRouter
from .config import AppConfig
from .extractor import DocumentExtractor
from .mover import FileMover
from .utils import is_supported_document, processing_lock, should_ignore, wait_until_ready


class DocumentProcessor:
    """Coordinate readiness checks, routing, classification, and movement."""

    def __init__(self, config: AppConfig, classifier: BaseClassifier, logger: logging.Logger) -> None:
        self.config, self.classifier, self.logger = config, classifier, logger
        self.router, self.extractor, self.mover = FilenameRouter(), DocumentExtractor(), FileMover(config)
        self._in_progress: set[Path] = set()
        self._lock = threading.Lock()

    def process(self, path: Path) -> None:
        path = path.resolve()
        if should_ignore(path) or not is_supported_document(path):
            return
        with self._lock:
            if path in self._in_progress:
                return
            self._in_progress.add(path)
        try:
            with processing_lock(self.config.root_folder, path) as acquired:
                if not acquired:
                    self.logger.debug("Another DocumentSorter process is handling %s", path.name)
                    return
                # A different process can have completed the move while this event was queued.
                if not is_supported_document(path):
                    return
                if not wait_until_ready(path, self.config.settle_seconds):
                    self.logger.warning("File did not settle; leaving in Downloads: %s", path.name)
                    return
                result = self.router.route(path)
                if result:
                    self.logger.info("Filename route: %s -> %s", path.name, result.destination)
                else:
                    result = self.classifier.classify(self.extractor.extract(path))
                    self.logger.info("Gemini route: %s -> %s (%.2f)", path.name, result.destination, result.confidence)
                if result.destination == "Downloads":
                    self.logger.info("Leaving in Downloads by classifier decision: %s", path.name)
                    return
                if result.confidence < self.config.confidence_threshold:
                    self.logger.info("Leaving in Downloads: low confidence %.2f for %s", result.confidence, path.name)
                    return
                record = self.mover.move(path, result)
                if record:
                    self.logger.info("%s %s -> %s", "Would move" if self.config.dry_run else "Moved", record.source, record.destination)
        except Exception:
            self.logger.exception("Could not process %s; file left in Downloads", path.name)
        finally:
            with self._lock:
                self._in_progress.discard(path)


class DownloadEventHandler(FileSystemEventHandler):
    """Dispatch created and renamed supported documents without blocking watchdog."""

    def __init__(self, processor: DocumentProcessor) -> None:
        super().__init__()
        self.processor = processor

    def on_created(self, event: FileSystemEvent) -> None:
        self._submit(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        self._submit(event, getattr(event, "dest_path", None))

    def _submit(self, event: FileSystemEvent, candidate: str | None = None) -> None:
        if event.is_directory:
            return
        threading.Thread(target=self.processor.process, args=(Path(candidate or event.src_path),), daemon=True).start()


class DownloadsWatcher:
    """Long-lived watchdog observer for the configured Downloads folder."""

    def __init__(self, config: AppConfig, processor: DocumentProcessor, logger: logging.Logger) -> None:
        self.config, self.processor, self.logger = config, processor, logger
        self.observer = Observer()

    def run(self) -> None:
        if not self.config.downloads_folder.is_dir():
            raise NotADirectoryError(f"Downloads folder not found: {self.config.downloads_folder}")
        self.observer.schedule(DownloadEventHandler(self.processor), str(self.config.downloads_folder), recursive=False)
        self.observer.start()
        self.logger.info("Watching %s", self.config.downloads_folder)
        try:
            self.observer.join()
        except KeyboardInterrupt:
            self.logger.info("Stopping watcher")
        finally:
            self.observer.stop()
            self.observer.join()
