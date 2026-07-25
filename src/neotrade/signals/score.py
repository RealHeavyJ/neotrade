"""Score a ticker universe with a fitted :class:`~neotrade.signals.model.SignalModel`.

Builds a same-day cross-section of lagging features so CS ranks match training,
then maps latest scores to buy/hold/sell.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from neotrade.logging_config import get_logger
from neotrade.signals.features import (
    CS_FEATURE_COLUMNS,
    add_cross_section_features,
    build_features,
)
from neotrade.signals.model import SignalModel

log = get_logger("signals.score")


@dataclass(frozen=True)
class SignalRow:
    """One symbol's latest model score.

    Attributes:
        symbol: Ticker symbol (uppercase).
        proba: Model score in ``[0, 1]`` (P(relative outperformance) when
            trained with ``label_mode=relative``).
        side: Discrete action label: ``buy``, ``hold``, or ``sell``.
        as_of: Date string of the bar used for the score.
    """

    symbol: str
    proba: float
    side: str
    as_of: str

    def to_dict(self) -> dict[str, object]:
        """Serialize for JSON / DataFrame construction."""
        return {
            "symbol": self.symbol,
            "proba": self.proba,
            "side": self.side,
            "as_of": self.as_of,
        }


@dataclass
class ScoreResult:
    """Universe scoring output including per-symbol failures."""

    rows: list[SignalRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def __iter__(self):
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index):
        return self.rows[index]


def side_from_proba(
    proba: float,
    *,
    buy_threshold: float = 0.55,
    sell_threshold: float = 0.45,
) -> str:
    """Map a probability to a discrete side."""
    if proba >= buy_threshold:
        return "buy"
    if proba <= sell_threshold:
        return "sell"
    return "hold"


def _latest_feature_panel(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per symbol: latest feature vector + dummy fwd_ret for CS helper."""
    parts: list[pd.DataFrame] = []
    for symbol, ohlcv in frames.items():
        try:
            feats = build_features(ohlcv)
            if feats.empty:
                continue
            row = feats.iloc[[-1]].copy()
            row["symbol"] = symbol
            row["fwd_ret"] = 0.0  # unused for scoring ranks
            row["label"] = 0
            parts.append(row)
        except (ValueError, KeyError) as exc:
            log.debug("skip features symbol=%s: %s", symbol, exc)
            continue
    if not parts:
        return pd.DataFrame()
    panel = pd.concat(parts, axis=0)
    # force a shared index date so groupby(level=0) is one cross-section
    as_of = panel.index.max()
    panel = panel.copy()
    panel.index = pd.DatetimeIndex([as_of] * len(panel))
    panel = add_cross_section_features(panel, relative_label=False)
    return panel


def score_universe(
    model: SignalModel,
    frames: dict[str, pd.DataFrame],
    *,
    buy_threshold: float = 0.55,
    sell_threshold: float = 0.45,
    w_model: float | None = None,
    w_mom: float | None = None,
) -> ScoreResult:
    """Score each symbol's latest bar with ``model``.

    When the model expects CS features, ranks are computed across the universe
    on the latest available bar set. Default blend is regime-aware (see
    :func:`~neotrade.signals.regime.detect_regime`) unless weights are passed.
    """
    if model.booster is None:
        raise RuntimeError("model is not fitted")

    if w_model is None or w_mom is None:
        try:
            from neotrade.signals.regime import detect_regime

            reg = detect_regime(frames)
            w_model = reg.w_model
            w_mom = reg.w_mom
            log.debug("%s", reg.summary_line())
        except (ValueError, KeyError, TypeError, RuntimeError) as exc:
            log.warning("regime blend fallback defaults: %s", exc)
            w_model, w_mom = 0.40, 0.60
    total_w = float(w_model) + float(w_mom)
    if total_w <= 0:
        w_model, w_mom = 0.40, 0.60
        total_w = 1.0
    w_model = float(w_model) / total_w
    w_mom = float(w_mom) / total_w

    needs_cs = any(c in model.feature_names for c in CS_FEATURE_COLUMNS)
    rows: list[SignalRow] = []
    errors: list[str] = []

    if needs_cs:
        panel = _latest_feature_panel(frames)
        if panel.empty:
            return ScoreResult(rows=[], errors=["no feature rows for any symbol"])
        for col in model.feature_names:
            if col not in panel.columns:
                panel[col] = 0.5 if col.startswith("cs_") else 0.0
        try:
            x = panel.loc[:, model.feature_names]
            proba = np.asarray(model.booster.predict(x), dtype=float)
        except (ValueError, KeyError) as exc:
            log.error("panel score failed: %s", exc)
            return ScoreResult(rows=[], errors=[f"panel: {exc}"])

        for i, (_, prow) in enumerate(panel.iterrows()):
            symbol = str(prow.get("symbol", ""))
            p_model = float(proba[i])
            mom_r = float(prow["cs_rank_ret_20"]) if "cs_rank_ret_20" in prow.index else 0.5
            if np.isnan(mom_r):
                mom_r = 0.5
            p = w_model * p_model + w_mom * mom_r
            p = float(min(1.0, max(0.0, p)))
            as_of = str(pd.Timestamp(prow.name).date()) if hasattr(prow.name, "day") else str(prow.name)
            rows.append(
                SignalRow(
                    symbol=symbol,
                    proba=p,
                    side=side_from_proba(
                        p,
                        buy_threshold=buy_threshold,
                        sell_threshold=sell_threshold,
                    ),
                    as_of=as_of,
                )
            )
    else:
        for symbol, ohlcv in frames.items():
            try:
                series = model.predict_proba(ohlcv)
                if series.empty:
                    errors.append(f"{symbol}: empty features")
                    continue
                proba = float(series.iloc[-1])
                as_of = (
                    str(series.index[-1].date())
                    if hasattr(series.index[-1], "date")
                    else str(series.index[-1])
                )
                rows.append(
                    SignalRow(
                        symbol=symbol,
                        proba=proba,
                        side=side_from_proba(
                            proba,
                            buy_threshold=buy_threshold,
                            sell_threshold=sell_threshold,
                        ),
                        as_of=as_of,
                    )
                )
            except (RuntimeError, ValueError, KeyError, TypeError) as exc:
                log.warning("score failed symbol=%s: %s", symbol, exc)
                errors.append(f"{symbol}: {exc}")

    rows.sort(key=lambda r: r.proba, reverse=True)
    log.debug("scored n=%s errors=%s", len(rows), len(errors))
    return ScoreResult(rows=rows, errors=errors)
