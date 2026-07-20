"""Score a ticker universe with a fitted :class:`~neotrade.signals.model.SignalModel`.

Maps latest P(up) estimates to discrete sides (buy / hold / sell) using
configurable probability thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from neotrade.signals.model import SignalModel


@dataclass(frozen=True)
class SignalRow:
    """One symbol's latest model score.

    Attributes:
        symbol: Ticker symbol (uppercase).
        proba: Model P(forward return > 0) in ``[0, 1]``.
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
    """Universe scoring output including per-symbol failures.

    Attributes:
        rows: Scores sorted by ``proba`` descending.
        errors: Human-readable per-symbol error messages (empty if all ok).
    """

    rows: list[SignalRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def __iter__(self):
        """Iterate score rows (allows ``for row in score_universe(...)``)."""
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index):
        """Index/slice rows (``result[0]``, ``result[:25]``)."""
        return self.rows[index]


def side_from_proba(
    proba: float,
    *,
    buy_threshold: float = 0.55,
    sell_threshold: float = 0.45,
) -> str:
    """Map a probability to a discrete side.

    Args:
        proba: Predicted P(up).
        buy_threshold: Inclusive lower bound for ``buy``.
        sell_threshold: Inclusive upper bound for ``sell``.

    Returns:
        ``buy``, ``sell``, or ``hold``.
    """
    if proba >= buy_threshold:
        return "buy"
    if proba <= sell_threshold:
        return "sell"
    return "hold"


def score_universe(
    model: SignalModel,
    frames: dict[str, pd.DataFrame],
    *,
    buy_threshold: float = 0.55,
    sell_threshold: float = 0.45,
) -> ScoreResult:
    """Score each symbol's latest bar with ``model``.

    Args:
        model: Fitted :class:`SignalModel`.
        frames: Map of symbol → OHLCV DataFrame (must include standard columns).
        buy_threshold: Buy side cutoff.
        sell_threshold: Sell side cutoff.

    Returns:
        :class:`ScoreResult` with ranked rows and any per-symbol errors.
        Also supports iteration over ``rows`` for backward compatibility.
    """
    rows: list[SignalRow] = []
    errors: list[str] = []
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
        except Exception as exc:  # noqa: BLE001 - collect and continue
            errors.append(f"{symbol}: {exc}")
    rows.sort(key=lambda r: r.proba, reverse=True)
    return ScoreResult(rows=rows, errors=errors)
