"""Command-line entry point for QABenchmarkEval."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from acquisition import acquire, load_yaml
from parsers import parse_all


def main() -> int:
    parser = argparse.ArgumentParser(prog="qabm", description="Acquire biomedical QA datasets")
    subparsers = parser.add_subparsers(dest="command", required=True)
    update = subparsers.add_parser("update", help="download and cache configured datasets")
    update.add_argument("config", type=Path, help="top-level YAML configuration")
    args = parser.parse_args()

    config = load_yaml(args.config.resolve())
    level = str(config.get("logging", {}).get("level", "INFO")).upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO), format="%(asctime)s %(levelname)s %(message)s")

    if args.command == "update":
        try:
            acquire(args.config)
            parse_all(args.config)
        except Exception as exc:
            logging.getLogger(__name__).error("Update failed: %s", exc)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
