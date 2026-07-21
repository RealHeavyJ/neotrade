"""Technical features from OHLCV bars for LightGBM signals.

All public feature names are listed in :data:`FEATURE_COLUMNS`. Frames must
include columns Open, High, Low, Close, Volume with a DatetimeIndex.

Labels (see :func:`build_labeled_frame`) default to **relative** outperformance
vs the cross-sectional median forward return when a panel is built — matching
rank-based portfolio construction. Absolute up/down remains available.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Max lookback used by any feature (for leakage docs / min bars)
MAX_LOOKBACK_BARS = 60

FEATURE_COLUMNS: tuple[str, ...] = (
    # returns
    "ret_1",
    "ret_3",
    "ret_5",
    "ret_10",
    "ret_20",
    "ret_60",
    # vol / range
    "vol_10",
    "vol_20",
    "vol_ratio_5_20",
    "atr_14_pct",
    "high_low_range",
    # trend / mean-reversion
    "rsi_14",
    "sma_ratio_10",
    "sma_ratio_20",
    "sma_ratio_50",
    "ema_ratio_12",
    "macd_hist",
    "bb_pct_20",
    "dist_high_20",
    "dist_low_20",
    # volume / microstructure-ish
    "volume_z_20",
    "volume_ratio_5_20",
    "close_open_ret",
    "gap_ret",
    # composite
    "mom_vol_20",
    "trend_strength_20",
)

# Added on panel only (cross-sectional ranks; still lagging info as-of that date)
CS_FEATURE_COLUMNS: tuple[str, ...] = (
    "cs_rank_ret_5",
    "cs_rank_ret_20",
    "cs_rank_vol_20",
    "cs_rank_rsi_14",
    "cs_rank_mom_vol_20",
)

ALL_MODEL_FEATURES: tuple[str, ...] = FEATURE_COLUMNS + CS_FEATURE_COLUMNS


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Wilder-style RSI via EWM of gains/losses."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr_pct(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(window, min_periods=window).mean()
    return atr / close.replace(0.0, np.nan)


def build_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Compute per-symbol lagging features; drop incomplete leading windows.

    Args:
        ohlcv: OHLCV frame with at least :data:`MAX_LOOKBACK_BARS` bars.

    Returns:
        DataFrame with columns :data:`FEATURE_COLUMNS`, NaN-free.

    Raises:
        ValueError: Missing columns or insufficient history.
    """
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(ohlcv.columns)
    if missing:
        raise ValueError(f"ohlcv missing columns: {sorted(missing)}")
    if len(ohlcv) < MAX_LOOKBACK_BARS:
        raise ValueError(
            f"need at least {MAX_LOOKBACK_BARS} bars for features, got {len(ohlcv)}"
        )

    close = ohlcv["Close"].astype(float)
    open_ = ohlcv["Open"].astype(float)
    high = ohlcv["High"].astype(float)
    low = ohlcv["Low"].astype(float)
    volume = ohlcv["Volume"].astype(float)

    ret_1 = close.pct_change(1)
    out = pd.DataFrame(index=ohlcv.index)
    out["ret_1"] = ret_1
    out["ret_3"] = close.pct_change(3)
    out["ret_5"] = close.pct_change(5)
    out["ret_10"] = close.pct_change(10)
    out["ret_20"] = close.pct_change(20)
    out["ret_60"] = close.pct_change(60)

    out["vol_10"] = ret_1.rolling(10).std()
    out["vol_20"] = ret_1.rolling(20).std()
    vol_5 = ret_1.rolling(5).std()
    out["vol_ratio_5_20"] = vol_5 / out["vol_20"].replace(0.0, np.nan)
    out["atr_14_pct"] = _atr_pct(high, low, close, 14)
    out["high_low_range"] = (high - low) / close.replace(0.0, np.nan)

    out["rsi_14"] = _rsi(close, 14)
    sma10 = close.rolling(10).mean()
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    out["sma_ratio_10"] = close / sma10 - 1.0
    out["sma_ratio_20"] = close / sma20 - 1.0
    out["sma_ratio_50"] = close / sma50 - 1.0

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["ema_ratio_12"] = close / ema12 - 1.0
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    out["macd_hist"] = (macd - signal) / close.replace(0.0, np.nan)

    bb_mid = sma20
    bb_std = close.rolling(20).std()
    bb_low = bb_mid - 2.0 * bb_std
    bb_high = bb_mid + 2.0 * bb_std
    out["bb_pct_20"] = (close - bb_low) / (bb_high - bb_low).replace(0.0, np.nan)

    roll_high = close.rolling(20).max()
    roll_low = close.rolling(20).min()
    out["dist_high_20"] = close / roll_high - 1.0
    out["dist_low_20"] = close / roll_low.replace(0.0, np.nan) - 1.0

    vol_mean = volume.rolling(20).mean()
    vol_std = volume.rolling(20).std()
    out["volume_z_20"] = (volume - vol_mean) / vol_std.replace(0.0, np.nan)
    out["volume_ratio_5_20"] = volume.rolling(5).mean() / vol_mean.replace(0.0, np.nan)
    out["close_open_ret"] = close / open_ - 1.0
    prev_close = close.shift(1)
    out["gap_ret"] = open_ / prev_close.replace(0.0, np.nan) - 1.0

    out["mom_vol_20"] = out["ret_20"] / out["vol_20"].replace(0.0, np.nan)
    # fraction of last 20 days up — simple trend persistence
    up = (ret_1 > 0).astype(float)
    out["trend_strength_20"] = up.rolling(20).mean()

    out = out.loc[:, list(FEATURE_COLUMNS)]
    return out.dropna()


