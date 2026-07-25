"""Market regime detection for smarter risk / scoring.

Uses universe cross-section of lagging features only (no lookahead).
Regimes adjust cash, top-N, and model/momentum blend weights.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from neotrade.signals.features import build_features


class Regime(str, Enum):
    """Coarse market regime for portfolio construction."""

    RISK_ON = "risk_on"  # calm trend — full book
    NEUTRAL = "neutral"  # default
    RISK_OFF = "risk_off"  # high vol / weak trend — de-risk


@dataclass(frozen=True)
class RegimeState:
    """Regime snapshot used by score blend and plan sizing."""

    regime: Regime
    vol_median: float
    trend_median: float
    # Blend: model vs momentum (sums to 1)
    w_model: float
    w_mom: float
    # Ranked book
    top_n: int
    min_cash_pct: float
    max_position_pct: float
    detail: str

    def summary_line(self) -> str:
        return (
            f"regime={self.regime.value} vol_med={self.vol_median:.4f} "
            f"trend_med={self.trend_median:.3f} blend={self.w_model:.0%}/{self.w_mom:.0%} "
            f"top_n={self.top_n} cash>={self.min_cash_pct:.0%} — {self.detail}"
        )


# Defaults tuned for neotrade-core-22 daily bars
_VOL_HIGH = 0.025  # median vol_20 above → risk-off leaning
_VOL_LOW = 0.012
_TREND_WEAK = 0.45  # median trend_strength_20


def detect_regime(
    frames: dict[str, pd.DataFrame],
    *,
    base_top_n: int = 5,
    base_min_cash: float = 0.01,
    base_max_pos: float = 0.18,
) -> RegimeState:
    """Infer regime from latest bar cross-section of vol_20 and trend_strength_20."""
    vols: list[float] = []
    trends: list[float] = []
    for _sym, ohlcv in frames.items():
        try:
            feats = build_features(ohlcv)
            if feats.empty:
                continue
            row = feats.iloc[-1]
            v = float(row.get("vol_20", np.nan))
            t = float(row.get("trend_strength_20", np.nan))
            if v == v and v > 0:
                vols.append(v)
            if t == t:
                trends.append(t)
        except (ValueError, KeyError, TypeError):
            continue

    vol_med = float(np.median(vols)) if vols else 0.015
    trend_med = float(np.median(trends)) if trends else 0.5

    if vol_med >= _VOL_HIGH or trend_med < _TREND_WEAK:
        return RegimeState(
            regime=Regime.RISK_OFF,
            vol_median=vol_med,
            trend_median=trend_med,
            w_model=0.50,
            w_mom=0.50,  # less chase in stress
            top_n=max(4, base_top_n - 1),
            min_cash_pct=min(0.15, base_min_cash + 0.04),
            max_position_pct=min(base_max_pos, 0.15),
            detail="elevated vol or weak breadth — slightly smaller book, balanced blend",
        )
    if vol_med <= _VOL_LOW and trend_med >= 0.55:
        return RegimeState(
            regime=Regime.RISK_ON,
            vol_median=vol_med,
            trend_median=trend_med,
            w_model=0.35,
            w_mom=0.65,
            top_n=base_top_n,
            min_cash_pct=base_min_cash,
            max_position_pct=base_max_pos,
            detail="calm + positive breadth — full top-N, momentum-tilted blend",
        )
    return RegimeState(
        regime=Regime.NEUTRAL,
        vol_median=vol_med,
        trend_median=trend_med,
        w_model=0.40,
        w_mom=0.60,
        top_n=base_top_n,
        min_cash_pct=base_min_cash,
        max_position_pct=base_max_pos,
        detail="mixed tape — default blend and book size",
    )


def detect_regime_from_close_panel(
    close_px: pd.DataFrame,
    asof_i: int,
    *,
    lookback: int = 20,
    base_top_n: int = 5,
    base_min_cash: float = 0.01,
    base_max_pos: float = 0.18,
) -> RegimeState:
    """Fast regime from close panel only (for backtest inner loop)."""
    if asof_i < lookback + 1 or close_px.empty:
        return RegimeState(
            regime=Regime.NEUTRAL,
            vol_median=0.015,
            trend_median=0.5,
            w_model=0.40,
            w_mom=0.60,
            top_n=base_top_n,
            min_cash_pct=base_min_cash,
            max_position_pct=base_max_pos,
            detail="insufficient history",
        )
    window = close_px.iloc[asof_i - lookback : asof_i + 1]
    rets = window.pct_change().iloc[1:]
    # cross-sectional median of each name's vol, then median across names
    name_vol = rets.std()
    vol_med = float(name_vol.median(skipna=True)) if len(name_vol) else 0.015
    # breadth: fraction of names with positive lookback return
    period_ret = window.iloc[-1] / window.iloc[0] - 1.0
    trend_med = float((period_ret > 0).mean()) if len(period_ret) else 0.5

    if vol_med >= _VOL_HIGH or trend_med < _TREND_WEAK:
        return RegimeState(
            regime=Regime.RISK_OFF,
            vol_median=vol_med,
            trend_median=trend_med,
            w_model=0.50,
            w_mom=0.50,
            top_n=max(4, base_top_n - 1),
            min_cash_pct=min(0.15, base_min_cash + 0.04),
            max_position_pct=min(base_max_pos, 0.15),
            detail="panel: high vol or weak breadth",
        )
    if vol_med <= _VOL_LOW and trend_med >= 0.55:
        return RegimeState(
            regime=Regime.RISK_ON,
            vol_median=vol_med,
            trend_median=trend_med,
            w_model=0.35,
            w_mom=0.65,
            top_n=base_top_n,
            min_cash_pct=base_min_cash,
            max_position_pct=base_max_pos,
            detail="panel: calm + positive breadth",
        )
    return RegimeState(
        regime=Regime.NEUTRAL,
        vol_median=vol_med,
        trend_median=trend_med,
        w_model=0.40,
        w_mom=0.60,
        top_n=base_top_n,
        min_cash_pct=base_min_cash,
        max_position_pct=base_max_pos,
        detail="panel: neutral",
    )
