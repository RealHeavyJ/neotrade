"""P1 ML rigor: walk-forward, baselines, calibration, leakage."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from neotrade.signals.eval import (
    baseline_always_long,
    baseline_momentum,
    build_panel,
    calibration_table,
    check_leakage,
    walk_forward_eval,
)
from neotrade.signals.features import build_labeled_frame


def _synth(n: int = 240, seed: int = 0, drift: float = 0.0003) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2023-01-03", periods=n)
    # mild momentum structure
    shock = rng.normal(0, 0.012, size=n)
    mom = np.zeros(n)
    for i in range(1, n):
        mom[i] = 0.25 * mom[i - 1] + shock[i] + drift
    close = 80 * np.cumprod(1 + mom)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * 1.008
    low = np.minimum(open_, close) * 0.992
    volume = rng.integers(800_000, 2_000_000, size=n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


def test_leakage_report_ok():
    rep = check_leakage(horizon=5)
    assert rep.ok is True
    assert rep.label_horizon_bars == 5
    assert rep.max_feature_lookback_bars >= 50  # includes ret_60 window
    assert any("shift" in n.lower() or "forward" in n.lower() or "Label" in n for n in rep.notes)


def test_leakage_negative_bad_horizon():
    rep = check_leakage(horizon=0)
    assert rep.ok is False


def test_label_uses_future_close_not_feature():
    """Positive structural: label depends on future close; features on past only."""
    df = _synth(n=100, seed=1)
    labeled = build_labeled_frame(df, horizon=5)
    # last rows dropped because no future — index max < ohlcv max
    assert labeled.index.max() < df.index.max()
    # ret_5 is lagging: correlates with past, not equal to fwd_ret
    assert "fwd_ret" in labeled.columns
    corr = labeled["ret_5"].corr(labeled["fwd_ret"])
    assert corr is not None
    # should not be perfectly collinear with label path
    assert abs(corr) < 0.99


def test_baselines_always_long_and_momentum():
    y = np.array([1, 1, 0, 1, 0])
    assert baseline_always_long(y) == pytest.approx(0.6)
    df = pd.DataFrame(
        {
            "ret_5": [0.01, -0.02, 0.03, -0.01, 0.0],
            "label": [1, 0, 1, 0, 1],
        }
    )
    # pred: 1,0,1,0,0 vs y 1,0,1,0,1 → 4/5
    assert baseline_momentum(df) == pytest.approx(0.8)


def test_calibration_table_bins():
    y = np.array([0, 0, 1, 1, 1, 0])
    p = np.array([0.1, 0.2, 0.6, 0.7, 0.9, 0.4])
    bins = calibration_table(y, p, n_bins=2)
    assert len(bins) == 2
    assert sum(b.n for b in bins) == 6


def test_walk_forward_eval_positive():
    frames = {
        "AAA": _synth(n=220, seed=1),
        "BBB": _synth(n=220, seed=2),
        "CCC": _synth(n=220, seed=3),
    }
    report = walk_forward_eval(
        frames,
        horizon=5,
        n_folds=3,
        min_train_frac=0.45,
        num_boost_round=40,
    )
    assert report.n_folds == 3
    assert len(report.folds) == 3
    assert 0.0 <= report.mean_accuracy <= 1.0
    assert report.leakage.ok is True
    # chronological folds
    for i in range(1, len(report.folds)):
        assert report.folds[i].test_start >= report.folds[i - 1].test_start
    lines = report.summary_lines()
    assert any("mean_accuracy" in ln for ln in lines)
    d = report.to_dict()
    assert "edge_vs_always_long" in d
    assert "calibration" in d


def test_walk_forward_rejects_too_few_folds():
    with pytest.raises(ValueError, match="n_folds"):
        walk_forward_eval({"A": _synth(80)}, n_folds=1)


def test_build_panel_requires_data():
    with pytest.raises(ValueError, match="no labeled"):
        build_panel({"X": _synth(n=30)})  # too short for features


def test_build_panel_has_cs_and_relative_labels():
    frames = {"A": _synth(n=120, seed=1), "B": _synth(n=120, seed=2)}
    panel = build_panel(frames, horizon=5, relative_label=True)
    assert "cs_rank_ret_5" in panel.columns
    assert set(panel["label"].unique()).issubset({0, 1})
    # relative labels should be ~balanced vs always-long absolute
    if "label_absolute" in panel.columns:
        assert panel["label"].mean() != pytest.approx(panel["label_absolute"].mean(), abs=0.0)
