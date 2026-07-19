"""Build paper trade intents from signals + risk limits + current positions.

Execution is intentionally separate (:meth:`AlpacaPaperClient.submit_market_order`)
so dry-run planning never places orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from neotrade.broker.alpaca import AccountSnapshot, Position
from neotrade.broker.risk import RiskLimits, sleeve_map
from neotrade.config.models import TickersConfig
from neotrade.signals.score import SignalRow


@dataclass(frozen=True)
class OrderIntent:
    """Single proposed market order before broker submit.

    Attributes:
        symbol: Ticker.
        side: ``buy`` or ``sell``.
        qty: Share quantity when set (mutually exclusive with ``notional``).
        notional: Dollar amount when set (fractional share path).
        reason: Short human explanation (usually signal proba).
        sleeve: ``growth`` or ``defensive``.
    """

    symbol: str
    side: str
    qty: float | None
    notional: float | None
    reason: str
    sleeve: str

    def describe(self) -> str:
        """One-line CLI / log representation."""
        size = f"qty={self.qty}" if self.qty is not None else f"notional=${self.notional:.2f}"
        return f"{self.side.upper():4} {self.symbol:<6} {size}  [{self.sleeve}] {self.reason}"


@dataclass
class TradePlan:
    """Risk-filtered set of order intents plus sleeve diagnostics."""

    intents: list[OrderIntent] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    equity: float = 0.0
    cash: float = 0.0
    growth_mv: float = 0.0
    defensive_mv: float = 0.0

    def summary_lines(self) -> list[str]:
        """Multi-line summary for CLI and agent context."""
        lines = [
            f"equity=${self.equity:,.2f} cash=${self.cash:,.2f}",
            f"sleeves: growth=${self.growth_mv:,.2f} defensive=${self.defensive_mv:,.2f}",
            f"intents: {len(self.intents)}",
        ]
        for intent in self.intents:
            lines.append(f"  {intent.describe()}")
        for note in self.notes:
            lines.append(f"note: {note}")
        return lines


def _pos_map(positions: list[Position]) -> dict[str, Position]:
    return {p.symbol.upper(): p for p in positions}


def build_trade_plan(
    *,
    signals: list[SignalRow],
    account: AccountSnapshot,
    positions: list[Position],
    cfg: TickersConfig,
    risk: RiskLimits,
    prices: dict[str, float] | None = None,
) -> TradePlan:
    """Construct a v1 paper trade plan.

    Policy:
        * Full exit on ``sell`` signal for held names in the universe.
        * New buys ranked by proba; skip names already held (no add-on).
        * Size by min(max_position_pct equity, sleeve room, spendable cash).
        * Prefer whole shares when a price is available; else notional.

    Note:
        Open / accepted orders are **not** modeled as positions. Pass only
        filled :class:`Position` objects from the broker.

    Args:
        signals: Latest universe scores.
        account: Equity / cash snapshot.
        positions: Filled positions only.
        cfg: Ticker + sleeve config.
        risk: Validated risk limits.
        prices: Optional symbol → last price for share sizing.

    Returns:
        :class:`TradePlan` (may contain zero intents with explanatory notes).
    """
    risk.validate()
    sleeves = sleeve_map(cfg)
    universe = set(sleeves)
    pos = _pos_map(positions)
    prices = dict(prices or {})

    equity = max(account.equity, 0.0)
    cash = max(account.cash, 0.0)
    plan = TradePlan(equity=equity, cash=cash)

    growth_mv = 0.0
    defensive_mv = 0.0
    for symbol, p in pos.items():
        if symbol not in sleeves:
            plan.notes.append(f"position outside universe ignored for sleeves: {symbol}")
            continue
        if sleeves[symbol] == "growth":
            growth_mv += max(p.market_value, 0.0)
        else:
            defensive_mv += max(p.market_value, 0.0)
    plan.growth_mv = growth_mv
    plan.defensive_mv = defensive_mv

    sig_by_sym = {s.symbol.upper(): s for s in signals if s.symbol.upper() in universe}

    # --- exits ---
    for symbol, p in pos.items():
        if symbol not in universe:
            continue
        sig = sig_by_sym.get(symbol)
        if sig is None:
            continue
        if sig.side == "sell" and p.qty > 0:
            plan.intents.append(
                OrderIntent(
                    symbol=symbol,
                    side="sell",
                    qty=abs(p.qty),
                    notional=None,
                    reason=f"signal sell proba={sig.proba:.3f}",
                    sleeve=sleeves[symbol],
                )
            )
            if sleeves[symbol] == "growth":
                growth_mv -= max(p.market_value, 0.0)
            else:
                defensive_mv -= max(p.market_value, 0.0)

    # --- entries (cash after min cash buffer) ---
    spendable = max(0.0, cash - equity * risk.min_cash_pct)
    if spendable < risk.min_notional:
        plan.notes.append("insufficient cash after min_cash_pct buffer")
        plan.growth_mv = max(growth_mv, 0.0)
        plan.defensive_mv = max(defensive_mv, 0.0)
        return plan

    growth_target = equity * risk.growth_target_pct
    defensive_target = equity * risk.defensive_target_pct
    growth_room = max(0.0, growth_target - max(growth_mv, 0.0))
    defensive_room = max(0.0, defensive_target - max(defensive_mv, 0.0))

    buys = [s for s in signals if s.side == "buy" and s.symbol.upper() in universe]
    buys.sort(key=lambda s: s.proba, reverse=True)
    buys = [s for s in buys if s.symbol.upper() not in pos]

    max_name = equity * risk.max_position_pct
    new_count = 0

    for sig in buys:
        if new_count >= risk.max_new_positions:
            plan.notes.append("hit max_new_positions")
            break
        if spendable < risk.min_notional:
            break
        symbol = sig.symbol.upper()
        sleeve = sleeves[symbol]
        room = growth_room if sleeve == "growth" else defensive_room
        if room < risk.min_notional:
            continue

        notional = min(max_name, room, spendable)
        if notional < risk.min_notional:
            continue

        px = prices.get(symbol)
        qty: float | None = None
        order_notional: float | None = round(notional, 2)
        if px and px > 0:
            shares = int(notional // px)
            if shares >= 1:
                qty = float(shares)
                order_notional = None
                notional = shares * px

        plan.intents.append(
            OrderIntent(
                symbol=symbol,
                side="buy",
                qty=qty,
                notional=order_notional,
                reason=f"signal buy proba={sig.proba:.3f}",
                sleeve=sleeve,
            )
        )
        spendable -= notional
        if sleeve == "growth":
            growth_room -= notional
            growth_mv += notional
        else:
            defensive_room -= notional
            defensive_mv += notional
        new_count += 1

    plan.growth_mv = max(growth_mv, 0.0)
    plan.defensive_mv = max(defensive_mv, 0.0)
    if not plan.intents:
        plan.notes.append("no actionable intents under risk rules")
    return plan
