"""Regime detection unit tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from neotrade.signals.regime import Regime, detect_regime, detect_regime_from_close_panel


def _ohlcv(n: int = 100, vol: float = 0.01, drift: float = 0.001) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2024-01-02", periods=n)
    rets = rng.normal(drift, vol, size=n)
    close = 100 * np.cumprod(1 + rets)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * 1.005
    low = np.minimum(open_, close) * 0.995
    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": rng.integers(1e6, 2e6, size=n),
        },
        index=idx,
    )


def test_detect_regime_returns_state():
    frames = {"A": _ohlcv(vol=0.01), "B": _ohlcv(vol=0.01, drift=0.002)}
    st = detect_regime(frames, base_top_n=5)
    assert st.regime in {Regime.RISK_ON, Regime.NEUTRAL, Regime.RISK_OFF}
    assert abs(st.w_model + st.w_mom - 1.0) < 1e-6
    assert st.top_n >= 1


def test_detect_regime_high_vol_risk_off():
    frames = {s: _ohlcv(vol=0.05, drift=0.0) for s in ["A", "B", "C"]}
    st = detect_regime(frames, base_top_n=5)
    assert st.regime == Regime.RISK_OFF
    assert st.min_cash_pct >= 0.04
    assert st.top_n <= 5


def test_panel_regime_matches_shape():
    idx = pd.bdate_range("2024-01-02", periods=80)
    rng = np.random.default_rng(1)
    data = {}
    for s in ["A", "B", "C"]:
        rets = rng.normal(0.001, 0.01, size=len(idx))
        data[s] = 100 * np.cumprod(1 + rets)
    close = pd.DataFrame(data, index=idx)
    st = detect_regime_from_close_panel(close, asof_i=60, base_top_n=5)
    assert st.regime in Regime
    assert st.summary_line()
