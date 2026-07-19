"""Risk limits and sleeve targets for paper trading."""

from __future__ import annotations

from dataclasses import dataclass

from neotrade.config.models import TickersConfig


@dataclass(frozen=True)
class RiskLimits:
    max_position_pct: float = 0.08
    growth_target_pct: float = 0.68
    defensive_target_pct: float = 0.32
    max_new_positions: int = 8
    min_notional: float = 25.0
    min_cash_pct: float = 0.02
    buy_threshold: float = 0.55
    sell_threshold: float = 0.45
    paper_only: bool = True

    def validate(self) -> None:
        if self.max_position_pct <= 0 or self.max_position_pct > 0.5:
            raise ValueError("max_position_pct must be in (0, 0.5]")
        total = self.growth_target_pct + self.defensive_target_pct
        if abs(total - 1.0) > 1e-6:
            raise ValueError("growth_target_pct + defensive_target_pct must equal 1.0")


def default_risk_limits(cfg: TickersConfig | None = None) -> RiskLimits:
    if cfg is None or cfg.risk is None:
        limits = RiskLimits()
    else:
        r = cfg.risk
        limits = RiskLimits(
            max_position_pct=r.max_position_pct,
            growth_target_pct=r.growth_target_pct,
            defensive_target_pct=r.defensive_target_pct,
            max_new_positions=r.max_new_positions,
            min_notional=r.min_notional,
            min_cash_pct=r.min_cash_pct,
            buy_threshold=r.buy_threshold,
            sell_threshold=r.sell_threshold,
            paper_only=r.paper_only,
        )
    limits.validate()
    return limits


def sleeve_map(cfg: TickersConfig) -> dict[str, str]:
    """symbol -> growth|defensive."""
    out: dict[str, str] = {}
    for t in cfg.tickers:
        sleeve = (t.sleeve or "").strip().lower()
        if sleeve not in {"growth", "defensive"}:
            raise ValueError(f"{t.symbol}: sleeve must be growth or defensive, got {t.sleeve!r}")
        out[t.symbol] = sleeve
    return out
