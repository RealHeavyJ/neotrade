"""Ops CLI: weekly, monitor, stream, bench, dashboard."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from neotrade.cli.common import log
from neotrade.config import load_tickers_config
from neotrade.monitor import MonitorConfig, QuoteMonitor, default_monitor_config
from neotrade.monitor.stream import run_stream_cli
from neotrade.ops.weekly import run_weekly_promote
from neotrade.perf.bench import run_full_bench

def cmd_bench(_: argparse.Namespace) -> int:
    """Benchmark local Ollama latency and LightGBM score speed."""
    report = run_full_bench(save=True)
    for line in report.summary_lines():
        print(line)
    print("saved: data/learning/bench_latest.json")
    return 0 if report.ollama_ok or report.signal_score_s is not None else 1


def cmd_weekly(args: argparse.Namespace) -> int:
    """Weekly promote cadence: fetch→train→eval→backtest→desk. Never executes."""
    mock = True if args.mock_llm else (False if args.real_llm else None)
    result = run_weekly_promote(
        force_fetch=not args.no_force_fetch,
        skip_desk=bool(args.no_desk),
        mock_llm=mock,
        skip_signals=bool(args.no_signals),
        config=args.config,
        save=not args.no_save,
    )
    for line in result.summary_lines():
        print(line)
    if result.promote:
        print("WEEKLY_PROMOTE_PASS — model ok for paper use under bare BT defaults")
    else:
        print(
            "WEEKLY_PROMOTE_FAIL — do not trust new model; fix gates before execute",
            file=sys.stderr,
        )
    return int(result.exit_code)


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Launch the Streamlit dashboard subprocess."""
    import subprocess

    app = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
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


def cmd_monitor(args: argparse.Namespace) -> int:
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


def cmd_stream(args: argparse.Namespace) -> int:
    """Alpaca MD WebSocket stream (IEX); monitor only — never executes."""
    cfg = load_tickers_config(args.config)
    symbols = cfg.symbols()
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    seconds = None if args.until_interrupt else float(args.seconds)
    # Default trades-only (free IEX symbol budget). --quotes adds quote channel.
    subscribe_quotes = bool(args.quotes)
    subscribe_trades = not bool(args.quotes_only)
    if args.quotes_only:
        subscribe_quotes = True
        subscribe_trades = False
    try:
        state = run_stream_cli(
            symbols,
            seconds=seconds,
            max_messages=args.max_messages,
            verbose=args.verbose,
            feed=args.feed,
            subscribe_trades=subscribe_trades,
            subscribe_quotes=subscribe_quotes,
            max_symbols=args.max_symbols,
        )
    except KeyboardInterrupt:
        print("stream stopped", flush=True)
        return 0
    except (RuntimeError, OSError) as exc:
        log.error("stream failed: %s", exc)
        print(f"stream failed: {exc}", file=sys.stderr)
        return 1
    if state.last_error and not state.quotes:
        err = state.last_error.lower()
        if "symbol limit" in err:
            print(
                "hint: reduce symbols, e.g. neotrade stream --symbols NVDA,AMD,ARM,TSM -v",
                file=sys.stderr,
            )
        return 1
    return 0


