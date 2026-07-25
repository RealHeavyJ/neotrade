"""Broker CLI: account, session, paper plan/execute, fills."""
from __future__ import annotations

import argparse
import sys

from neotrade import defaults as D
from neotrade.broker import (
    AlpacaPaperClient,
    assert_execute_allowed,
    build_trade_plan,
    get_session_status,
)
from neotrade.broker.alpaca import AlpacaAPIError
from neotrade.broker.fills import (
    append_fill,
    calibrate_fills,
    effective_slip_bps,
    load_fills,
    load_saved_calibration,
    make_observation,
    parse_filled_order,
    save_calibration,
)
from neotrade.cli.common import load_signals_for_paper, log
from neotrade.config import load_tickers_config
from neotrade.data import fetch_universe_quotes


def cmd_account(_: argparse.Namespace) -> int:
    """Show paper account equity, filled positions, and open orders."""
    session = get_session_status()
    print(session.summary_line())
    try:
        client = AlpacaPaperClient()
        acct = client.get_account()
    except (RuntimeError, AlpacaAPIError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"status={acct.status} paper endpoint ok")
    print(f"equity=${acct.equity:,.2f} cash=${acct.cash:,.2f} bp=${acct.buying_power:,.2f}")
    print(f"blocked={acct.trading_blocked or acct.account_blocked} pdt={acct.pattern_day_trader}")
    positions = client.list_positions()
    print(f"positions={len(positions)}")
    for p in positions:
        print(
            f"  {p.symbol:<6} qty={p.qty:g} mv=${p.market_value:,.2f} "
            f"px={p.current_price:.2f} upl=${p.unrealized_pl:,.2f}"
        )
    open_orders = client.list_open_orders(limit=50)
    print(f"open_orders={len(open_orders)}")
    for o in open_orders:
        print(
            f"  {o.side:<4} {o.symbol:<6} "
            f"rem={o.remaining_qty:g} filled={o.filled_qty:g} "
            f"status={o.status}"
        )
    if open_orders and not positions:
        print("note: day market orders often stay accepted until the next US regular session")
    if open_orders:
        print("note: paper-plan reserves open-buy cash and avoids double-buy/sell")
    if not session.allow_execute:
        print("note: paper execute blocked until US RTH (09:30–16:00 ET); no after-hours")
    cal = calibrate_fills()
    slip_eff = effective_slip_bps(fallback=D.BT_SLIP_BPS)
    print(
        f"fill_calib n={cal.n}/{cal.min_n} "
        f"bt_slip_bps={slip_eff:.1f}"
        + (
            f" median={cal.median_slip_bps:.1f}"
            if cal.median_slip_bps is not None
            else ""
        )
    )
    return 0


