"""Assemble a full desk packet: session, book, signals, plan, eval/BT gates, regime.

This is the factual backbone for multi-agent desk runs. LLMs must not invent
numbers that contradict this packet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from neotrade.broker import (
    AlpacaPaperClient,
    build_trade_plan,
    default_risk_limits,
    get_session_status,
)
from neotrade.broker.alpaca import AlpacaAPIError
from neotrade.config import load_tickers_config
from neotrade.config.load import project_root
from neotrade.config.models import TickersConfig
from neotrade.data import load_universe_ohlcv, prices_for_plan
from neotrade.logging_config import get_logger
from neotrade.signals import SignalModel, score_universe
from neotrade.signals.regime import detect_regime
from neotrade.signals.score import SignalRow

log = get_logger("agents.desk_context")


@dataclass
class DeskPacket:
    """Structured facts for the desk graph."""

    ts: str
    session_line: str
    allow_execute: bool
    universe: str
    regime_line: str
    account_lines: list[str] = field(default_factory=list)
    signal_lines: list[str] = field(default_factory=list)
    plan_lines: list[str] = field(default_factory=list)
    eval_lines: list[str] = field(default_factory=list)
    backtest_lines: list[str] = field(default_factory=list)
    promote_ok: bool | None = None
    notes: list[str] = field(default_factory=list)
    top_signals: list[SignalRow] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        lines = [
            f"Desk packet @ {self.ts}",
            "HARD RULES: paper only; never invent prices/equity; open_orders ≠ positions;",
            "LightGBM trains only via neotrade train on OHLCV — never on agent prose;",
            "Execute only if allow_execute=true AND human uses paper-execute --confirm.",
            "",
            f"SESSION: {self.session_line}",
            f"allow_execute={self.allow_execute}",
            f"REGIME: {self.regime_line}",
            f"UNIVERSE: {self.universe}",
            "",
            "ACCOUNT:",
        ]
        lines.extend(f"  {x}" for x in (self.account_lines or ["(unavailable)"]))
        lines += ["", "SIGNALS (top by proba):"]
        lines.extend(f"  {x}" for x in (self.signal_lines or ["(none)"]))
        lines += ["", "PAPER PLAN:"]
        lines.extend(f"  {x}" for x in (self.plan_lines or ["(none)"]))
        lines += ["", "EVAL (classification rigor):"]
        lines.extend(
            f"  {x}"
            for x in (self.eval_lines or ["(no eval_latest.json — run neotrade eval)"])
        )
        lines += ["", "BACKTEST (portfolio promote gate):"]
        lines.extend(
            f"  {x}"
            for x in (
                self.backtest_lines
                or ["(no backtest_latest.json — run neotrade backtest)"]
            )
        )
        lines.append(f"promote_ok={self.promote_ok}")
        if self.notes:
            lines.append("NOTES:")
            lines.extend(f"  {n}" for n in self.notes)
        return "\n".join(lines)


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("json load failed %s: %s", path, exc)
        return None


def _eval_lines(data: dict) -> list[str]:
    return [
        f"mean_accuracy={data.get('mean_accuracy')}",
        f"edge_vs_always_long={data.get('edge_vs_always_long')}",
        f"edge_vs_momentum={data.get('edge_vs_momentum')}",
        f"mean_brier={data.get('mean_brier')}",
        f"n_folds={data.get('n_folds')}",
    ]


def _backtest_lines(data: dict) -> tuple[list[str], bool | None]:
    gate = data.get("gate") or {}
    stable = data.get("stable_gate") or {}
    sig = data.get("signal") or {}
    eq = data.get("equal_weight") or {}
    mom = data.get("momentum") or {}
    full_pass = bool(gate.get("pass"))
    stable_pass = stable.get("pass") if stable else None
    if stable_pass is None:
        promote = full_pass
    else:
        promote = full_pass and bool(stable_pass)
    lines = [
        f"full_gate_pass={full_pass}",
        f"stable_gate_pass={stable_pass}",
        f"promote={promote}",
        f"signal_ret={sig.get('total_return')} maxDD={sig.get('max_drawdown')} sharpe={sig.get('sharpe')}",
        f"eq_ret={eq.get('total_return')} mom_ret={mom.get('total_return')}",
    ]
    for r in (gate.get("reasons") or [])[:6]:
        lines.append(f"gate_reason: {r}")
    if stable:
        for r in (stable.get("reasons") or [])[:4]:
            lines.append(f"stable_reason: {r}")
    wins = data.get("windows") or []
    if wins:
        n_ok = sum(1 for w in wins if w.get("gate_pass"))
        lines.append(f"windows_pass={n_ok}/{len(wins)}")
    return lines, promote


def gather_desk_packet(
    *,
    model_path: Path,
    config_path: str | Path | None = None,
    cfg: TickersConfig | None = None,
    include_account: bool = True,
) -> DeskPacket:
    """Build desk packet from live tools + latest eval/BT artifacts."""
    root = project_root()
    cfg = cfg or load_tickers_config(config_path)
    risk = default_risk_limits(cfg)
    session = get_session_status()
    packet = DeskPacket(
        ts=datetime.now(UTC).isoformat(),
        session_line=session.summary_line(),
        allow_execute=session.allow_execute,
        universe=cfg.universe.name,
        regime_line="(pending)",
    )

    if not model_path.is_file():
        packet.notes.append(f"model missing: {model_path} (run neotrade train)")
        packet.regime_line = "unknown"
        return packet

    model = SignalModel.load(model_path)
    bars = load_universe_ohlcv(cfg, force_refresh=False, root=root)
    if bars.errors:
        packet.notes.extend(f"bars: {e}" for e in bars.errors[:5])

    try:
        reg = detect_regime(
            bars.frames,
            base_top_n=risk.top_n,
            base_min_cash=risk.min_cash_pct,
            base_max_pos=risk.max_position_pct,
        )
        packet.regime_line = reg.summary_line()
    except Exception as exc:  # noqa: BLE001
        packet.regime_line = f"regime error: {exc}"
        packet.notes.append(str(exc))

    scored = score_universe(
        model,
        bars.frames,
        buy_threshold=risk.buy_threshold,
        sell_threshold=risk.sell_threshold,
    )
    packet.top_signals = list(scored.rows[:15])
    for s in packet.top_signals:
        packet.signal_lines.append(f"{s.symbol} proba={s.proba:.3f} side={s.side} as_of={s.as_of}")
    if scored.errors:
        packet.notes.extend(scored.errors[:5])

    prices = prices_for_plan(cfg, frames=bars.frames)

    if include_account:
        try:
            client = AlpacaPaperClient()
            acct = client.get_account()
            positions = client.list_positions()
            open_orders = client.list_orders(status="open", limit=20)
            packet.account_lines = [
                f"equity=${acct.equity:,.2f} cash=${acct.cash:,.2f} bp=${acct.buying_power:,.2f}",
                f"status={acct.status} blocked={acct.trading_blocked or acct.account_blocked}",
                f"filled_positions={len(positions)} open_unfilled_orders={len(open_orders)}",
            ]
            for p in positions[:15]:
                packet.account_lines.append(
                    f"FILL {p.symbol} qty={p.qty:g} mv=${p.market_value:,.2f} "
                    f"px={p.current_price:.2f} upl=${p.unrealized_pl:,.2f}"
                )
            for o in open_orders[:8]:
                packet.account_lines.append(
                    f"WORKING {o.get('side')} {o.get('symbol')} qty={o.get('qty')} "
                    f"status={o.get('status')}"
                )
            plan = build_trade_plan(
                signals=scored.rows,
                account=acct,
                positions=positions,
                cfg=cfg,
                risk=risk,
                prices=prices,
            )
            packet.plan_lines = plan.summary_lines()
        except (RuntimeError, AlpacaAPIError, OSError) as exc:
            packet.notes.append(f"account/plan unavailable: {exc}")
            log.warning("desk account failed: %s", exc)

    learning = root / "data" / "learning"
    ev = _load_json(learning / "eval_latest.json")
    if ev:
        packet.eval_lines = _eval_lines(ev)
    bt = _load_json(learning / "backtest_latest.json")
    if bt:
        packet.backtest_lines, packet.promote_ok = _backtest_lines(bt)

    # Experiment discipline status (agents must complete opens)
    try:
        from neotrade.learning.experiments import discipline_status, reconcile_open_experiments

        reconcile_open_experiments()
        st = discipline_status()
        if st["open_count"] == 0:
            packet.notes.append("experiments: none open (disciplined)")
        else:
            packet.notes.append(
                f"experiments: OPEN {st['open_ids'][0]} — {st['open_hypotheses'][0]} "
                "(complete after train/eval/backtest)"
            )
        for rc in st.get("recent_complete") or []:
            packet.notes.append(
                f"experiments: last {rc.get('id')} → {rc.get('outcome')} ({rc.get('hyp')})"
            )
    except Exception as exc:  # noqa: BLE001
        packet.notes.append(f"experiments: status error {exc}")

    return packet
