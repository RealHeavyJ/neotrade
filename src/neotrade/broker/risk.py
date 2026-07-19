"""Risk limits and sleeve targets for paper trading.

Values typically come from the ``risk:`` block in ``config/tickers.yaml`` via
:func:`default_risk_limits`.
"""

from __future__ import annotations

from dataclasses import dataclass

from neotrade.config.models import TickersConfig


@dataclass(frozen=True)
class RiskLimits:
    """Runtime risk knobs for :func:`~neotrade.broker.plan.build_trade_plan`.

    Attributes:
        max_position_pct: Max single-name weight of equity (e.g. 0.08 = 8%).
        growth_target_pct: Target portfolio share for growth sleeve.
        defensive_target_pct: Target portfolio share for defensive sleeve.
            Must sum with growth to 1.0.
        max_new_positions: Cap on new buys per plan.
        min_notional: Minimum dollar order size.
        min_cash_pct: Cash buffer retained as fraction of equity.
        buy_threshold / sell_threshold: Signal side cutoffs (mirrors scoring).
        paper_only: Documentation flag; live trading is refused elsewhere.
    """

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
        """Raise ``ValueError`` if limits are internally inconsistent."""
        if self.max_position_pct <= 0 or self.max_position_pct > 0.5:
            raise ValueError("max_position_pct must be in (0, 0.5]")
        total = self.growth_target_pct + self.defensive_target_pct
        if abs(total - 1.0) > 1e-6:
            raise ValueError("growth_target_pct + defensive_target_pct must equal 1.0")


def default_risk_limits(cfg: TickersConfig | None = None) -> RiskLimits:
    """Build validated limits from config or package defaults.

    Args:
        cfg: Optional loaded tickers config. Uses ``cfg.risk`` when present.

    Returns:
        Validated :class:`RiskLimits`.
    """
    if cfg is None:
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
    """Map each configured symbol to ``growth`` or ``defensive``.

    Raises:
        ValueError: If any ticker has an invalid sleeve.
    """
    out: dict[str, str] = {}
    for t in cfg.tickers:
        sleeve = (t.sleeve or "").strip().lower()
        if sleeve not in {"growth", "defensive"}:
            raise ValueError(f"{t.symbol}: sleeve must be growth or defensive, got {t.sleeve!r}")
        out[t.symbol] = sleeve
    return out
