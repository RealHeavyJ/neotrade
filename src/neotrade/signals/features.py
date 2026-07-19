"""Technical features from OHLCV bars."""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_COLUMNS: tuple[str, ...] = (
    "ret_1",
    "ret_5",
    "ret_10",
    "ret_20",
    "vol_10",
    "vol_20",
    "rsi_14",
    "sma_ratio_10",
    "sma_ratio_20",
    "sma_ratio_50",
    "bb_pct_20",
    "volume_z_20",
    "high_low_range",
    "close_open_ret",
)


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def build_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Return feature frame aligned to ohlcv index; leading NaNs dropped."""
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(ohlcv.columns)
    if missing:
        raise ValueError(f"ohlcv missing columns: {sorted(missing)}")
    if len(ohlcv) < 60:
        raise ValueError(f"need at least 60 bars for features, got {len(ohlcv)}")

    close = ohlcv["Close"].astype(float)
    open_ = ohlcv["Open"].astype(float)
    high = ohlcv["High"].astype(float)
    low = ohlcv["Low"].astype(float)
    volume = ohlcv["Volume"].astype(float)

    ret_1 = close.pct_change(1)
    out = pd.DataFrame(index=ohlcv.index)
    out["ret_1"] = ret_1
    out["ret_5"] = close.pct_change(5)
    out["ret_10"] = close.pct_change(10)
    out["ret_20"] = close.pct_change(20)
    out["vol_10"] = ret_1.rolling(10).std()
    out["vol_20"] = ret_1.rolling(20).std()
    out["rsi_14"] = _rsi(close, 14)

    sma10 = close.rolling(10).mean()
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    out["sma_ratio_10"] = close / sma10 - 1.0
    out["sma_ratio_20"] = close / sma20 - 1.0
    out["sma_ratio_50"] = close / sma50 - 1.0

    bb_mid = sma20
    bb_std = close.rolling(20).std()
    bb_low = bb_mid - 2.0 * bb_std
    bb_high = bb_mid + 2.0 * bb_std
    out["bb_pct_20"] = (close - bb_low) / (bb_high - bb_low).replace(0.0, np.nan)

    vol_mean = volume.rolling(20).mean()
    vol_std = volume.rolling(20).std()
    out["volume_z_20"] = (volume - vol_mean) / vol_std.replace(0.0, np.nan)
    out["high_low_range"] = (high - low) / close.replace(0.0, np.nan)
    out["close_open_ret"] = close / open_ - 1.0

    out = out.loc[:, list(FEATURE_COLUMNS)]
    return out.dropna()


def build_labeled_frame(ohlcv: pd.DataFrame, *, horizon: int = 5) -> pd.DataFrame:
    """Features plus binary label: forward close return over horizon > 0."""
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    feats = build_features(ohlcv)
    close = ohlcv["Close"].astype(float)
    fwd = close.shift(-horizon) / close - 1.0
    frame = feats.copy()
    frame["fwd_ret"] = fwd.reindex(feats.index)
    frame["label"] = (frame["fwd_ret"] > 0.0).astype(int)
    return frame.dropna(subset=["fwd_ret"])
