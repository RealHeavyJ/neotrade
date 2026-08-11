"""Read-only model card for status / learning."""

from __future__ import annotations

import json
from pathlib import Path

from neotrade.learning.model_card import load_model_card
from neotrade.signals.model import DEFAULT_PARAMS


def test_model_card_defaults_when_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "neotrade.learning.model_card.project_root",
        lambda: tmp_path,
    )
    card = load_model_card(model_path=tmp_path / "models" / "signal.txt")
    assert card.source == "defaults"
    assert card.n_features > 0
    assert card.params.get("num_leaves") == DEFAULT_PARAMS["num_leaves"]
    assert card.exclude_groups == ("vol",)
    lines = card.summary_lines()
    assert any("model card" in ln for ln in lines)
    assert any("num_leaves=" in ln for ln in lines)
    assert any("max_depth=(unset" in ln for ln in lines)


def test_model_card_from_meta(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "neotrade.learning.model_card.project_root",
        lambda: tmp_path,
    )
    model = tmp_path / "models" / "signal.txt"
    model.parent.mkdir(parents=True)
    model.write_text("booster", encoding="utf-8")
    meta = {
        "feature_names": ["ret_1", "ret_5", "cs_rank_ret_5"],
        "horizon": 5,
        "label_mode": "relative",
        "include_cs": True,
        "params": {**DEFAULT_PARAMS, "num_leaves": 15},
        "best_iteration": 42,
    }
    model.with_suffix(model.suffix + ".meta.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    card = load_model_card(model_path=model)
    assert card.source == "meta"
    assert card.n_features == 3
    assert card.params["num_leaves"] == 15
    assert card.best_iteration == 42
    assert any("feature drift" in n for n in card.notes)
    assert any("best_iteration=42" in ln for ln in card.summary_lines())
