import numpy as np
import pandas as pd
import pytest

from neotrade.signals.features import (
    FEATURE_COLUMNS,
    MAX_LOOKBACK_BARS,
    add_cross_section_features,
    build_features,
    build_labeled_frame,
)


def _synth_ohlcv(n: int = 120, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-01-02", periods=n)
    rets = rng.normal(0.0005, 0.015, size=n)
    close = 100 * np.cumprod(1 + rets)
    open_ = close * (1 + rng.normal(0, 0.002, size=n))
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, size=n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, size=n))
    volume = rng.integers(1_000_000, 5_000_000, size=n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


def test_build_features_columns_and_no_nan():
    feats = build_features(_synth_ohlcv(n=150))
    assert list(feats.columns) == list(FEATURE_COLUMNS)
    assert feats.isna().sum().sum() == 0
    assert len(feats) >= 50


def test_build_features_too_short():
    with pytest.raises(ValueError, match=str(MAX_LOOKBACK_BARS)):
        build_features(_synth_ohlcv(n=40))


def test_labeled_frame_has_binary_labels():
    labeled = build_labeled_frame(_synth_ohlcv(n=150), horizon=5)
    assert set(labeled["label"].unique()).issubset({0, 1})
    assert "fwd_ret" in labeled.columns


def test_cross_section_relative_label():
    idx = pd.to_datetime(["2024-06-03", "2024-06-03", "2024-06-04", "2024-06-04"])
    panel = pd.DataFrame(
        {
            "ret_5": [0.1, -0.1, 0.0, 0.05],
            "ret_20": [0.0, 0.0, 0.0, 0.0],
            "vol_20": [0.01, 0.02, 0.01, 0.01],
            "rsi_14": [40.0, 60.0, 50.0, 55.0],
            "mom_vol_20": [1.0, -1.0, 0.0, 0.5],
            "fwd_ret": [0.05, -0.02, 0.01, 0.03],
            "label": [1, 0, 1, 1],
            "symbol": ["A", "B", "A", "B"],
        },
        index=idx,
    )
    out = add_cross_section_features(panel, relative_label=True)
    assert "cs_rank_ret_5" in out.columns
    # day1: A fwd 0.05 > median, B -0.02 < median
    day1 = out.loc["2024-06-03"]
    labels = dict(zip(day1["symbol"], day1["label"], strict=False))
    assert labels["A"] == 1
    assert labels["B"] == 0
