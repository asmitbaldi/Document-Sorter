"""CLI entry point for DocumentSorter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .classifier import GeminiClassifier
from .config import load_config
from .logger import configure_logging
from .mover import FileMover
from .watcher import DocumentProcessor, DownloadsWatcher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organize supported downloaded documents with Gemini.")
    parser.add_argument("--config", type=Path, default=Path("config.json"), help="Path to configuration JSON")
    parser.add_argument("--once", action="store_true", help="Process current supported files once, then exit")
    parser.add_argument("--undo-last", action="store_true", help="Undo the most recent recorded move")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        logger = configure_logging(args.config.parent / "logs", config.verbose_logging)
        if args.undo_last:
            record = FileMover(config).undo_last()
            logger.info("%s", "No moves to undo" if record is None else f"Undid: {record.destination} -> {record.source}")
            return 0
        classifier = GeminiClassifier(config.gemini_model, config.max_gemini_retries)
        processor = DocumentProcessor(config, classifier, logger)
        if args.once:
            for file in config.downloads_folder.iterdir():
                processor.process(file)
            return 0
        DownloadsWatcher(config, processor, logger).run()
        return 0
    except Exception as exc:
        print(f"DocumentSorter error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
