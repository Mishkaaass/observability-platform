"""Verify sanitized JSON records and finite local log rotation."""

import json
import logging
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import LOGGER, app
from app.workload_logs import BACKUPS, MAX_BYTES, make_file_handler


def test_request_log_has_fixed_fields_and_no_request_content(tmp_path):
    path = tmp_path / "workload.jsonl"
    handler = make_file_handler(path)
    LOGGER.addHandler(handler)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/validate?private=never-in-log",
            json={"message": "do-not-record-payload"},
        )
        assert response.status_code == 200
    finally:
        LOGGER.removeHandler(handler)
        handler.close()

    raw = path.read_text()
    event = json.loads(raw)
    assert set(event) == {"timestamp", "event", "route", "status", "duration_ms"}
    assert datetime.fromisoformat(event["timestamp"]).utcoffset().total_seconds() == 0
    assert event["event"] == "workload_request"
    assert event["route"] == "/api/validate"
    assert event["status"] == 200
    assert event["duration_ms"] >= 0
    assert "never-in-log" not in raw
    assert "do-not-record-payload" not in raw


def test_rotation_retains_at_most_four_files(tmp_path):
    path = tmp_path / "workload.jsonl"
    handler = make_file_handler(path)
    assert handler.maxBytes == MAX_BYTES
    assert handler.backupCount == BACKUPS
    handler.maxBytes = 128
    logger = logging.Logger("rotation-test")
    logger.addHandler(handler)
    try:
        for _ in range(30):
            logger.info("x" * 60)
    finally:
        logger.removeHandler(handler)
        handler.close()

    files = list(tmp_path.glob("workload.jsonl*"))
    assert len(files) == BACKUPS + 1
    assert all(file.stat().st_size <= 128 for file in files)
