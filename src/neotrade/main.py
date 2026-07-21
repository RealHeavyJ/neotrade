"""CLI entry point for neotrade.

Exposes subcommands for data, signals, paper trading, local agents, bench, and
the Streamlit dashboard. Prefer importing library modules directly from
``neotrade.*`` when embedding; this module is the console script surface only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from neotrade import __version__
from neotrade.agents import run_advise
from neotrade.agents.llm import MockLLM, OllamaClient, OllamaConfig
from neotrade.broker import (
    AlpacaPaperClient,
    assert_execute_allowed,
    build_trade_plan,
    default_risk_limits,
    get_session_status,
)
from neotrade.broker.alpaca import AlpacaAPIError
from neotrade.config import default_config_path, load_tickers_config
from neotrade.config.load import project_root, resolve_cache_dir
from neotrade.data import fetch_universe_quotes, load_universe_ohlcv, prices_for_plan
from neotrade.learning.log import append_retrain_event
from neotrade.learning.policy import policy_blurb, record_advice_run
from neotrade.logging_config import get_logger, setup_logging
from neotrade.monitor import MonitorConfig, QuoteMonitor, default_monitor_config
from neotrade.monitor.stream import run_stream_cli
from neotrade.perf.bench import run_full_bench
from neotrade.signals import SignalModel, score_universe
from neotrade.signals.backtest import BacktestConfig, run_portfolio_backtest, save_backtest_report
from neotrade.signals.eval import run_signal_eval

DEFAULT_MODEL_PATH = Path("models/signal.txt")
log = get_logger("cli")


def _cmd_version(_: argparse.Namespace) -> int:
    """Print package version."""
    print(f"neotrade v{__version__}")
    return 0


def _cmd_tickers(args: argparse.Namespace) -> int:
    """List configured universe tickers and sleeves."""
    cfg = load_tickers_config(args.config)
    print(f"universe: {cfg.universe.name} ({len(cfg.tickers)} tickers)")
    for t in cfg.tickers:
        sector = f"  [{t.sector}]" if t.sector else ""
        name = f" — {t.name}" if t.name else ""
        print(f"  {t.symbol}{name}{sector}")
    return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
    """Download/refresh OHLCV into the local CSV cache."""
    cfg = load_tickers_config(args.config)
    root = project_root()
    cache_dir = resolve_cache_dir(cfg.data.cache_dir, root)
    provider = getattr(args, "provider", None) or cfg.data.provider
    print(f"config: {args.config or default_config_path()}")
    print(f"cache:  {cache_dir}")
    print(f"provider={provider} period={cfg.data.default_period} interval={cfg.data.default_interval}")
    bars = load_universe_ohlcv(cfg, force_refresh=args.force, root=root, provider=provider)
    for symbol, frame in bars.frames.items():
        last = frame.index[-1].date() if len(frame) else "?"
        print(f"  {symbol}: {len(frame)} bars, last={last}")
    if bars.errors:
        print("errors:", file=sys.stderr)
        for err in bars.errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    return 0


def _resolve_model_path(path: str | None) -> Path:
    """Resolve LightGBM artifact path relative to project root when needed."""
    p = Path(path) if path else DEFAULT_MODEL_PATH
    if not p.is_absolute():
        p = project_root() / p
    return p


def _cmd_train(args: argparse.Namespace) -> int:
    """Fit LightGBM on cached bars and write ``models/signal.txt``."""
    cfg = load_tickers_config(args.config)
    root = project_root()
    bars = load_universe_ohlcv(cfg, force_refresh=False, root=root)
    if bars.errors:
        for err in bars.errors:
            print(f"warn: {err}", file=sys.stderr)
    label_mode = getattr(args, "label_mode", None) or "relative"
    model = SignalModel(horizon=args.horizon, label_mode=label_mode, include_cs=True)
    result = model.fit(
        bars.frames,
        valid_fraction=args.valid_fraction,
        num_boost_round=args.rounds,
    )
    out = _resolve_model_path(args.output)
    saved = model.save(out)
    print(f"trained: n_train={result.n_train} n_valid={result.n_valid} label_mode={label_mode}")
    for key, val in result.metrics.items():
        print(f"  {key}={val:.4f}" if isinstance(val, float) else f"  {key}={val}")
    print(f"saved: {saved}")
    try:
        append_retrain_event(
            metrics=result.metrics,
            n_train=result.n_train,
            n_valid=result.n_valid,
        )
    except OSError as exc:
        log.warning("retrain event log skipped: %s", exc)
    log.info(
        "train complete n_train=%s n_valid=%s path=%s",
        result.n_train,
        result.n_valid,
        saved,
    )
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    """Walk-forward eval + baselines + calibration (does not overwrite model)."""
    cfg = load_tickers_config(args.config)
    root = project_root()
    bars = load_universe_ohlcv(cfg, force_refresh=False, root=root)
    if bars.errors:
        for err in bars.errors:
            print(f"warn: {err}", file=sys.stderr)
    try:
        report = run_signal_eval(
            bars.frames,
            horizon=args.horizon,
            n_folds=args.folds,
            num_boost_round=args.rounds,
            save=not args.no_save,
            relative_label=not args.absolute_label,
        )
    except (ValueError, RuntimeError) as exc:
        log.error("eval failed: %s", exc)
        print(f"eval failed: {exc}", file=sys.stderr)
        return 1
    for line in report.summary_lines():
        print(line)
    if not args.no_save:
        print("saved: data/learning/eval_latest.json")
    log.info(
        "eval done mean_acc=%.4f edge_al=%+.4f edge_mom=%+.4f",
        report.mean_accuracy,
        report.edge_vs_always_long,
        report.edge_vs_momentum,
    )
    # Non-zero if model fails both baselines (honest quality signal)
    if report.edge_vs_always_long <= 0 and report.edge_vs_momentum <= 0:
        return 2
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    """Walk-forward portfolio backtest + promotion gate (no live orders)."""
    cfg = load_tickers_config(args.config)
    root = project_root()
    risk = default_risk_limits(cfg)
    bars = load_universe_ohlcv(cfg, force_refresh=False, root=root)
    if bars.errors:
        for err in bars.errors:
            print(f"warn: {err}", file=sys.stderr)
    bt = BacktestConfig(
        initial_cash=float(args.cash),
        horizon=int(args.horizon),
        train_days=int(args.train_days),
        retrain_every=int(args.retrain_every),
        num_boost_round=int(args.rounds),
        cost_bps=float(args.cost_bps),
        buy_threshold=float(args.buy_threshold) if args.buy_threshold is not None else risk.buy_threshold,
        sell_threshold=float(args.sell_threshold) if args.sell_threshold is not None else risk.sell_threshold,
        fill=str(args.fill),
        momentum_top_n=int(args.momentum_top_n),
    )
    try:
        report = run_portfolio_backtest(bars.frames, cfg, risk=risk, bt=bt)
    except (ValueError, RuntimeError) as exc:
        log.error("backtest failed: %s", exc)
        print(f"backtest failed: {exc}", file=sys.stderr)
        return 1
    for line in report.summary_lines():
        print(line)
    if not args.no_save:
        path = save_backtest_report(report)
        print(f"saved: {path}")
    log.info(
        "backtest done gate=%s signal_ret=%.4f eq_ret=%.4f mom_ret=%.4f",
        report.gate.pass_,
        report.signal.total_return,
        report.equal_weight.total_return,
        report.momentum.total_return,
    )
    return 0 if report.gate.pass_ else 2


def _cmd_signals(args: argparse.Namespace) -> int:
    """Print ranked buy/hold/sell table from the trained signal model."""
    cfg = load_tickers_config(args.config)
    root = project_root()
    model_path = _resolve_model_path(args.model)
    if not model_path.is_file():
        print(f"model not found: {model_path}", file=sys.stderr)
        print("run: neotrade train", file=sys.stderr)
        return 1
    model = SignalModel.load(model_path)
    bars = load_universe_ohlcv(cfg, force_refresh=False, root=root)
    scored = score_universe(
        model,
        bars.frames,
        buy_threshold=args.buy_threshold,
        sell_threshold=args.sell_threshold,
    )
    print(f"{'SYMBOL':<8} {'PROBA':>7} {'SIDE':<5} AS_OF")
    for row in scored.rows:
        print(f"{row.symbol:<8} {row.proba:>7.3f} {row.side:<5} {row.as_of}")
    errors = list(scored.errors)
    if bars.errors:
        errors.extend(bars.errors)
    if errors:
        print("errors:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1 if not scored.rows else 0
    return 0


def _load_signals_for_paper(args: argparse.Namespace):
    """Shared path for paper-plan / paper-execute: config, risk, signals, prices."""
    cfg = load_tickers_config(args.config)
    root = project_root()
    risk = default_risk_limits(cfg)
    buy_th = getattr(args, "buy_threshold", None) or risk.buy_threshold
    sell_th = getattr(args, "sell_threshold", None) or risk.sell_threshold
    model_path = _resolve_model_path(getattr(args, "model", None))
    if not model_path.is_file():
        raise FileNotFoundError(f"model not found: {model_path} (run: neotrade train)")
    model = SignalModel.load(model_path)
    bars = load_universe_ohlcv(cfg, force_refresh=False, root=root)
    scored = score_universe(
        model,
        bars.frames,
        buy_threshold=buy_th,
        sell_threshold=sell_th,
    )
    prices = prices_for_plan(cfg, frames=bars.frames)
    return cfg, risk, scored.rows, prices


def _cmd_quotes(args: argparse.Namespace) -> int:
    """Print latest Alpaca market-data prices (cache fallback)."""
    cfg = load_tickers_config(args.config)
    snap = fetch_universe_quotes(cfg, prefer_alpaca=not args.cache_only, fallback_cache=True)
    print(f"feed={snap.feed or 'n/a'} symbols={len(snap.rows)}")
    print(f"{'SYMBOL':<8} {'PRICE':>10} {'BID':>10} {'ASK':>10} SOURCE")
    for r in snap.rows:
        px = f"{r.price:.2f}" if r.price is not None else "—"
        bid = f"{r.bid:.2f}" if r.bid is not None else "—"
        ask = f"{r.ask:.2f}" if r.ask is not None else "—"
        print(f"{r.symbol:<8} {px:>10} {bid:>10} {ask:>10} {r.source or '—'}")
    if snap.errors:
        print("errors:", file=sys.stderr)
        for err in snap.errors:
            print(f"  {err}", file=sys.stderr)
        priced = sum(1 for r in snap.rows if r.price is not None)
        return 1 if priced == 0 else 0
    return 0


def _cmd_account(_: argparse.Namespace) -> int:
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
    open_orders = client.list_orders(status="open", limit=50)
    print(f"open_orders={len(open_orders)}")
    for o in open_orders:
        print(
            f"  {o.get('side', '?'):<4} {str(o.get('symbol', '')):<6} "
            f"qty={o.get('qty')} status={o.get('status')} "
            f"filled={o.get('filled_qty', 0)}"
        )
    if open_orders and not positions:
        print("note: day market orders often stay accepted until the next US regular session")
    if not session.allow_execute:
        print("note: paper execute blocked until US RTH (09:30–16:00 ET); no after-hours")
    return 0


def _cmd_paper_plan(args: argparse.Namespace) -> int:
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
        cfg, risk, signals, prices = _load_signals_for_paper(args)
        client = AlpacaPaperClient()
        acct = client.get_account()
        positions = client.list_positions()
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
    )
    for line in plan.summary_lines():
        print(line)
    return 0


def _cmd_paper_execute(args: argparse.Namespace) -> int:
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
        cfg, risk, signals, prices = _load_signals_for_paper(args)
        client = AlpacaPaperClient()
        acct = client.get_account()
        if acct.trading_blocked or acct.account_blocked:
            log.error("account trading blocked")
            print("account trading blocked", file=sys.stderr)
            return 1
        positions = client.list_positions()
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
    )
    if not plan.intents:
        print("no intents to execute")
        for note in plan.notes:
            print(f"note: {note}")
        log.info("execute: no intents")
        return 0
    errors = 0
    for intent in plan.intents:
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
        except AlpacaAPIError as exc:
            errors += 1
            log.error("order fail %s: %s", intent.describe(), exc)
            print(f"ORDER FAIL {intent.describe()}: {exc}", file=sys.stderr)
    return 1 if errors else 0


def _cmd_session(_: argparse.Namespace) -> int:
    """Print US equity session phase and whether paper execute is allowed."""
    st = get_session_status()
    print(st.summary_line())
    print(f"phase={st.phase.value} is_rth={st.is_rth} trading_day={st.is_trading_day}")
    print(f"allow_execute={st.allow_execute}")
    if st.next_rth_open_et is not None:
        print(f"next_rth_open={st.next_rth_open_et.isoformat()}")
    return 0 if st.allow_execute else 1


def _cmd_advise(args: argparse.Namespace) -> int:
    """Run local LangGraph trading expert + performance analyst (Ollama)."""
    model_path = _resolve_model_path(args.model)
    if args.mock_llm:
        llm = MockLLM()
    else:
        cfg = OllamaConfig.from_env()
        if args.llm_model:
            cfg = OllamaConfig(
                host=cfg.host,
                model=args.llm_model,
                temperature=cfg.temperature,
                timeout=cfg.timeout,
            )
        llm = OllamaClient(cfg)
        if not llm.ping():
            print(
                f"Ollama not reachable at {cfg.host}. "
                "Install Ollama, run `ollama serve`, pull a small model "
                f"(e.g. `ollama pull {cfg.model}`), or use --mock-llm.",
                file=sys.stderr,
            )
            return 1
    try:
        report = run_advise(
            model_path=model_path,
            config_path=args.config,
            include_account=not args.no_account,
            llm=llm,
        )
    except FileNotFoundError as exc:
        log.error("%s", exc)
        print(str(exc), file=sys.stderr)
        return 1
    except (RuntimeError, OSError, ValueError) as exc:
        log.error("advise failed: %s", exc)
        print(f"advise failed: {exc}", file=sys.stderr)
        return 1
    print(report.render())
    print(f"\npolicy: {policy_blurb()}")
    rating = getattr(args, "rating", None)
    notes = getattr(args, "notes", "") or ""
    try:
        path = record_advice_run(
            report,
            source="cli",
            rating=rating,
            notes=notes or "auto from neotrade advise",
        )
        print(f"logged: {path}")
    except (OSError, ValueError) as exc:
        log.warning("advice log skipped: %s", exc)
    log.info("advise done stance=%s model=%s rating=%s", report.stance, report.model, rating)
    return 1 if report.errors and not report.trader_raw else 0


def _cmd_bench(_: argparse.Namespace) -> int:
    """Benchmark local Ollama latency and LightGBM score speed."""
    report = run_full_bench(save=True)
    for line in report.summary_lines():
        print(line)
    print("saved: data/learning/bench_latest.json")
    return 0 if report.ollama_ok or report.signal_score_s is not None else 1


def _cmd_dashboard(args: argparse.Namespace) -> int:
    """Launch the Streamlit dashboard subprocess."""
    import subprocess

    app = Path(__file__).resolve().parent / "dashboard" / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    if args.port:
        cmd.extend(["--server.port", str(args.port)])
    print(f"starting dashboard: {app}")
    return subprocess.call(cmd)


def _cmd_monitor(args: argparse.Namespace) -> int:
    """Poll Alpaca MD quotes on an interval (monitor only — never executes)."""
    base = default_monitor_config()
    interval = float(args.interval) if args.interval is not None else base.interval_s
    move_pct = float(args.move_pct) if args.move_pct is not None else base.move_pct
    log_path = Path(args.log) if args.log else (None if args.no_log else base.log_path)
    cfg_mon = MonitorConfig(
        interval_s=interval,
        move_pct=move_pct,
        prefer_alpaca=not args.cache_only,
        fallback_cache=True,
        log_path=log_path,
    )
    tickers_cfg = load_tickers_config(args.config)
    mon = QuoteMonitor(cfg_mon, cfg=tickers_cfg)
    max_ticks = 1 if args.once else args.max_ticks
    print(
        f"monitor start interval>={cfg_mon.clamped_interval():.0f}s "
        f"move_pct={cfg_mon.move_pct} max_ticks={max_ticks or '∞'} "
        f"(execute never called; RTH gate unchanged)",
        flush=True,
    )
    try:
        for tick in mon.iter_ticks(max_ticks=max_ticks):
            print(tick.summary_line(), flush=True)
            if args.verbose:
                for r in tick.snapshot.rows:
                    if r.price is None:
                        continue
                    print(
                        f"  {r.symbol:<6} {r.price:>10.2f}  {r.source or '—'}",
                        flush=True,
                    )
            for m in tick.moves:
                print(f"  MOVE {m.describe()}", flush=True)
            if tick.snapshot.errors and args.verbose:
                for err in tick.snapshot.errors:
                    print(f"  err: {err}", file=sys.stderr, flush=True)
    except KeyboardInterrupt:
        print("monitor stopped", flush=True)
        return 0
    return 0


def _cmd_stream(args: argparse.Namespace) -> int:
    """Alpaca MD WebSocket stream (IEX); monitor only — never executes."""
    cfg = load_tickers_config(args.config)
    symbols = cfg.symbols()
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    seconds = None if args.until_interrupt else float(args.seconds)
    try:
        state = run_stream_cli(
            symbols,
            seconds=seconds,
            max_messages=args.max_messages,
            verbose=args.verbose,
            feed=args.feed,
        )
    except KeyboardInterrupt:
        print("stream stopped", flush=True)
        return 0
    except (RuntimeError, OSError) as exc:
        log.error("stream failed: %s", exc)
        print(f"stream failed: {exc}", file=sys.stderr)
        return 1
    if state.last_error and not state.quotes:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argparse tree for the ``neotrade`` console script."""
    parser = argparse.ArgumentParser(prog="neotrade", description="Local paper-trading decision support")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    p_tickers = sub.add_parser("tickers", help="list configured universe")
    p_tickers.add_argument("--config", type=str, default=None, help="path to tickers.yaml")
    p_tickers.set_defaults(func=_cmd_tickers)

    p_fetch = sub.add_parser("fetch", help="download OHLCV into local cache")
    p_fetch.add_argument("--config", type=str, default=None, help="path to tickers.yaml")
    p_fetch.add_argument("--force", action="store_true", help="ignore cache freshness")
    p_fetch.add_argument(
        "--provider",
        type=str,
        default=None,
        choices=["auto", "alpaca", "yfinance"],
        help="override data.provider from config",
    )
    p_fetch.set_defaults(func=_cmd_fetch)

    p_quotes = sub.add_parser("quotes", help="latest prices via Alpaca market data (cache fallback)")
    p_quotes.add_argument("--config", type=str, default=None)
    p_quotes.add_argument("--cache-only", action="store_true", help="skip Alpaca; use cached closes")
    p_quotes.set_defaults(func=_cmd_quotes)

    p_mon = sub.add_parser(
        "monitor",
        help="poll quotes on an interval (watch only; never executes)",
    )
    p_mon.add_argument("--config", type=str, default=None)
    p_mon.add_argument(
        "--interval",
        type=float,
        default=None,
        help=f"seconds between polls (min 5, default {15})",
    )
    p_mon.add_argument(
        "--move-pct",
        type=float,
        default=None,
        help="flag symbols moving at least this %% vs prior tick (default 1.0)",
    )
    p_mon.add_argument("--once", action="store_true", help="single poll then exit")
    p_mon.add_argument(
        "--max-ticks",
        type=int,
        default=None,
        help="stop after N polls (default: run until Ctrl+C)",
    )
    p_mon.add_argument("--verbose", "-v", action="store_true", help="print each symbol price")
    p_mon.add_argument("--cache-only", action="store_true", help="skip Alpaca MD")
    p_mon.add_argument("--log", type=str, default=None, help="JSONL log path")
    p_mon.add_argument("--no-log", action="store_true", help="disable JSONL log")
    p_mon.set_defaults(func=_cmd_monitor)

    p_stream = sub.add_parser(
        "stream",
        help="Alpaca WebSocket quotes/trades (IEX; watch only, never executes)",
    )
    p_stream.add_argument("--config", type=str, default=None)
    p_stream.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="comma-separated symbols (default: full universe)",
    )
    p_stream.add_argument(
        "--seconds",
        type=float,
        default=30.0,
        help="run duration in seconds (default 30)",
    )
    p_stream.add_argument(
        "--until-interrupt",
        action="store_true",
        help="run until Ctrl+C (ignores --seconds)",
    )
    p_stream.add_argument("--max-messages", type=int, default=None, help="stop after N data msgs")
    p_stream.add_argument("--feed", type=str, default=None, help="iex (default) or sip")
    p_stream.add_argument("--verbose", "-v", action="store_true", help="print each tick")
    p_stream.set_defaults(func=_cmd_stream)

    p_train = sub.add_parser("train", help="train LightGBM signal model on cached OHLCV")
    p_train.add_argument("--config", type=str, default=None)
    p_train.add_argument("--output", type=str, default=str(DEFAULT_MODEL_PATH))
    p_train.add_argument("--horizon", type=int, default=5, help="forward-return label horizon (days)")
    p_train.add_argument("--rounds", type=int, default=160)
    p_train.add_argument("--valid-fraction", type=float, default=0.2)
    p_train.add_argument(
        "--label-mode",
        type=str,
        default="relative",
        choices=["relative", "absolute"],
        help="relative=beat CS median fwd ret (default); absolute=fwd_ret>0",
    )
    p_train.set_defaults(func=_cmd_train)

    p_eval = sub.add_parser(
        "eval",
        help="walk-forward LightGBM eval vs baselines (does not save model)",
    )
    p_eval.add_argument("--config", type=str, default=None)
    p_eval.add_argument("--horizon", type=int, default=5)
    p_eval.add_argument("--folds", type=int, default=4)
    p_eval.add_argument("--rounds", type=int, default=100)
    p_eval.add_argument(
        "--absolute-label",
        action="store_true",
        help="eval with absolute up/down labels instead of relative",
    )
    p_eval.add_argument("--no-save", action="store_true", help="skip writing eval_latest.json")
    p_eval.set_defaults(func=_cmd_eval)

    p_bt = sub.add_parser(
        "backtest",
        help="walk-forward portfolio BT vs eq-weight/momentum (promotion gate)",
    )
    p_bt.add_argument("--config", type=str, default=None)
    p_bt.add_argument("--cash", type=float, default=100_000.0)
    p_bt.add_argument("--horizon", type=int, default=5)
    p_bt.add_argument("--train-days", type=int, default=120)
    p_bt.add_argument("--retrain-every", type=int, default=21)
    p_bt.add_argument("--rounds", type=int, default=80)
    p_bt.add_argument("--cost-bps", type=float, default=5.0, help="one-way cost in bps per fill")
    p_bt.add_argument("--buy-threshold", type=float, default=None)
    p_bt.add_argument("--sell-threshold", type=float, default=None)
    p_bt.add_argument("--fill", type=str, default="next_open", choices=["next_open", "next_close"])
    p_bt.add_argument("--momentum-top-n", type=int, default=5)
    p_bt.add_argument("--no-save", action="store_true")
    p_bt.set_defaults(func=_cmd_backtest)

    p_sig = sub.add_parser("signals", help="score universe with trained model")
    p_sig.add_argument("--config", type=str, default=None)
    p_sig.add_argument("--model", type=str, default=str(DEFAULT_MODEL_PATH))
    p_sig.add_argument("--buy-threshold", type=float, default=0.55)
    p_sig.add_argument("--sell-threshold", type=float, default=0.45)
    p_sig.set_defaults(func=_cmd_signals)

    p_acct = sub.add_parser("account", help="show Alpaca paper account + positions")
    p_acct.set_defaults(func=_cmd_account)

    p_sess = sub.add_parser("session", help="US RTH session status (execute allowed?)")
    p_sess.set_defaults(func=_cmd_session)

    p_plan = sub.add_parser("paper-plan", help="dry-run trade plan from signals + risk")
    p_plan.add_argument("--config", type=str, default=None)
    p_plan.add_argument("--model", type=str, default=str(DEFAULT_MODEL_PATH))
    p_plan.add_argument("--buy-threshold", type=float, default=None)
    p_plan.add_argument("--sell-threshold", type=float, default=None)
    p_plan.set_defaults(func=_cmd_paper_plan)

    p_exec = sub.add_parser("paper-execute", help="submit paper market orders (requires --confirm)")
    p_exec.add_argument("--config", type=str, default=None)
    p_exec.add_argument("--model", type=str, default=str(DEFAULT_MODEL_PATH))
    p_exec.add_argument("--buy-threshold", type=float, default=None)
    p_exec.add_argument("--sell-threshold", type=float, default=None)
    p_exec.add_argument(
        "--confirm",
        action="store_true",
        help="required safety flag to place paper orders",
    )
    p_exec.set_defaults(func=_cmd_paper_execute)

    p_adv = sub.add_parser("advise", help="LangGraph agents: trading expert + performance analyst")
    p_adv.add_argument("--config", type=str, default=None)
    p_adv.add_argument("--model", type=str, default=str(DEFAULT_MODEL_PATH), help="LightGBM model path")
    p_adv.add_argument("--llm-model", type=str, default=None, help="Ollama model name (default env/llama3.2:3b)")
    p_adv.add_argument("--no-account", action="store_true", help="skip Alpaca account/plan context")
    p_adv.add_argument("--mock-llm", action="store_true", help="use offline stub LLM (no Ollama)")
    p_adv.add_argument(
        "--rating",
        type=int,
        default=None,
        choices=[1, 2, 3, 4, 5],
        help="optional 1-5 human quality rating (journal only; not for LightGBM)",
    )
    p_adv.add_argument("--notes", type=str, default="", help="optional journal note for learning log")
    p_adv.set_defaults(func=_cmd_advise)

    p_bench = sub.add_parser("bench", help="benchmark local Ollama + LightGBM efficiency")
    p_bench.set_defaults(func=_cmd_bench)

    p_dash = sub.add_parser("dashboard", help="launch Streamlit UI")
    p_dash.add_argument("--port", type=int, default=8501)
    p_dash.set_defaults(func=_cmd_dashboard)

    return parser


def main(argv: list[str] | None = None) -> None:
    """Parse CLI args and dispatch to the selected subcommand handler."""
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        raise SystemExit(_cmd_version(args))
    if args.command is None:
        _cmd_version(args)
        parser.print_help()
        raise SystemExit(0)
    log.debug("dispatch command=%s", args.command)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
