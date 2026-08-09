"""CLI: social fetch / status / summary (X research module)."""

from __future__ import annotations

import argparse
import json
import sys

from neotrade.config import load_tickers_config
from neotrade.config.load import project_root
from neotrade.social.accounts import default_accounts_path, load_social_accounts
from neotrade.social.cache import cache_stats, load_posts
from neotrade.social.features import aggregate_by_ticker
from neotrade.social.pipeline import fetch_and_cache
from neotrade.social.policy import bearer_token, social_enabled, social_llm_enabled


def cmd_social(args: argparse.Namespace) -> int:
    """Dispatch ``neotrade social <action>``."""
    action = getattr(args, "social_action", None)
    if action == "fetch":
        return _cmd_fetch(args)
    if action == "status":
        return _cmd_status(args)
    if action == "summary":
        return _cmd_summary(args)
    print("usage: neotrade social {fetch,status,summary}", file=sys.stderr)
    return 2


def _cmd_fetch(args: argparse.Namespace) -> int:
    root = project_root()
    cfg = load_tickers_config(args.config)
    symbols = cfg.symbols()
    if getattr(args, "symbols", None):
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    max_accounts = getattr(args, "max_accounts", None)
    include_accounts = not getattr(args, "no_accounts", False)
    include_cashtags = not getattr(args, "no_cashtags", False)
    max_per = int(getattr(args, "max_results", 10) or 10)

    print(f"social fetch: symbols={len(symbols)} root={root}")
    print(f"  token={'yes' if bearer_token() else 'NO'} enabled_desk={social_enabled()}")
    print(f"  accounts_yaml={default_accounts_path(root)}")

    result = fetch_and_cache(
        symbols=symbols,
        root=root,
        max_per_query=max_per,
        max_accounts=max_accounts,
        include_accounts=include_accounts,
        include_cashtags=include_cashtags,
    )
    print(f"  fetched={result.n_fetched} written={result.n_written} errors={len(result.errors)}")
    for err in result.errors[:8]:
        print(f"  err: {err}", file=sys.stderr)
    if not result.token_present:
        return 1
    # partial API errors still exit 0 if something wrote
    if result.n_written == 0 and result.errors:
        return 1
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    root = project_root()
    stats = cache_stats(root)
    accounts = load_social_accounts(default_accounts_path(root))
    print("social status")
    print(f"  desk_enabled={social_enabled()} llm={social_llm_enabled()}")
    print(f"  token={'set' if bearer_token() else 'missing'}")
    print(f"  accounts_config={len(accounts)}")
    print(f"  cache_path={stats['path']}")
    print(f"  n_posts={stats['n_posts']} bytes={stats['bytes']}")
    print(f"  last_ts={stats.get('last_ts') or '—'}")
    meta = stats.get("meta") or {}
    if meta:
        print(f"  last_fetch={meta.get('last_fetch_ts')} ok={meta.get('ok')} written={meta.get('n_written')}")
        for err in (meta.get("errors") or [])[:5]:
            print(f"  last_err: {err}")
    return 0


def _cmd_summary(args: argparse.Namespace) -> int:
    root = project_root()
    cfg = load_tickers_config(args.config)
    hours = float(getattr(args, "hours", 48) or 48)
    posts = load_posts(root, max_age_hours=hours)
    aggs = aggregate_by_ticker(posts, universe=cfg.symbols())
    if getattr(args, "json", False):
        payload = {
            "hours": hours,
            "n_posts": len(posts),
            "tickers": [
                {
                    "ticker": a.ticker,
                    "n_posts": a.n_posts,
                    "mean_score": a.mean_score,
                    "eng_weighted_score": a.eng_weighted_score,
                    "label": a.label,
                    "bullish": a.bullish,
                    "bearish": a.bearish,
                    "neutral": a.neutral,
                }
                for a in aggs
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"social summary (last {hours:g}h) posts={len(posts)}")
    if not aggs:
        print("  (no ticker aggregates — fetch first or widen window)")
        return 0
    print(f"  {'TICKER':<8} {'N':>4} {'MEAN':>7} {'WMEAN':>7} LABEL")
    for a in aggs[:30]:
        print(
            f"  {a.ticker:<8} {a.n_posts:>4} {a.mean_score:>+7.2f} "
            f"{a.eng_weighted_score:>+7.2f} {a.label}"
        )
    return 0
