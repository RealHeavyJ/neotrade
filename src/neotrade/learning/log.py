"""Append-only JSONL learning log for advice quality and retrain cadence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from neotrade.config.load import project_root


def learning_dir() -> Path:
    path = project_root() / "data" / "learning"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class LearningLog:
    ts: str
    kind: str
    payload: dict = field(default_factory=dict)


def append_entry(kind: str, payload: dict) -> Path:
    entry = LearningLog(
        ts=datetime.now(timezone.utc).isoformat(),
        kind=kind,
        payload=payload,
    )
    path = learning_dir() / "events.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(entry)) + "\n")
    return path


def append_advice_feedback(
    *,
    stance: str,
    top_picks: list[str],
    action: str,
    model: str,
    rating: int | None = None,
    notes: str = "",
) -> Path:
    return append_entry(
        "advice_feedback",
        {
            "stance": stance,
            "top_picks": top_picks,
            "action": action,
            "model": model,
            "rating": rating,
            "notes": notes,
        },
    )


def append_retrain_event(*, metrics: dict, n_train: int, n_valid: int) -> Path:
    return append_entry(
        "retrain",
        {"metrics": metrics, "n_train": n_train, "n_valid": n_valid},
    )


def load_recent(limit: int = 50) -> list[dict]:
    path = learning_dir() / "events.jsonl"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