def cmd_fills(args: argparse.Namespace) -> int:
    """Report paper fill slip vs mid; optional apply to BT default."""
    # 1) existing journal
    obs = load_fills()
    # 2) optional backfill from closed orders + live mids
    if not args.no_broker:
        try:
            client = AlpacaPaperClient()
            closed = client.list_orders(status="closed", limit=int(args.limit))
        except (RuntimeError, AlpacaAPIError, OSError) as exc:
            print(f"warn: broker orders unavailable: {exc}", file=sys.stderr)
            closed = []
        known = {o.order_id for o in obs if o.order_id}
        # mids from quotes for symbols we need
        need_syms: list[str] = []
        parsed_rows: list[dict] = []
        for row in closed:
            p = parse_filled_order(row)
            if not p or p["order_id"] in known:
                continue
            parsed_rows.append(p)
            if p["symbol"] not in need_syms:
                need_syms.append(p["symbol"])
        mids: dict[str, float] = {}
        if parsed_rows and not args.no_quotes:
            try:
                cfg = load_tickers_config(args.config)
                snap = fetch_universe_quotes(cfg, prefer_alpaca=True, fallback_cache=True)
                for q in snap.rows:
                    mid = q.mid or q.display_price()
                    if mid and mid > 0:
                        mids[str(q.symbol).upper()] = float(mid)
            except (RuntimeError, OSError, ValueError) as exc:
                print(f"warn: quotes for mid: {exc}", file=sys.stderr)
        added = 0
        for p in parsed_rows:
            mid = mids.get(p["symbol"])
            if mid is None or mid <= 0:
                continue
            # current quote mid is weak for old fills — only log if --backfill
            if not args.backfill:
                continue
            try:
                o = make_observation(
                    order_id=p["order_id"],
                    symbol=p["symbol"],
                    side=p["side"],
                    fill_px=p["fill_px"],
                    mid_px=mid,
                    qty=p["qty"],
                    source="closed_order_backfill",
                    status=p["status"],
                    ts=p.get("filled_at") or None,
                )
                append_fill(o)
                obs.append(o)
                known.add(o.order_id)
                added += 1
            except (ValueError, OSError):
                continue
        if args.backfill:
            print(f"backfill added={added} (quote mid ≈ now — prefer execute-time logs)")

    cal = calibrate_fills(obs, min_n=int(args.min_n))
    for line in cal.summary_lines():
        print(line)
    # show sample
    show = obs[- int(args.show) :] if obs else []
    if show:
        print(f"last {len(show)} fills:")
        for o in show:
            print(
                f"  {o.ts[:19]} {o.side:<4} {o.symbol:<6} "
                f"fill={o.fill_px:.4f} mid={o.mid_px:.4f} "
                f"slip={o.slip_bps:+.1f}bps src={o.source}"
            )
    slip_now = effective_slip_bps(fallback=D.BT_SLIP_BPS)
    print(f"effective BT slip_bps now={slip_now:.1f} (package default={D.BT_SLIP_BPS:.1f})")
    if args.apply:
        if cal.recommended_slip_bps is None:
            print(
                f"refuse --apply: need n≥{cal.min_n} fills with recommendation",
                file=sys.stderr,
            )
            return 2
        path = save_calibration(cal)
        print(f"saved calibration: {path}")
        print(f"BT default slip_bps → {cal.recommended_slip_bps:.1f}")
    elif cal.recommended_slip_bps is not None:
        print("tip: neotrade fills --apply  # write slip_calibration.json for BT default")
    saved = load_saved_calibration()
    if saved and saved.get("recommended_slip_bps") is not None:
        print(
            f"saved calib: n={saved.get('n')} "
            f"recommended={saved.get('recommended_slip_bps')} "
            f"ts={str(saved.get('ts') or '')[:19]}"
        )
    return 0


