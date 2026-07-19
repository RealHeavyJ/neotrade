import numpy as np
import pandas as pd
import pytest

from neotrade.signals.features import FEATURE_COLUMNS, build_features, build_labeled_frame


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
    feats = build_features(_synth_ohlcv())
    assert list(feats.columns) == list(FEATURE_COLUMNS)
    assert feats.isna().sum().sum() == 0
    assert len(feats) >= 50


def test_build_features_too_short():
    with pytest.raises(ValueError, match="60"):
        build_features(_synth_ohlcv(n=40))


def test_labeled_frame_has_binary_labels():
    labeled = build_labeled_frame(_synth_ohlcv(), horizon=5)
    assert set(labeled["label"].unique()).issubset({0, 1})
    assert "fwd_ret" in labeled.columns
