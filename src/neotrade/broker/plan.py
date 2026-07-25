"""Build paper trade intents from signals + risk limits + current positions.

Execution is intentionally separate (:meth:`AlpacaPaperClient.submit_market_order`)
so dry-run planning never places orders.

Modes:
  * ``ranked`` (default) — hold equal-weight **top-N by model proba**; exit names
    that fall out of the book. Aligns portfolio construction with relative scores
    and cuts churn vs daily buy/sell side flips.
  * ``sides`` — legacy: sell on sell side, buy new buy-side names only (no add-on).
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


def _size_buy(
    *,
    symbol: str,
    notional: float,
    prices: dict[str, float],
) -> tuple[float | None, float | None, float]:
    """Return qty, order_notional, effective_notional for a buy."""
    px = prices.get(symbol)
    qty: float | None = None
    order_notional: float | None = round(notional, 2)
    eff = notional
    if px and px > 0:
        shares = int(notional // px)
        if shares >= 1:
            qty = float(shares)
            order_notional = None
            eff = shares * px
    return qty, order_notional, eff


def _plan_ranked(
    *,
    signals: list[SignalRow],
    account: AccountSnapshot,
    positions: list[Position],
    cfg: TickersConfig,
    risk: RiskLimits,
    prices: dict[str, float],
) -> TradePlan:
    """Top-N by proba, equal-weight targets, exit names outside the book."""
    risk.validate()
    sleeves = sleeve_map(cfg)
    universe = set(sleeves)
    pos = _pos_map(positions)
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

    ranked = [s for s in signals if s.symbol.upper() in universe]
    ranked.sort(key=lambda s: s.proba, reverse=True)
    # Eligible: above soft floor (use sell_threshold as "stay interesting")
    floor = min(risk.buy_threshold, risk.sell_threshold + 0.05)
    eligible = [s for s in ranked if s.proba >= floor]
    if not eligible:
        eligible = ranked[: risk.top_n]
    targets = eligible[: risk.top_n]
    target_set = {s.symbol.upper() for s in targets}
    plan.notes.append(
        f"mode=ranked top_n={risk.top_n} targets="
        + ",".join(f"{s.symbol}:{s.proba:.2f}" for s in targets)
    )

    # Exit names not in target book (or hard sell side below floor)
    for symbol, p in pos.items():
        if symbol not in universe or p.qty <= 0:
            continue
        sig = next((s for s in ranked if s.symbol.upper() == symbol), None)
        drop = symbol not in target_set
        hard_sell = sig is not None and sig.proba < risk.sell_threshold
        if drop or hard_sell:
            reason = (
                f"ranked exit proba={sig.proba:.3f}"
                if sig is not None
                else "ranked exit (no score)"
            )
            if hard_sell and not drop:
                reason = f"hard sell proba={sig.proba:.3f}"
            plan.intents.append(
                OrderIntent(
                    symbol=symbol,
                    side="sell",
                    qty=abs(p.qty),
                    notional=None,
                    reason=reason,
                    sleeve=sleeves.get(symbol, "growth"),
                )
            )
            mv = max(p.market_value, 0.0)
            if sleeves.get(symbol) == "growth":
                growth_mv -= mv
            else:
                defensive_mv -= mv

    # Target equal weight among survivors; deploy almost all equity
    n_tgt = max(len(targets), 1)
    target_w = min(risk.max_position_pct, (1.0 - risk.min_cash_pct) / n_tgt)
    target_notional = equity * target_w
    band = risk.rebalance_band_pct

    # After sells, approximate cash available (conservative: current cash only for buys;
    # backtest applies sells first so this matches fill order)
    spendable = max(0.0, cash - equity * risk.min_cash_pct)
    # Credit pending sell MV into spendable for planning denser books
    for intent in plan.intents:
        if intent.side == "sell" and intent.qty:
            px = prices.get(intent.symbol) or 0.0
            spendable += intent.qty * px

    # Sort buys: underweight targets first (highest proba first among them)
    def held_mv(sym: str) -> float:
        p = pos.get(sym)
        return max(p.market_value, 0.0) if p else 0.0

    buy_order = sorted(targets, key=lambda s: (held_mv(s.symbol.upper()), -s.proba))
    for sig in buy_order:
        if spendable < risk.min_notional:
            break
        symbol = sig.symbol.upper()
        current = held_mv(symbol)
        # if we're exiting this name in same plan, treat current as 0
        if any(i.symbol == symbol and i.side == "sell" for i in plan.intents):
            current = 0.0
        desired = target_notional
        if current >= desired * (1.0 - band) and current > 0:
            continue  # within band
        need = desired - current
        if need < risk.min_notional:
            continue
        notional = min(need, spendable, equity * risk.max_position_pct)
        if notional < risk.min_notional:
            continue
        qty, order_notional, eff = _size_buy(symbol=symbol, notional=notional, prices=prices)
        if eff < risk.min_notional and order_notional is None:
            continue
        plan.intents.append(
            OrderIntent(
                symbol=symbol,
                side="buy",
                qty=qty,
                notional=order_notional,
                reason=f"ranked top{risk.top_n} proba={sig.proba:.3f}",
                sleeve=sleeves.get(symbol, "growth"),
            )
        )
        spendable -= eff
        if sleeves.get(symbol) == "growth":
            growth_mv += eff
        else:
            defensive_mv += eff

    plan.growth_mv = max(growth_mv, 0.0)
    plan.defensive_mv = max(defensive_mv, 0.0)
    if not plan.intents:
        plan.notes.append("no actionable intents under ranked rules")
    return plan


def _plan_sides(
    *,
    signals: list[SignalRow],
    account: AccountSnapshot,
    positions: list[Position],
    cfg: TickersConfig,
    risk: RiskLimits,
    prices: dict[str, float],
) -> TradePlan:
    """Legacy side-based policy (buy new buys, sell sells)."""
    risk.validate()
    sleeves = sleeve_map(cfg)
    universe = set(sleeves)
    pos = _pos_map(positions)

    equity = max(account.equity, 0.0)
    cash = max(account.cash, 0.0)
    plan = TradePlan(equity=equity, cash=cash)
    plan.notes.append("mode=sides")

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

        qty, order_notional, eff = _size_buy(symbol=symbol, notional=notional, prices=prices)
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
        spendable -= eff
        if sleeve == "growth":
            growth_room -= eff
            growth_mv += eff
        else:
            defensive_room -= eff
            defensive_mv += eff
        new_count += 1

    plan.growth_mv = max(growth_mv, 0.0)
    plan.defensive_mv = max(defensive_mv, 0.0)
    if not plan.intents:
        plan.notes.append("no actionable intents under risk rules")
    return plan


def build_trade_plan(
    *,
    signals: list[SignalRow],
    account: AccountSnapshot,
    positions: list[Position],
    cfg: TickersConfig,
    risk: RiskLimits,
    prices: dict[str, float] | None = None,
) -> TradePlan:
    """Construct a paper trade plan using ``risk.plan_mode``.

    Note:
        Open / accepted orders are **not** modeled as positions. Pass only
        filled :class:`Position` objects from the broker.
    """
    prices = dict(prices or {})
    mode = (risk.plan_mode or "ranked").strip().lower()
    if mode == "sides":
        return _plan_sides(
            signals=signals,
            account=account,
            positions=positions,
            cfg=cfg,
            risk=risk,
            prices=prices,
        )
    return _plan_ranked(
        signals=signals,
        account=account,
        positions=positions,
        cfg=cfg,
        risk=risk,
        prices=prices,
    )
