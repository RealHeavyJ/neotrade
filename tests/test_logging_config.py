"""P2 logging setup tests."""

from __future__ import annotations

import json
import logging

from neotrade.logging_config import get_logger, setup_logging


def test_setup_logging_text_and_get_logger(monkeypatch):
    monkeypatch.delenv("NEOTRADE_LOG_JSON", raising=False)
    monkeypatch.setenv("NEOTRADE_LOG_LEVEL", "DEBUG")
    setup_logging(force=True)
    log = get_logger("unit.test")
    assert log.name == "neotrade.unit.test"
    assert log.getEffectiveLevel() == logging.DEBUG
    log.debug("hello")


def test_json_formatter_emits_object(monkeypatch, capsys):
    monkeypatch.setenv("NEOTRADE_LOG_JSON", "1")
    monkeypatch.setenv("NEOTRADE_LOG_LEVEL", "INFO")
    setup_logging(force=True)
    log = get_logger("json.test")
    log.info("event msg")
    err = capsys.readouterr().err
    # last non-empty line should be JSON
    lines = [ln for ln in err.strip().splitlines() if ln.strip()]
    assert lines
    payload = json.loads(lines[-1])
    assert payload["msg"] == "event msg"
    assert payload["level"] == "INFO"
    assert "neotrade" in payload["logger"]


def test_log_file_written(monkeypatch, tmp_path):
    path = tmp_path / "neotrade.log"
    monkeypatch.setenv("NEOTRADE_LOG_FILE", str(path))
    monkeypatch.delenv("NEOTRADE_LOG_JSON", raising=False)
    monkeypatch.setenv("NEOTRADE_LOG_LEVEL", "INFO")
    setup_logging(force=True)
    log = get_logger("file.test")
    log.info("to_file")
    for h in logging.getLogger("neotrade").handlers:
        if hasattr(h, "flush"):
            h.flush()
    text = path.read_text(encoding="utf-8")
    assert "to_file" in text
