"""Pydantic models for ticker universe and data settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Ticker(BaseModel):
    symbol: str
    name: str = ""
    sector: str = ""
    sleeve: Literal["growth", "defensive"] = "growth"

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("symbol must be non-empty")
        return symbol


class Universe(BaseModel):
    name: str = "default"
    currency: str = "USD"
    exchange_bias: str = "NYSE_NASDAQ"


class DataSettings(BaseModel):
    cache_dir: Path = Path("data/cache")
    # auto = Alpaca bars first, yfinance fallback
    provider: Literal["auto", "alpaca", "yfinance"] = "auto"
    default_period: str = "1y"
    default_interval: str = "1d"
    max_age_hours: float = Field(default=24.0, gt=0)


class RiskSettings(BaseModel):
    max_position_pct: float = Field(default=0.08, gt=0, le=0.5)
    growth_target_pct: float = Field(default=0.68, ge=0, le=1)
    defensive_target_pct: float = Field(default=0.32, ge=0, le=1)
    max_new_positions: int = Field(default=8, ge=1)
    min_notional: float = Field(default=25.0, gt=0)
    min_cash_pct: float = Field(default=0.02, ge=0, le=0.5)
    buy_threshold: float = Field(default=0.55, ge=0, le=1)
    sell_threshold: float = Field(default=0.45, ge=0, le=1)
    paper_only: bool = True


class TickersConfig(BaseModel):
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
        return [t.symbol for t in self.tickers]