def build_labeled_frame(
    ohlcv: pd.DataFrame,
    *,
    horizon: int = 5,
    label_mode: str = "absolute",
) -> pd.DataFrame:
    """Features plus label and forward return.

    Args:
        ohlcv: OHLCV bars.
        horizon: Forward return window in bars.
        label_mode: ``absolute`` → label = fwd_ret > 0.
            ``relative`` is applied later at panel level (see
            :func:`add_cross_section_features`).

    Returns:
        Feature columns plus ``fwd_ret`` and binary ``label`` (absolute unless
        overwritten by panel relative labeling).
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if label_mode not in {"absolute", "relative"}:
        raise ValueError("label_mode must be 'absolute' or 'relative'")
    feats = build_features(ohlcv)
    close = ohlcv["Close"].astype(float)
    fwd = close.shift(-horizon) / close - 1.0
    frame = feats.copy()
    frame["fwd_ret"] = fwd.reindex(feats.index)
    frame["label"] = (frame["fwd_ret"] > 0.0).astype(int)
    return frame.dropna(subset=["fwd_ret"])


def add_cross_section_features(
    panel: pd.DataFrame,
    *,
    relative_label: bool = True,
) -> pd.DataFrame:
    """Add same-day cross-sectional ranks and optional relative labels.

    Ranks use only information available on date t (feature values at t).
    Relative label: 1 if ``fwd_ret`` exceeds that date's cross-sectional median
    (stock-picking objective aligned with ranking by signal proba).

    Args:
        panel: Multi-symbol frame with DatetimeIndex (duplicate dates OK) and
            columns including FEATURE_COLUMNS, ``fwd_ret``, ``label``, ``symbol``.
        relative_label: If True, overwrite ``label`` with relative outperformance.

    Returns:
        Panel with CS_FEATURE_COLUMNS and updated label.
    """
    if panel.empty:
        return panel
    out = panel.copy()
    g = out.groupby(level=0, group_keys=False)

    def _rank(s: pd.Series) -> pd.Series:
        return s.rank(pct=True, method="average")

    for col, src in (
        ("cs_rank_ret_5", "ret_5"),
        ("cs_rank_ret_20", "ret_20"),
        ("cs_rank_vol_20", "vol_20"),
        ("cs_rank_rsi_14", "rsi_14"),
        ("cs_rank_mom_vol_20", "mom_vol_20"),
    ):
        if src not in out.columns:
            out[col] = 0.5
        else:
            out[col] = g[src].transform(_rank)

    if relative_label and "fwd_ret" in out.columns:
        med = g["fwd_ret"].transform("median")
        out["label_absolute"] = (out["fwd_ret"] > 0.0).astype(int)
        out["label"] = (out["fwd_ret"] > med).astype(int)

    # fill any residual CS nan
    for col in CS_FEATURE_COLUMNS:
        if col in out.columns:
            out[col] = out[col].fillna(0.5)
    return out


def model_feature_names(*, include_cs: bool = True) -> list[str]:
    """Feature list used by SignalModel / eval."""
    if include_cs:
        return list(ALL_MODEL_FEATURES)
    return list(FEATURE_COLUMNS)
