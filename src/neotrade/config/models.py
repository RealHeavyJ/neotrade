"""Pydantic models for ticker universe, data, and risk settings.

These models are the schema for ``config/tickers.yaml``. Field descriptions
aid IDE hover docs and future OpenAPI / JSON-schema export.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Ticker(BaseModel):
    """One tradable name in the neotrade universe."""

    symbol: str = Field(..., description="Exchange ticker, normalized to uppercase")
    name: str = Field(default="", description="Optional display name")
    sector: str = Field(default="", description="GICS-style sector label")
    sleeve: Literal["growth", "defensive"] = Field(
        default="growth",
        description="Portfolio sleeve for 68/32 diversification targets",
    )

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("symbol must be non-empty")
        return symbol


class Universe(BaseModel):
    """Named basket metadata (not used for routing)."""

    name: str = "default"
    currency: str = "USD"
    exchange_bias: str = "NYSE_NASDAQ"


class DataSettings(BaseModel):
    """OHLCV cache and provider preferences."""

    cache_dir: Path = Path("data/cache")
    provider: Literal["auto", "alpaca", "yfinance"] = Field(
        default="auto",
        description="auto = Alpaca bars first, yfinance fallback",
    )
    default_period: str = "2y"  # production default (see neotrade.defaults)
    default_interval: str = "1d"
    max_age_hours: float = Field(default=24.0, gt=0)


class RiskSettings(BaseModel):
    """YAML-serializable risk knobs (mirrored by :class:`RiskLimits`)."""

    max_position_pct: float = Field(default=0.12, gt=0, le=0.5)
    growth_target_pct: float = Field(default=0.68, ge=0, le=1)
    defensive_target_pct: float = Field(default=0.32, ge=0, le=1)
    max_new_positions: int = Field(default=8, ge=1)
    min_notional: float = Field(default=25.0, gt=0)
    min_cash_pct: float = Field(default=0.01, ge=0, le=0.5)
    buy_threshold: float = Field(default=0.50, ge=0, le=1)
    sell_threshold: float = Field(default=0.40, ge=0, le=1)
    plan_mode: Literal["ranked", "sides"] = "ranked"
    top_n: int = Field(default=7, ge=1, le=30)
    rebalance_band_pct: float = Field(default=0.15, ge=0, le=0.5)
    paper_only: bool = True


class TickersConfig(BaseModel):
    """Root config document for neotrade."""

    universe: Universe = Field(default_factory=Universe)
    tickers: list[Ticker]
    data: DataSettings = Field(default_factory=DataSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)

    @field_validator("tickers")
    @classmethod
    def require_tickers(cls, value: list[Ticker]) -> list[Ticker]:
        if not value:
            raise ValueError("tickers must contain at least one symbol")
        symbols = [t.symbol for t in value]
        if len(symbols) != len(set(symbols)):
            raise ValueError("duplicate ticker symbols are not allowed")
        return value

    def symbols(self) -> list[str]:
        """Ordered list of configured ticker symbols."""
        return [t.symbol for t in self.tickers]
