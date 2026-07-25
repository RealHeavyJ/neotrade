"""Gather signals, optional account/plan snapshot for agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from neotrade.broker import AlpacaPaperClient, build_trade_plan, default_risk_limits
from neotrade.broker.alpaca import AlpacaAPIError
from neotrade.config import load_tickers_config
from neotrade.config.load import project_root
from neotrade.config.models import TickersConfig
from neotrade.data import load_universe_ohlcv, prices_for_plan
from neotrade.logging_config import get_logger
from neotrade.signals import SignalModel, score_universe
from neotrade.signals.score import SignalRow

log = get_logger("agents.context")


@dataclass
class MarketContext:
    universe: str
    signals: list[SignalRow]
    plan_lines: list[str] = field(default_factory=list)
    account_lines: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        lines = [
            f"Universe: {self.universe}",
            (
                "Definitions: filled positions = owned shares; open_orders = unfilled working orders "
                "(not inventory). Cash usually unchanged until fills."
            ),
            "Signals (symbol proba side as_of):",
        ]
        for s in self.signals[:25]:
            lines.append(f"  {s.symbol} {s.proba:.3f} {s.side} {s.as_of}")
        if self.account_lines:
            lines.append("Account:")
            lines.extend(f"  {x}" for x in self.account_lines)
        if self.plan_lines:
            lines.append("Paper plan:")
            lines.extend(f"  {x}" for x in self.plan_lines)
        if self.notes:
            lines.append("Notes:")
            lines.extend(f"  {x}" for x in self.notes)
        return "\n".join(lines)


def gather_market_context(
    *,
    config_path: str | Path | None = None,
    model_path: Path,
    include_account: bool = True,
    cfg: TickersConfig | None = None,
) -> MarketContext:
    cfg = cfg or load_tickers_config(config_path)
    root = project_root()
    risk = default_risk_limits(cfg)
    if not model_path.is_file():
        raise FileNotFoundError(f"model not found: {model_path} (run: neotrade train)")
    model = SignalModel.load(model_path)
    bars = load_universe_ohlcv(cfg, force_refresh=False, root=root)
    scored = score_universe(
        model,
        bars.frames,
        buy_threshold=risk.buy_threshold,
        sell_threshold=risk.sell_threshold,
    )
    ctx = MarketContext(universe=cfg.universe.name, signals=list(scored.rows))

    if not include_account:
        return ctx

    try:
        client = AlpacaPaperClient()
        acct = client.get_account()
        positions = client.list_positions()
        open_orders = client.list_orders(status="open", limit=20)
        filled_n = len(positions)
        open_n = len(open_orders)
        ctx.account_lines = [
            f"equity=${acct.equity:,.2f} cash=${acct.cash:,.2f}",
            f"filled_positions={filled_n} open_unfilled_orders={open_n}",
            (
                "portfolio_state=cash_with_working_orders"
                if filled_n == 0 and open_n > 0
                else (
                    "portfolio_state=deployed"
                    if filled_n > 0
                    else "portfolio_state=flat_cash"
                )
            ),
        ]
        if filled_n == 0 and open_n > 0:
            ctx.notes.append(
                "Open orders are not fills. Do not treat as owned positions or full deployment."
            )
        if positions:
            ctx.account_lines.append("Filled positions:")
            for p in positions[:15]:
                ctx.account_lines.append(
                    f"  FILL {p.symbol} qty={p.qty:g} mv=${p.market_value:,.2f} upl=${p.unrealized_pl:,.2f}"
                )
        else:
            ctx.account_lines.append("Filled positions: none")
        if open_orders:
            ctx.account_lines.append("Open unfilled orders:")
            for o in open_orders[:10]:
                ctx.account_lines.append(
                    f"  WORKING {o.get('side')} {o.get('symbol')} qty={o.get('qty')} "
                    f"status={o.get('status')} filled_qty={o.get('filled_qty', 0)}"
                )
        else:
            ctx.account_lines.append("Open unfilled orders: none")
        plan = build_trade_plan(
            signals=ctx.signals,
            account=acct,
            positions=positions,
            cfg=cfg,
            risk=risk,
            prices=prices_for_plan(cfg, frames=bars.frames),
        )
        ctx.plan_lines = plan.summary_lines()
    except (RuntimeError, AlpacaAPIError, OSError, FileNotFoundError) as exc:
        log.warning("account/plan unavailable: %s", exc)
        ctx.notes.append(f"account/plan unavailable: {exc}")
    return ctx
