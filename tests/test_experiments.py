"""Experiment ledger tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neotrade.learning.experiments import (
    complete_experiment,
    format_compare,
    list_experiments,
    open_experiment,
    open_from_desk,
    snapshot_gates,
)


def test_open_complete_and_list(monkeypatch, tmp_path: Path):
    from neotrade.learning import experiments as exp_mod
    from neotrade.learning import log as log_mod

    monkeypatch.setattr(exp_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(exp_mod, "learning_dir", lambda: tmp_path / "data" / "learning")
    monkeypatch.setattr(log_mod, "project_root", lambda: tmp_path)
    (tmp_path / "data" / "learning").mkdir(parents=True)

    # fake gate files
    learning = tmp_path / "data" / "learning"
    learning.joinpath("backtest_latest.json").write_text(
        json.dumps(
            {
                "gate": {"pass": False, "reasons": ["FAIL"]},
                "stable_gate": {"pass": False},
                "signal": {"total_return": 0.1, "max_drawdown": 0.1, "sharpe": 1.0, "n_trades": 10},
                "equal_weight": {"total_return": 0.2},
                "momentum": {"total_return": 0.25},
            }
        ),
        encoding="utf-8",
    )

    exp = open_experiment("try rebalance_every=7", source="test")
    assert exp.status == "open"
    assert exp.id
    assert list_experiments(status="open")

    learning.joinpath("backtest_latest.json").write_text(
        json.dumps(
            {
                "gate": {"pass": True, "reasons": ["PASS"]},
                "stable_gate": {"pass": True},
                "signal": {"total_return": 0.3, "max_drawdown": 0.1, "sharpe": 1.5, "n_trades": 8},
                "equal_weight": {"total_return": 0.2},
                "momentum": {"total_return": 0.25},
            }
        ),
        encoding="utf-8",
    )
    done = complete_experiment(exp.id[:8], notes="looks better")
    assert done.status == "complete"
    assert done.outcome == "pass"
    assert not list_experiments(status="open")
    lines = format_compare(done.before, done.after)
    assert any("promote" in ln.lower() or "sig_ret" in ln.lower() for ln in lines)


def test_open_rejects_none():
    with pytest.raises(ValueError):
        open_experiment("none")


def test_open_from_desk(monkeypatch, tmp_path: Path):
    from neotrade.learning import experiments as exp_mod
    from neotrade.learning import log as log_mod

    monkeypatch.setattr(exp_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(exp_mod, "learning_dir", lambda: tmp_path / "data" / "learning")
    monkeypatch.setattr(log_mod, "project_root", lambda: tmp_path)
    learning = tmp_path / "data" / "learning"
    learning.mkdir(parents=True)
    learning.joinpath("desk_latest.json").write_text(
        json.dumps({"experiment": "raise top_n to 6", "promote": "yes"}),
        encoding="utf-8",
    )
    exp = open_from_desk()
    assert exp is not None
    assert "top_n" in exp.hypothesis

    learning.joinpath("desk_latest.json").write_text(
        json.dumps({"experiment": "none"}),
        encoding="utf-8",
    )
    assert open_from_desk() is None


def test_snapshot_gates_empty(monkeypatch, tmp_path: Path):
    from neotrade.learning import experiments as exp_mod

    monkeypatch.setattr(exp_mod, "project_root", lambda: tmp_path)
    snap = snapshot_gates()
    assert "ts" in snap


def test_single_open_discipline(monkeypatch, tmp_path: Path):
    from neotrade.learning import experiments as exp_mod
    from neotrade.learning import log as log_mod
    from neotrade.learning.experiments import (
        complete_all_open,
        discipline_status,
        list_experiments,
        open_experiment,
        reconcile_open_experiments,
    )

    monkeypatch.setattr(exp_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(exp_mod, "learning_dir", lambda: tmp_path / "data" / "learning")
    monkeypatch.setattr(log_mod, "project_root", lambda: tmp_path)
    (tmp_path / "data" / "learning").mkdir(parents=True)

    a = open_experiment("hyp-a", source="test")
    b = open_experiment("hyp-b", source="test", replace_open=True)
    assert b.hypothesis == "hyp-b"
    # a should be abandoned
    assert list_experiments(status="open")
    assert len(list_experiments(status="open")) == 1
    assert list_experiments(status="open")[0].id == b.id
    # force two opens via ledger bypass then reconcile
    open_experiment("hyp-c", source="test", replace_open=True)
    st = discipline_status()
    assert st["disciplined"] is True
    assert st["open_count"] == 1
    done = complete_all_open(outcome="abandoned", notes="test sweep")
    assert len(done) >= 1
    assert list_experiments(status="open") == []
    assert reconcile_open_experiments() == []
