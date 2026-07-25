"""OHLCV fetch/load orchestration for configured universe tickers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yfinance as yf

from neotrade.config.load import project_root, resolve_cache_dir
from neotrade.config.models import TickersConfig
from neotrade.data.alpaca_md import AlpacaMarketDataClient
from neotrade.data.cache import (
    OHLCV_COLUMNS,
    cache_path,
    is_cache_fresh,
    load_cached_ohlcv,
    save_ohlcv,
)

ALLOWED_PROVIDERS = {"auto", "alpaca", "yfinance"}


@dataclass
class UniverseBars:
    """Universe OHLCV result with partial-load errors."""

    frames: dict[str, pd.DataFrame]
    errors: list[str] = field(default_factory=list)

    def symbols(self) -> list[str]:
        return list(self.frames.keys())


def _normalize_ohlcv(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame.empty:
        raise RuntimeError(f"empty OHLCV for {symbol}")
    out = frame.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [c[0] for c in out.columns]
    for col in OHLCV_COLUMNS:
        if col not in out.columns:
            raise RuntimeError(f"missing {col} in OHLCV for {symbol}")
    out.index = pd.to_datetime(out.index)
    out = out[OHLCV_COLUMNS].sort_index()
    out = out.dropna(subset=["Close"])
    if out.empty:
        raise RuntimeError(f"no valid OHLCV rows for {symbol}")
    return out


def _download_yfinance(symbol: str, *, period: str, interval: str) -> pd.DataFrame:
    frame = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        group_by="column",
        threads=False,
    )
    return _normalize_ohlcv(frame, symbol)


def _download_alpaca(symbol: str, *, interval: str, period: str) -> pd.DataFrame:
    if interval != "1d":
        raise RuntimeError(f"Alpaca fetch supports interval=1d only (got {interval})")
    client = AlpacaMarketDataClient()
    timeframe = "1Day"
    frame = client.get_stock_bars(symbol, timeframe=timeframe, limit=10_000)
    return _normalize_ohlcv(frame, symbol)


def download_ohlcv(
    symbol: str,
    *,
    provider: str = "auto",
    period: str = "1y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Download one symbol's OHLCV frame from configured provider."""
    provider = (provider or "auto").lower()
    if provider not in ALLOWED_PROVIDERS:
        raise ValueError(f"unsupported provider: {provider}")
    if provider == "yfinance":
        return _download_yfinance(symbol, period=period, interval=interval)
    if provider == "alpaca":
        return _download_alpaca(symbol, interval=interval, period=period)
    try:
        return _download_alpaca(symbol, interval=interval, period=period)
    except (RuntimeError, OSError, ValueError):
        return _download_yfinance(symbol, period=period, interval=interval)


def fetch_ohlcv(
    symbol: str,
    *,
    cache_dir: Path,
    period: str = "1y",
    interval: str = "1d",
    max_age_hours: float = 24.0,
    force_refresh: bool = False,
    provider: str = "auto",
) -> pd.DataFrame:
    """Load one symbol from cache when fresh, else download and cache."""
    path = cache_path(cache_dir, symbol, interval, period)
    if not force_refresh and is_cache_fresh(path, max_age_hours=max_age_hours):
        return load_cached_ohlcv(path)
    frame = download_ohlcv(symbol, provider=provider, period=period, interval=interval)
    save_ohlcv(path, frame)
    return frame


def load_universe_ohlcv(
    cfg: TickersConfig,
    *,
    root: Path | None = None,
    force_refresh: bool = False,
    provider: str | None = None,
) -> UniverseBars:
    """Load OHLCV for all configured tickers with partial-error tolerance."""
    root = root or project_root()
    provider = (provider or cfg.data.provider).lower()
    cache_dir = resolve_cache_dir(cfg.data.cache_dir, root)
    frames: dict[str, pd.DataFrame] = {}
    errors: list[str] = []
    for ticker in cfg.tickers:
        sym = ticker.symbol
        try:
            frames[sym] = fetch_ohlcv(
                sym,
                cache_dir=cache_dir,
                period=cfg.data.default_period,
                interval=cfg.data.default_interval,
                max_age_hours=cfg.data.max_age_hours,
                force_refresh=force_refresh,
                provider=provider,
            )
        except (RuntimeError, OSError, ValueError) as exc:
            errors.append(f"{sym}: {exc}")
    if not frames:
        raise RuntimeError(f"failed to load universe OHLCV ({len(cfg.tickers)} symbols)")
    return UniverseBars(frames=frames, errors=errors)


def prices_for_plan(
    cfg: TickersConfig,
    *,
    frames: dict[str, pd.DataFrame] | None = None,
) -> dict[str, float]:
    """Return latest close per configured symbol for trade-plan sizing."""
    prices: dict[str, float] = {}
    for ticker in cfg.tickers:
        sym = ticker.symbol
        frame = (frames or {}).get(sym)
        if frame is None or frame.empty:
            continue
        try:
            prices[sym] = float(frame["Close"].iloc[-1])
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    return prices
