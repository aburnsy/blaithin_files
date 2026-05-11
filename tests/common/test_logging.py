"""Tests for structlog configuration."""

import json


def test_get_logger_returns_bound_logger():
    from src.common.logging import get_logger
    log = get_logger("test")
    assert log is not None


def test_logs_are_json_to_file(tmp_path, monkeypatch):
    from src.common import logging as logging_mod

    log_file = tmp_path / "test.jsonl"
    monkeypatch.setattr(logging_mod, "LOG_FILE", log_file)
    logging_mod.configure(force=True)

    log = logging_mod.get_logger("test_emit")
    log.info("hello", value=42, source="tullys")

    # Flush handlers
    import logging as stdlib_logging
    for h in stdlib_logging.getLogger().handlers:
        h.flush()

    lines = log_file.read_text().strip().split("\n")
    assert len(lines) >= 1
    record = json.loads(lines[-1])
    assert record["event"] == "hello"
    assert record["value"] == 42
    assert record["source"] == "tullys"
