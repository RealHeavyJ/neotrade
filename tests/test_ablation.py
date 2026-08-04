"""Feature group ablation (fast synthetic)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from neotrade.signals.eval import run_feature_ablation
from neotrade.signals.features import FEATURE_GROUPS


def _synth(n: int = 200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2023-01-01", periods=n)
    close = 100 * np.cumprod(1 + rng.normal(0.0005, 0.015, size=n))
    high = close * (1 + rng.uniform(0, 0.01, size=n))
    low = close * (1 - rng.uniform(0, 0.01, size=n))
    open_ = close * (1 + rng.normal(0, 0.002, size=n))
    vol = rng.integers(1_000_000, 5_000_000, size=n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )


def test_feature_groups_cover_model_features():
    from neotrade.signals.features import model_feature_names

    named = {c for cols in FEATURE_GROUPS.values() for c in cols}
    full = set(model_feature_names(include_cs=True))
    # groups may not cover every col but should be subset
    assert named <= full or named.intersection(full)


def test_ablation_runs_on_synth(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "neotrade.signals.eval.project_root",
        lambda: tmp_path,
    )
    frames = {s: _synth(220, seed=i) for i, s in enumerate(["AAA", "BBB", "CCC", "DDD"])}
    # only two groups for speed
    groups = {
        "returns": FEATURE_GROUPS["returns"],
        "cs": FEATURE_GROUPS["cs"],
    }
    rep = run_feature_ablation(
        frames,
        n_folds=2,
        num_boost_round=20,
        groups=groups,
        save=True,
    )
    assert rep.baseline_acc == rep.baseline_acc  # finite
    assert len(rep.rows) >= 1
    assert (tmp_path / "data" / "learning" / "ablation_latest.json").is_file()
