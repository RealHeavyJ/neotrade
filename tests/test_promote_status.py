"""Promote status + quote age helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from neotrade.data.quotes import quote_age_seconds
from neotrade.learning.promote_status import (
    load_promote_status,
    promote_from_backtest_dict,
)


def test_promote_from_dict_requires_stable_when_present():
    assert promote_from_backtest_dict({"gate": {"pass": True}}) is True
    assert (
        promote_from_backtest_dict(
            {"gate": {"pass": True}, "stable_gate": {"pass": False}}
        )
        is False
    )
    assert (
        promote_from_backtest_dict(
            {"gate": {"pass": True}, "stable_gate": {"pass": True}}
        )
        is True
    )


def test_quote_age_seconds():
    now = datetime(2026, 7, 25, 18, 0, tzinfo=UTC)
    ts = (now - timedelta(seconds=90)).isoformat()
    age = quote_age_seconds(ts, now=now)
    assert age is not None
    assert 89 <= age <= 91
    assert quote_age_seconds("", now=now) is None


def test_load_promote_status_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "neotrade.learning.promote_status.project_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "neotrade.learning.promote_status.learning_dir",
        lambda: tmp_path / "data" / "learning",
    )
    monkeypatch.setattr(
        "neotrade.learning.promote_status.calibrate_fills",
        lambda: type("C", (), {"n": 0, "min_n": 20})(),
    )
    monkeypatch.setattr(
        "neotrade.learning.promote_status.effective_slip_bps",
        lambda fallback=5.0: fallback,
    )
    (tmp_path / "data" / "learning").mkdir(parents=True)
    ps = load_promote_status(model_path=tmp_path / "models" / "x.txt")
    assert ps.promote is None
    assert ps.defaults_top_n == 7


def test_load_promote_status_with_bt(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "neotrade.learning.promote_status.project_root",
        lambda: tmp_path,
    )
    learning = tmp_path / "data" / "learning"
    learning.mkdir(parents=True)
    monkeypatch.setattr(
        "neotrade.learning.promote_status.learning_dir",
        lambda: learning,
    )
    monkeypatch.setattr(
        "neotrade.learning.promote_status.calibrate_fills",
        lambda: type("C", (), {"n": 3, "min_n": 20})(),
    )
    monkeypatch.setattr(
        "neotrade.learning.promote_status.effective_slip_bps",
        lambda fallback=5.0: 5.0,
    )
    bt = {
        "ts": "2026-07-25T00:00:00+00:00",
        "gate": {"pass": True, "reasons": []},
        "stable_gate": {"pass": True, "reasons": []},
        "signal": {"total_return": 0.5, "sharpe": 1.2, "max_drawdown": 0.1},
        "config": {"top_n": 7, "rebalance_every": 14},
        "windows": [{"gate_pass": True}, {"gate_pass": True}],
    }
    (learning / "backtest_latest.json").write_text(json.dumps(bt), encoding="utf-8")
    ps = load_promote_status(model_path=Path("nope"))
    assert ps.promote is True
    assert ps.top_n == 7
    assert ps.windows_pass == "2/2"
