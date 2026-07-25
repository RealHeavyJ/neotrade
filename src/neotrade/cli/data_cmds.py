"""Data CLI: tickers, fetch, quotes."""
from __future__ import annotations

import argparse
import sys

from neotrade.config import default_config_path, load_tickers_config
from neotrade.config.load import project_root, resolve_cache_dir
from neotrade.data import fetch_universe_quotes, load_universe_ohlcv


def cmd_tickers(args: argparse.Namespace) -> int:
    """List configured universe tickers and sleeves."""
    cfg = load_tickers_config(args.config)
    print(f"universe: {cfg.universe.name} ({len(cfg.tickers)} tickers)")
    for t in cfg.tickers:
        sector = f"  [{t.sector}]" if t.sector else ""
        name = f" — {t.name}" if t.name else ""
        print(f"  {t.symbol}{name}{sector}")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
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


def cmd_quotes(args: argparse.Namespace) -> int:
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


