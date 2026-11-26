"""Allow only sanitized workload events in a bounded, opt-in local log file."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE = Path("/var/log/observability/workload.jsonl")
MAX_BYTES = 256 * 1024
BACKUPS = 3


def make_file_handler(path: Path = LOG_FILE) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler
