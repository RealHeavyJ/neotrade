"""Score a ticker universe with a fitted SignalModel."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from neotrade.signals.model import SignalModel


@dataclass(frozen=True)
class SignalRow:
    symbol: str
    proba: float
    side: str
    as_of: str

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "proba": self.proba,
            "side": self.side,
            "as_of": self.as_of,
        }


def side_from_proba(proba: float, *, buy_threshold: float = 0.55, sell_threshold: float = 0.45) -> str:
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
) -> list[SignalRow]:
    rows: list[SignalRow] = []
    errors: list[str] = []
    for symbol, ohlcv in frames.items():
        try:
            series = model.predict_proba(ohlcv)
            if series.empty:
                errors.append(f"{symbol}: empty features")
                continue
            proba = float(series.iloc[-1])
            as_of = str(series.index[-1].date()) if hasattr(series.index[-1], "date") else str(series.index[-1])
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
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{symbol}: {exc}")
    rows.sort(key=lambda r: r.proba, reverse=True)
    # attach errors for CLI via attribute without changing return type contract much
    setattr(score_universe, "_last_errors", errors)
    return rows
