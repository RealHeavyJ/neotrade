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

from neotrade.broker.alpaca import AccountSnapshot, OpenOrder, Position
from neotrade.broker.risk import RiskLimits, sleeve_map
from neotrade.config.models import TickersConfig
from neotrade.signals.score import SignalRow


@dataclass(frozen=True)
class OrderBookState:
    """Derived exposure from fills + working orders (partial-fill aware)."""

    reserved_buy_cash: float
    pending_buy_qty: dict[str, float]
    pending_buy_notional: dict[str, float]
    pending_sell_qty: dict[str, float]
    notes: list[str]


def summarize_open_orders(
    open_orders: list[OpenOrder],
    *,
    prices: dict[str, float],
) -> OrderBookState:
    """Aggregate working orders into reserved cash and pending qty by symbol."""
    reserved = 0.0
    buy_qty: dict[str, float] = {}
    buy_notional: dict[str, float] = {}
    sell_qty: dict[str, float] = {}
    notes: list[str] = []
    for oo in open_orders:
        sym = oo.symbol.upper()
        px = prices.get(sym)
        if oo.side == "buy":
            res = oo.reserved_buy_notional(px)
            reserved += res
            if oo.remaining_qty > 1e-12:
                buy_qty[sym] = buy_qty.get(sym, 0.0) + oo.remaining_qty
            if res > 0:
                buy_notional[sym] = buy_notional.get(sym, 0.0) + res
            notes.append(
                f"open {oo.side} {sym} rem_qty={oo.remaining_qty:g} "
                f"filled={oo.filled_qty:g} status={oo.status} reserved=${res:,.0f}"
            )
        elif oo.side == "sell":
            pq = oo.pending_sell_qty()
            if pq > 1e-12:
                sell_qty[sym] = sell_qty.get(sym, 0.0) + pq
            notes.append(
                f"open sell {sym} rem_qty={pq:g} filled={oo.filled_qty:g} status={oo.status}"
            )
    return OrderBookState(
        reserved_buy_cash=reserved,
        pending_buy_qty=buy_qty,
        pending_buy_notional=buy_notional,
        pending_sell_qty=sell_qty,
        notes=notes,
    )


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
    reserved_buy_cash: float = 0.0

    def summary_lines(self) -> list[str]:
        """Multi-line summary for CLI and agent context."""
        lines = [
            f"equity=${self.equity:,.2f} cash=${self.cash:,.2f} "
            f"reserved_open_buys=${self.reserved_buy_cash:,.2f}",
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
    open_orders: list[OpenOrder],
) -> TradePlan:
    """Top-N by proba, equal-weight targets, exit names outside the book."""
    risk.validate()
    sleeves = sleeve_map(cfg)
    universe = set(sleeves)
    pos = _pos_map(positions)
    book = summarize_open_orders(open_orders, prices=prices)
    equity = max(account.equity, 0.0)
    cash = max(account.cash, 0.0)
    plan = TradePlan(equity=equity, cash=cash, reserved_buy_cash=book.reserved_buy_cash)
    plan.notes.extend(book.notes)

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
    # Working buys count toward sleeve exposure (prevents oversize)
    for sym, ntl in book.pending_buy_notional.items():
        if sleeves.get(sym) == "growth":
            growth_mv += ntl
        elif sleeves.get(sym) == "defensive":
            defensive_mv += ntl
    plan.growth_mv = growth_mv
    plan.defensive_mv = defensive_mv

    ranked = [s for s in signals if s.symbol.upper() in universe]
    ranked.sort(key=lambda s: s.proba, reverse=True)
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

    # Exit names not in target book (or hard sell) — only remaining after pending sells
    for symbol, p in pos.items():
        if symbol not in universe or p.qty <= 0:
            continue
        pending_sell = book.pending_sell_qty.get(symbol, 0.0)
        sellable = max(0.0, abs(p.qty) - pending_sell)
        if sellable <= 1e-12:
            if pending_sell > 0:
                plan.notes.append(f"skip sell {symbol}: open sell covers position")
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
            if pending_sell > 0:
                reason += f" (after open sell {pending_sell:g})"
            plan.intents.append(
                OrderIntent(
                    symbol=symbol,
                    side="sell",
                    qty=sellable,
                    notional=None,
                    reason=reason,
                    sleeve=sleeves.get(symbol, "growth"),
                )
            )
            mv = sellable * (prices.get(symbol) or p.current_price or 0.0)
            if sleeves.get(symbol) == "growth":
                growth_mv -= mv
            else:
                defensive_mv -= mv

    n_tgt = max(len(targets), 1)
    target_w = min(risk.max_position_pct, (1.0 - risk.min_cash_pct) / n_tgt)
    target_notional = equity * target_w
    band = risk.rebalance_band_pct

    # Free cash minus buffer minus reserved working buys
    spendable = max(0.0, cash - equity * risk.min_cash_pct - book.reserved_buy_cash)
    for intent in plan.intents:
        if intent.side == "sell" and intent.qty:
            px = prices.get(intent.symbol) or 0.0
            spendable += intent.qty * px

    def exposure_mv(sym: str) -> float:
        """Filled MV + working buy notional (partial-fill aware)."""
        p = pos.get(sym)
        filled = max(p.market_value, 0.0) if p else 0.0
        pending = book.pending_buy_notional.get(sym, 0.0)
        if pending <= 0 and book.pending_buy_qty.get(sym, 0) > 0:
            px = prices.get(sym) or 0.0
            pending = book.pending_buy_qty[sym] * px
        return filled + pending

    buy_order = sorted(targets, key=lambda s: (exposure_mv(s.symbol.upper()), -s.proba))
    for sig in buy_order:
        if spendable < risk.min_notional:
            break
        symbol = sig.symbol.upper()
        current = exposure_mv(symbol)
        if any(i.symbol == symbol and i.side == "sell" for i in plan.intents):
            current = 0.0
        desired = target_notional
        if current >= desired * (1.0 - band) and current > 0:
            if book.pending_buy_qty.get(symbol, 0) > 0 or book.pending_buy_notional.get(symbol, 0) > 0:
                plan.notes.append(f"skip buy {symbol}: open buy + fill within band")
            continue
        need = desired - current
        if need < risk.min_notional:
            continue
        notional = min(need, spendable, equity * risk.max_position_pct)
        if notional < risk.min_notional:
            continue
        qty, order_notional, eff = _size_buy(symbol=symbol, notional=notional, prices=prices)
        if eff < risk.min_notional and order_notional is None:
            continue
        reason = f"ranked top{risk.top_n} proba={sig.proba:.3f}"
        if book.pending_buy_qty.get(symbol, 0) > 0:
            reason += " (add after partial open buy)"
        plan.intents.append(
            OrderIntent(
                symbol=symbol,
                side="buy",
                qty=qty,
                notional=order_notional,
                reason=reason,
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
    open_orders: list[OpenOrder],
) -> TradePlan:
    """Legacy side-based policy (buy new buys, sell sells)."""
    risk.validate()
    sleeves = sleeve_map(cfg)
    universe = set(sleeves)
    pos = _pos_map(positions)
    book = summarize_open_orders(open_orders, prices=prices)

    equity = max(account.equity, 0.0)
    cash = max(account.cash, 0.0)
    plan = TradePlan(equity=equity, cash=cash, reserved_buy_cash=book.reserved_buy_cash)
    plan.notes.append("mode=sides")
    plan.notes.extend(book.notes)

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
    for sym, ntl in book.pending_buy_notional.items():
        if sleeves.get(sym) == "growth":
            growth_mv += ntl
        elif sleeves.get(sym) == "defensive":
            defensive_mv += ntl
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
            pending_sell = book.pending_sell_qty.get(symbol, 0.0)
            sellable = max(0.0, abs(p.qty) - pending_sell)
            if sellable <= 1e-12:
                plan.notes.append(f"skip sell {symbol}: open sell covers position")
                continue
            plan.intents.append(
                OrderIntent(
                    symbol=symbol,
                    side="sell",
                    qty=sellable,
                    notional=None,
                    reason=f"signal sell proba={sig.proba:.3f}",
                    sleeve=sleeves[symbol],
                )
            )
            mv = sellable * (prices.get(symbol) or p.current_price or 0.0)
            if sleeves[symbol] == "growth":
                growth_mv -= mv
            else:
                defensive_mv -= mv

    spendable = max(0.0, cash - equity * risk.min_cash_pct - book.reserved_buy_cash)
    if spendable < risk.min_notional:
        plan.notes.append("insufficient cash after min_cash_pct + open buy reserves")
        plan.growth_mv = max(growth_mv, 0.0)
        plan.defensive_mv = max(defensive_mv, 0.0)
        return plan

    growth_target = equity * risk.growth_target_pct
    defensive_target = equity * risk.defensive_target_pct
    growth_room = max(0.0, growth_target - max(growth_mv, 0.0))
    defensive_room = max(0.0, defensive_target - max(defensive_mv, 0.0))

    buys = [s for s in signals if s.side == "buy" and s.symbol.upper() in universe]
    buys.sort(key=lambda s: s.proba, reverse=True)
    # Skip names with filled position OR working buy (avoid double-buy)
    held_or_pending = set(pos.keys()) | set(book.pending_buy_qty) | set(book.pending_buy_notional)
    buys = [s for s in buys if s.symbol.upper() not in held_or_pending]

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
    open_orders: list[OpenOrder] | None = None,
) -> TradePlan:
    """Construct a paper trade plan using ``risk.plan_mode``.

    Args:
        open_orders: Working / partially filled orders. Reserved buy cash is
            subtracted from spendable; pending sells reduce sellable qty;
            pending buys count toward name exposure (no double-buy).
    """
    prices = dict(prices or {})
    oos = list(open_orders or [])
    mode = (risk.plan_mode or "ranked").strip().lower()
    if mode == "sides":
        return _plan_sides(
            signals=signals,
            account=account,
            positions=positions,
            cfg=cfg,
            risk=risk,
            prices=prices,
            open_orders=oos,
        )
    return _plan_ranked(
        signals=signals,
        account=account,
        positions=positions,
        cfg=cfg,
        risk=risk,
        prices=prices,
        open_orders=oos,
    )
