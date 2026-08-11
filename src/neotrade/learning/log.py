"""Append-only JSONL learning log for advice quality and retrain cadence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
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
        ts=datetime.now(UTC).isoformat(),
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


def append_retrain_event(
    *,
    metrics: dict,
    n_train: int,
    n_valid: int,
    params: dict | None = None,
    feature_names: list[str] | None = None,
    exclude_groups: list[str] | tuple[str, ...] | None = None,
    label_mode: str | None = None,
    horizon: int | None = None,
    rounds: int | None = None,
) -> Path:
    """Append retrain row; optional model-card fields for learning history."""
    payload: dict = {"metrics": metrics, "n_train": n_train, "n_valid": n_valid}
    if params is not None:
        payload["params"] = params
    if feature_names is not None:
        payload["feature_names"] = list(feature_names)
        payload["n_features"] = len(feature_names)
    if exclude_groups is not None:
        payload["exclude_groups"] = list(exclude_groups)
    if label_mode is not None:
        payload["label_mode"] = label_mode
    if horizon is not None:
        payload["horizon"] = horizon
    if rounds is not None:
        payload["rounds"] = rounds
    return append_entry("retrain", payload)


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
