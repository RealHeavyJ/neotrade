"""Latest quote/trade snapshot helpers for monitor and CLI surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from neotrade.config import load_tickers_config
from neotrade.config.load import project_root, resolve_cache_dir
from neotrade.config.models import TickersConfig
from neotrade.data.alpaca_md import AlpacaMarketDataClient
from neotrade.data.cache import cache_path, load_cached_ohlcv


@dataclass
class QuoteRow:
    """One latest quote/trade point for a symbol."""

    symbol: str
    price: float | None = None
    bid: float | None = None
    ask: float | None = None
    size: float | None = None
    ts: str = ""
    source: str = ""
    sleeve: str = ""

    @property
    def mid(self) -> float | None:
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2.0
        return None

    def display_price(self) -> float | None:
        return self.price if self.price is not None else self.mid

    def to_dict(self) -> dict[str, str | float | None]:
        return {
            "symbol": self.symbol,
            "price": self.display_price(),
            "bid": self.bid,
            "ask": self.ask,
            "size": self.size,
            "ts": self.ts,
            "source": self.source,
            "sleeve": self.sleeve,
        }


@dataclass
class QuoteSnapshot:
    """Universe-level snapshot of latest rows + non-fatal errors."""

    rows: list[QuoteRow]
    feed: str = ""
    errors: list[str] = field(default_factory=list)

    def prices(self) -> dict[str, float]:
        return {r.symbol: px for r in self.rows if (px := r.display_price()) is not None}


def _apply_cache_fallback(cfg: TickersConfig, rows: list[QuoteRow], errors: list[str]) -> None:
    cache_dir = resolve_cache_dir(cfg.data.cache_dir, project_root())
    for row in rows:
        if row.display_price() is not None:
            continue
        path = cache_path(cache_dir, row.symbol, cfg.data.default_interval, cfg.data.default_period)
        try:
            frame = load_cached_ohlcv(path)
        except (OSError, ValueError):
            continue
        if frame.empty:
            continue
        try:
            row.price = float(frame["Close"].iloc[-1])
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        row.source = row.source or "cache:close"
    if not any(r.display_price() is not None for r in rows):
        errors.append("no prices available from Alpaca or cache")


def fetch_universe_quotes(
    cfg: TickersConfig | None = None,
    *,
    prefer_alpaca: bool = True,
    fallback_cache: bool = True,
) -> QuoteSnapshot:
    """Fetch latest quotes/trades for configured universe symbols."""
    cfg = cfg or load_tickers_config()
    rows = [QuoteRow(symbol=t.symbol, sleeve=t.sleeve) for t in cfg.tickers]
    errors: list[str] = []
    feed = ""

    if prefer_alpaca:
        try:
            client = AlpacaMarketDataClient()
            feed = client.feed
            symbols = [r.symbol for r in rows]
            trades = client.get_latest_trades(symbols)
            quotes = client.get_latest_quotes(symbols)
            for row in rows:
                trade = trades.get(row.symbol)
                quote = quotes.get(row.symbol)
                if trade is not None:
                    row.price = trade.price
                    row.size = trade.size
                    row.ts = trade.ts
                    row.source = f"alpaca:{client.feed}"
                if quote is not None:
                    row.bid = quote.bid
                    row.ask = quote.ask
                    if not row.ts:
                        row.ts = quote.ts
                    if not row.source:
                        row.source = f"alpaca:{client.feed}"
        except (RuntimeError, OSError, ValueError) as exc:
            errors.append(f"alpaca quotes unavailable: {exc}")

    if fallback_cache:
        _apply_cache_fallback(cfg, rows, errors)

    return QuoteSnapshot(rows=rows, feed=feed, errors=errors)
