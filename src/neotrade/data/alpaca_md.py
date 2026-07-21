"""Alpaca market-data REST client (paper-safe credentials)."""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import pandas as pd

from neotrade.broker.credentials import AlpacaCredentials, load_alpaca_credentials

DEFAULT_DATA_URL = "https://data.alpaca.markets"
OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def _ssl_context() -> ssl.SSLContext:
    """Prefer certifi CA bundle (fixes macOS python.org CERTIFICATE_VERIFY_FAILED)."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def data_base_url() -> str:
    """Alpaca market-data REST host (no trailing ``/v2``)."""
    base = (
        os.environ.get("ALPACA_DATA_URL")
        or os.environ.get("APCA_API_DATA_URL")
        or DEFAULT_DATA_URL
    ).strip().rstrip("/")
    if base.endswith("/v2"):
        base = base[: -len("/v2")]
    return base


def data_feed() -> str:
    """Configured Alpaca market-data feed (defaults to ``iex``)."""
    return os.environ.get("ALPACA_DATA_FEED", "iex").strip().lower() or "iex"


@dataclass(frozen=True)
class LatestTrade:
    """Latest trade snapshot from Alpaca."""

    symbol: str
    price: float
    size: float | None = None
    ts: str = ""
    exchange: str = ""


@dataclass(frozen=True)
class LatestQuote:
    """Latest quote snapshot from Alpaca."""

    symbol: str
    bid: float | None = None
    ask: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    ts: str = ""

    @property
    def mid(self) -> float | None:
        if self.bid is not None and self.ask is not None and self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        if self.ask is not None:
            return self.ask
        return self.bid


def _f(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


class AlpacaMarketDataClient:
    """Small Alpaca market-data REST wrapper used by fetch/quotes paths."""

    def __init__(
        self,
        *,
        credentials: AlpacaCredentials | None = None,
        data_url: str | None = None,
        feed: str | None = None,
    ) -> None:
        self.credentials = credentials or load_alpaca_credentials(require_paper=True)
        self.data_url = (data_url or data_base_url()).rstrip("/")
        if self.data_url.endswith("/v2"):
            self.data_url = self.data_url[: -len("/v2")]
        self.feed = (feed or data_feed()).lower()

    def _request(self, path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
        query_str = f"?{urlencode(query)}" if query else ""
        url = f"{self.data_url}{path}{query_str}"
        req = urllib.request.Request(url, headers=self.credentials.headers(), method="GET")
        try:
            # context= is required on macOS python.org builds (certifi CA bundle)
            with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as res:
                payload = res.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Alpaca data API {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Alpaca data network/SSL error: {exc.reason}") from exc
        data = json.loads(payload) if payload else {}
        if not isinstance(data, dict):
            raise RuntimeError("unexpected Alpaca market-data response")
        return data

    def get_latest_trades(self, symbols: list[str]) -> dict[str, LatestTrade]:
        """Return latest trade per symbol."""
        syms = [s.strip().upper() for s in symbols if s and s.strip()]
        if not syms:
            return {}
        data = self._request(
            "/v2/stocks/trades/latest",
            query={"symbols": ",".join(syms), "feed": self.feed},
        )
        trades_raw = data.get("trades")
        if not isinstance(trades_raw, dict):
            return {}
        out: dict[str, LatestTrade] = {}
        for sym, row in trades_raw.items():
            if not isinstance(row, dict):
                continue
            price = _f(row.get("p"))
            if price is None:
                continue
            out[str(sym).upper()] = LatestTrade(
                symbol=str(sym).upper(),
                price=price,
                size=_f(row.get("s")),
                ts=str(row.get("t") or ""),
                exchange=str(row.get("x") or ""),
            )
        return out

    def get_latest_quotes(self, symbols: list[str]) -> dict[str, LatestQuote]:
        """Return latest bid/ask quote per symbol."""
        syms = [s.strip().upper() for s in symbols if s and s.strip()]
        if not syms:
            return {}
        data = self._request(
            "/v2/stocks/quotes/latest",
            query={"symbols": ",".join(syms), "feed": self.feed},
        )
        quotes_raw = data.get("quotes")
        if not isinstance(quotes_raw, dict):
            return {}
        out: dict[str, LatestQuote] = {}
        for sym, row in quotes_raw.items():
            if not isinstance(row, dict):
                continue
            out[str(sym).upper()] = LatestQuote(
                symbol=str(sym).upper(),
                bid=_f(row.get("bp")),
                ask=_f(row.get("ap")),
                bid_size=_f(row.get("bs")),
                ask_size=_f(row.get("as")),
                ts=str(row.get("t") or ""),
            )
        return out

    def get_stock_bars(
        self,
        symbol: str,
        *,
        timeframe: str = "1Day",
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 10_000,
    ) -> pd.DataFrame:
        """Fetch Alpaca bars and normalize to OHLCV frame."""
        sym = symbol.strip().upper()
        query: dict[str, Any] = {"timeframe": timeframe, "limit": int(limit), "feed": self.feed}
        if start is not None:
            query["start"] = start.isoformat()
        if end is not None:
            query["end"] = end.isoformat()
        data = self._request(f"/v2/stocks/{sym}/bars", query=query)
        bars_obj = data.get("bars", [])
        rows: list[dict[str, Any]]
        if isinstance(bars_obj, dict):
            rows = list(bars_obj.get(sym, []))
        elif isinstance(bars_obj, list):
            rows = list(bars_obj)
        else:
            rows = []
        if not rows:
            raise RuntimeError(f"no bars returned for {sym}")
        frame = pd.DataFrame(rows)
        frame["Date"] = pd.to_datetime(frame["t"], utc=True)
        frame = frame.set_index("Date")
        out = pd.DataFrame(
            {
                "Open": pd.to_numeric(frame.get("o"), errors="coerce"),
                "High": pd.to_numeric(frame.get("h"), errors="coerce"),
                "Low": pd.to_numeric(frame.get("l"), errors="coerce"),
                "Close": pd.to_numeric(frame.get("c"), errors="coerce"),
                "Volume": pd.to_numeric(frame.get("v"), errors="coerce"),
            },
            index=frame.index,
        )
        out = out[OHLCV_COLUMNS].dropna(subset=["Close"]).sort_index()
        if out.empty:
            raise RuntimeError(f"no valid bars returned for {sym}")
        return out
