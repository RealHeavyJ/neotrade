"""Structured logging setup for neotrade.

Environment:
    NEOTRADE_LOG_LEVEL — DEBUG, INFO, WARNING, ERROR (default INFO)
    NEOTRADE_LOG_FILE  — optional path; logs append as text lines
    NEOTRADE_LOG_JSON  — if ``1``/``true``, emit one JSON object per line

Usage:
    from neotrade.logging_config import get_logger, setup_logging
    setup_logging()  # once at process start (CLI/dashboard)
    log = get_logger(__name__)
    log.info("event", extra={"symbol": "ARM"})  # extra merged in JSON mode
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_CONFIGURED = False
_LOG_RECORD_BUILTIN = {
    "name",
    "msg",
    "args",
    "created",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "exc_info",
    "exc_text",
    "thread",
    "threadName",
    "taskName",
}


class _JsonFormatter(logging.Formatter):
    """One JSON object per line for machine-friendly logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key, val in record.__dict__.items():
            if key in _LOG_RECORD_BUILTIN or key.startswith("_"):
                continue
            try:
                json.dumps(val)
                payload[key] = val
            except (TypeError, ValueError):
                payload[key] = repr(val)
        return json.dumps(payload, default=str)


class _TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )


def _level_from_env() -> int:
    raw = (os.environ.get("NEOTRADE_LOG_LEVEL") or "INFO").strip().upper()
    return getattr(logging, raw, logging.INFO)


def _json_mode() -> bool:
    return (os.environ.get("NEOTRADE_LOG_JSON") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def setup_logging(*, force: bool = False) -> None:
    """Configure root ``neotrade`` logger once per process.

    Args:
        force: Reconfigure even if already set up (tests).
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    level = _level_from_env()
    root = logging.getLogger("neotrade")
    root.handlers.clear()
    root.setLevel(level)
    root.propagate = False

    formatter: logging.Formatter = _JsonFormatter() if _json_mode() else _TextFormatter()

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(level)
    sh.setFormatter(formatter)
    root.addHandler(sh)

    log_file = (os.environ.get("NEOTRADE_LOG_FILE") or "").strip()
    if log_file:
        path = Path(log_file).expanduser()
        if not path.is_absolute():
            from neotrade.config.load import project_root

            path = project_root() / path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(path, encoding="utf-8")
            fh.setLevel(level)
            fh.setFormatter(formatter)
            root.addHandler(fh)
        except OSError as exc:
            root.warning("log file unavailable path=%s err=%s", path, exc)

    _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child of the ``neotrade`` logger (ensures setup)."""
    setup_logging()
    if not name or name == "neotrade":
        return logging.getLogger("neotrade")
    if name.startswith("neotrade."):
        return logging.getLogger(name)
    return logging.getLogger(f"neotrade.{name}")