def cmd_paper_plan(args: argparse.Namespace) -> int:
    """Dry-run risk-aware order intents (no broker submit)."""
    session = get_session_status()
    print(session.summary_line())
    if not session.allow_execute:
        print(
            "warn: outside RTH — plan is dry-run only; execute will be blocked "
            "(neotrade does not trade pre/after-hours)",
            file=sys.stderr,
        )
    try:
        cfg, risk, signals, prices = load_signals_for_paper(args)
        client = AlpacaPaperClient()
        acct = client.get_account()
        positions = client.list_positions()
        open_orders = client.list_open_orders()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (RuntimeError, AlpacaAPIError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    plan = build_trade_plan(
        signals=signals,
        account=acct,
        positions=positions,
        cfg=cfg,
        risk=risk,
        prices=prices,
        open_orders=open_orders,
    )
    for line in plan.summary_lines():
        print(line)
    return 0


def cmd_paper_execute(args: argparse.Namespace) -> int:
    """Submit paper market orders; requires ``--confirm`` and US RTH."""
    if not args.confirm:
        log.warning("execute refused: missing --confirm")
        print("refusing execute without --confirm (dry-run: neotrade paper-plan)", file=sys.stderr)
        return 2
    try:
        session = assert_execute_allowed()
    except RuntimeError as exc:
        log.warning("execute blocked by session: %s", exc)
        print(str(exc), file=sys.stderr)
        return 3
    print(session.summary_line())
    try:
        cfg, risk, signals, prices = load_signals_for_paper(args)
        client = AlpacaPaperClient()
        acct = client.get_account()
        if acct.trading_blocked or acct.account_blocked:
            log.error("account trading blocked")
            print("account trading blocked", file=sys.stderr)
            return 1
        positions = client.list_positions()
        open_orders = client.list_open_orders()
    except FileNotFoundError as exc:
        log.error("%s", exc)
        print(str(exc), file=sys.stderr)
        return 1
    except (RuntimeError, AlpacaAPIError, OSError) as exc:
        log.error("execute prep failed: %s", exc)
        print(str(exc), file=sys.stderr)
        return 1
    plan = build_trade_plan(
        signals=signals,
        account=acct,
        positions=positions,
        cfg=cfg,
        risk=risk,
        prices=prices,
        open_orders=open_orders,
    )
    if not plan.intents:
        print("no intents to execute")
        for note in plan.notes:
            print(f"note: {note}")
        log.info("execute: no intents")
        return 0
    errors = 0
    for intent in plan.intents:
        mid = float(prices.get(intent.symbol.upper()) or 0) if prices else 0.0
        try:
            result = client.submit_market_order(
                symbol=intent.symbol,
                side=intent.side,
                qty=intent.qty,
                notional=intent.notional,
            )
            print(
                f"submitted {result.side} {result.symbol} qty={result.qty} "
                f"id={result.id} status={result.status}"
            )
            log.info(
                "order submitted symbol=%s side=%s id=%s status=%s",
                result.symbol,
                result.side,
                result.id,
                result.status,
            )
            # Log fill vs pre-submit mid when broker reports filled_avg_price
            maybe_log_fill_observation(client, result.id, mid_px=mid, source="execute")
        except AlpacaAPIError as exc:
            errors += 1
            log.error("order fail %s: %s", intent.describe(), exc)
            print(f"ORDER FAIL {intent.describe()}: {exc}", file=sys.stderr)
    return 1 if errors else 0


def maybe_log_fill_observation(
    client: AlpacaPaperClient,
    order_id: str,
    *,
    mid_px: float,
    source: str = "execute",
) -> None:
    """If order has a fill price and mid, append fill observation (best-effort)."""
    if not order_id or mid_px <= 0:
        return
    try:
        raw = client.get_order(order_id)
    except (AlpacaAPIError, RuntimeError, OSError) as exc:
        log.warning("fill observe skip get_order: %s", exc)
        return
    parsed = parse_filled_order(raw)
    if not parsed:
        # still open — store nothing; fills-report can backfill later
        return
    try:
        obs = make_observation(
            order_id=parsed["order_id"],
            symbol=parsed["symbol"],
            side=parsed["side"],
            fill_px=parsed["fill_px"],
            mid_px=mid_px,
            qty=parsed["qty"],
            source=source,
            status=parsed["status"],
        )
        append_fill(obs)
        print(
            f"  fill-log {obs.side} {obs.symbol} fill={obs.fill_px:.4f} "
            f"mid={obs.mid_px:.4f} slip={obs.slip_bps:+.1f}bps"
        )
    except (ValueError, TypeError, OSError) as exc:
        log.warning("fill observe skip: %s", exc)


def cmd_session(_: argparse.Namespace) -> int:
    """Print US equity session phase and whether paper execute is allowed."""
    st = get_session_status()
    print(st.summary_line())
    print(f"phase={st.phase.value} is_rth={st.is_rth} trading_day={st.is_trading_day}")
    print(f"allow_execute={st.allow_execute}")
    if st.next_rth_open_et is not None:
        print(f"next_rth_open={st.next_rth_open_et.isoformat()}")
    return 0 if st.allow_execute else 1


