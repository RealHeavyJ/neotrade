"""Argparse tree for the neotrade console script."""
from __future__ import annotations

import argparse

from neotrade import defaults as D
from neotrade.broker.fills import MIN_FILLS_FOR_CALIBRATION
from neotrade.cli.agent_cmds import cmd_advise, cmd_desk, cmd_experiment
from neotrade.cli.broker_cmds import (
    cmd_account,
    cmd_fills,
    cmd_paper_execute,
    cmd_paper_plan,
    cmd_session,
)
from neotrade.cli.common import DEFAULT_MODEL_PATH, cmd_version
from neotrade.cli.data_cmds import cmd_fetch, cmd_quotes, cmd_tickers
from neotrade.cli.ml_cmds import cmd_backtest, cmd_eval, cmd_signals, cmd_train
from neotrade.cli.ops_cmds import (
    cmd_bench,
    cmd_dashboard,
    cmd_monitor,
    cmd_status,
    cmd_stream,
    cmd_weekly,
)
from neotrade.cli.social_cmds import cmd_social

# re-export for callers that expect version on parser module
__all__ = ["build_parser", "cmd_version"]


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argparse tree for the ``neotrade`` console script."""
    parser = argparse.ArgumentParser(prog="neotrade", description="Local paper-trading decision support")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    p_tickers = sub.add_parser("tickers", help="list configured universe")
    p_tickers.add_argument("--config", type=str, default=None, help="path to tickers.yaml")
    p_tickers.set_defaults(func=cmd_tickers)

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
    p_fetch.set_defaults(func=cmd_fetch)

    p_quotes = sub.add_parser("quotes", help="latest prices via Alpaca market data (cache fallback)")
    p_quotes.add_argument("--config", type=str, default=None)
    p_quotes.add_argument("--cache-only", action="store_true", help="skip Alpaca; use cached closes")
    p_quotes.set_defaults(func=cmd_quotes)

    p_social = sub.add_parser(
        "social",
        help="X/Twitter research: fetch/cache/grade posts (desk context; not LightGBM train)",
    )
    social_sub = p_social.add_subparsers(dest="social_action", required=True)
    p_soc_fetch = social_sub.add_parser("fetch", help="pull recent posts + lexicon grade → data/social/")
    p_soc_fetch.add_argument("--config", type=str, default=None)
    p_soc_fetch.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="comma-separated cashtag symbols (default: full universe)",
    )
    p_soc_fetch.add_argument("--max-results", type=int, default=10, help="per-query max (10–100)")
    p_soc_fetch.add_argument(
        "--max-accounts",
        type=int,
        default=None,
        help="cap curated account pulls (default: all in social_accounts.yaml)",
    )
    p_soc_fetch.add_argument("--no-accounts", action="store_true", help="cashtag search only")
    p_soc_fetch.add_argument("--no-cashtags", action="store_true", help="curated accounts only")
    p_soc_fetch.set_defaults(func=cmd_social)
    p_soc_status = social_sub.add_parser("status", help="token, cache age, last fetch")
    p_soc_status.set_defaults(func=cmd_social)
    p_soc_sum = social_sub.add_parser("summary", help="per-ticker aggregates from cache")
    p_soc_sum.add_argument("--config", type=str, default=None)
    p_soc_sum.add_argument("--hours", type=float, default=48.0, help="lookback window (default 48)")
    p_soc_sum.add_argument("--json", action="store_true", help="JSON output")
    p_soc_sum.set_defaults(func=cmd_social)

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
    p_mon.set_defaults(func=cmd_monitor)

    p_stream = sub.add_parser(
        "stream",
        help="Alpaca WebSocket trades (IEX; watch only). Free tier: limited symbols.",
    )
    p_stream.add_argument("--config", type=str, default=None)
    p_stream.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="comma-separated symbols (default: universe, capped for free IEX)",
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
    p_stream.add_argument(
        "--quotes",
        action="store_true",
        help="also subscribe quotes (uses more of free symbol budget)",
    )
    p_stream.add_argument(
        "--quotes-only",
        action="store_true",
        help="subscribe quotes only (no trades)",
    )
    p_stream.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help="cap symbols (default 30 / NEOTRADE_STREAM_MAX_SYMBOLS)",
    )
    p_stream.set_defaults(func=cmd_stream)

    p_train = sub.add_parser("train", help="train LightGBM signal model on cached OHLCV")
    p_train.add_argument("--config", type=str, default=None)
    p_train.add_argument("--output", type=str, default=str(DEFAULT_MODEL_PATH))
    p_train.add_argument(
        "--horizon",
        type=int,
        default=D.TRAIN_HORIZON,
        help=f"forward-return label horizon days (default {D.TRAIN_HORIZON})",
    )
    p_train.add_argument("--rounds", type=int, default=D.TRAIN_ROUNDS)
    p_train.add_argument("--valid-fraction", type=float, default=D.TRAIN_VALID_FRACTION)
    p_train.add_argument(
        "--label-mode",
        type=str,
        default=D.TRAIN_LABEL_MODE,
        choices=["relative", "absolute"],
        help="relative=beat CS median (default); absolute=fwd_ret>0 ablation",
    )
    p_train.set_defaults(func=cmd_train)

    p_eval = sub.add_parser(
        "eval",
        help="walk-forward LightGBM eval vs baselines (does not save model)",
    )
    p_eval.add_argument("--config", type=str, default=None)
    p_eval.add_argument("--horizon", type=int, default=D.TRAIN_HORIZON)
    p_eval.add_argument("--folds", type=int, default=D.EVAL_FOLDS)
    p_eval.add_argument("--rounds", type=int, default=D.EVAL_ROUNDS)
    p_eval.add_argument(
        "--absolute-label",
        action="store_true",
        help="eval with absolute up/down labels instead of relative",
    )
    p_eval.add_argument(
        "--ablate",
        action="store_true",
        help="feature-group leave-one-out ablation (research; writes ablation_latest.json)",
    )
    p_eval.add_argument("--no-save", action="store_true", help="skip writing eval_latest.json")
    p_eval.set_defaults(func=cmd_eval)

    p_bt = sub.add_parser(
        "backtest",
        help="strict portfolio BT + promote gate (defaults=production; flags=ablation)",
    )
    p_bt.add_argument("--config", type=str, default=None)
    p_bt.add_argument("--cash", type=float, default=D.BT_CASH)
    p_bt.add_argument("--horizon", type=int, default=D.TRAIN_HORIZON)
    p_bt.add_argument(
        "--train-days",
        type=int,
        default=None,
        help=f"train window (default: auto from period, usually {D.BT_TRAIN_DAYS})",
    )
    p_bt.add_argument("--retrain-every", type=int, default=D.BT_RETRAIN_EVERY)
    p_bt.add_argument(
        "--rebalance-every",
        type=int,
        default=D.BT_REBALANCE_EVERY,
        help=f"days between score+rebalance (default {D.BT_REBALANCE_EVERY})",
    )
    p_bt.add_argument("--rounds", type=int, default=D.BT_ROUNDS)
    p_bt.add_argument(
        "--cost-bps",
        type=float,
        default=D.BT_COST_BPS,
        help=f"fee bps (default {D.BT_COST_BPS}; use 0 only for ablation)",
    )
    p_bt.add_argument(
        "--slip-bps",
        type=float,
        default=None,
        help=(
            f"adverse slip bps (default: fill calibration or {D.BT_SLIP_BPS}; "
            "use 0 only for ablation)"
        ),
    )
    p_bt.add_argument(
        "--period",
        type=str,
        default=None,
        help=f"OHLCV lookback (default config/{D.BT_PERIOD}; use 1y only for fast smoke)",
    )
    p_bt.add_argument(
        "--force-refresh",
        action="store_true",
        help="re-download bars",
    )
    p_bt.add_argument("--buy-threshold", type=float, default=None)
    p_bt.add_argument("--sell-threshold", type=float, default=None)
    p_bt.add_argument(
        "--fill",
        type=str,
        default=D.BT_FILL,
        choices=["next_open", "next_close"],
    )
    p_bt.add_argument("--momentum-top-n", type=int, default=D.RISK_TOP_N)
    p_bt.add_argument(
        "--windows",
        type=int,
        default=D.BT_WINDOWS,
        help=f"stability windows (default {D.BT_WINDOWS}; 1=disable multi-window)",
    )
    p_bt.add_argument(
        "--min-window-pass",
        type=float,
        default=D.BT_MIN_WINDOW_PASS,
        help=f"fraction of windows that must PASS (default {D.BT_MIN_WINDOW_PASS})",
    )
    p_bt.add_argument("--no-regime", action="store_true", help="ablation: disable regime filter")
    p_bt.add_argument(
        "--cost-stress-bps",
        type=float,
        default=D.BT_COST_STRESS_BPS,
        help=f"stress fee bps (default {D.BT_COST_STRESS_BPS})",
    )
    p_bt.add_argument(
        "--slip-stress-bps",
        type=float,
        default=D.BT_SLIP_STRESS_BPS,
        help=f"stress slip bps (default {D.BT_SLIP_STRESS_BPS})",
    )
    p_bt.add_argument("--min-sharpe", type=float, default=D.BT_MIN_SHARPE)
    p_bt.add_argument(
        "--require-both",
        action="store_true",
        help="harder gate: beat both eq-weight and momentum",
    )
    p_bt.add_argument(
        "--fast",
        action="store_true",
        help="ablation smoke: 1y, 1 window, no friction stress (NOT for promote)",
    )
    p_bt.add_argument("--no-save", action="store_true")
    p_bt.set_defaults(func=cmd_backtest)

    p_sig = sub.add_parser("signals", help="score universe with trained model")
    p_sig.add_argument("--config", type=str, default=None)
    p_sig.add_argument("--model", type=str, default=str(DEFAULT_MODEL_PATH))
    p_sig.add_argument("--buy-threshold", type=float, default=0.55)
    p_sig.add_argument("--sell-threshold", type=float, default=0.45)
    p_sig.set_defaults(func=cmd_signals)

    p_acct = sub.add_parser("account", help="show Alpaca paper account + positions")
    p_acct.set_defaults(func=cmd_account)

    p_sess = sub.add_parser("session", help="US RTH session status (execute allowed?)")
    p_sess.set_defaults(func=cmd_session)

    p_plan = sub.add_parser("paper-plan", help="dry-run trade plan from signals + risk")
    p_plan.add_argument("--config", type=str, default=None)
    p_plan.add_argument("--model", type=str, default=str(DEFAULT_MODEL_PATH))
    p_plan.add_argument("--buy-threshold", type=float, default=None)
    p_plan.add_argument("--sell-threshold", type=float, default=None)
    p_plan.set_defaults(func=cmd_paper_plan)

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
    p_exec.set_defaults(func=cmd_paper_execute)

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
    p_adv.set_defaults(func=cmd_advise)

    p_desk = sub.add_parser(
        "desk",
        help="multi-agent desk (ops/quant/PM/critic) — smarter process, no auto-execute",
    )
    p_desk.add_argument("--config", type=str, default=None)
    p_desk.add_argument("--model", type=str, default=str(DEFAULT_MODEL_PATH))
    p_desk.add_argument("--llm-model", type=str, default=None)
    p_desk.add_argument("--no-account", action="store_true")
    p_desk.add_argument("--mock-llm", action="store_true")
    p_desk.add_argument("--no-save", action="store_true")
    p_desk.set_defaults(func=cmd_desk)

    p_exp = sub.add_parser(
        "experiment",
        help="experiment ledger: open/complete desk experiments with gate snapshots",
    )
    exp_sub = p_exp.add_subparsers(dest="experiment_action", required=True)
    p_exp_list = exp_sub.add_parser("list", help="list experiments")
    p_exp_list.add_argument("--status", choices=["open", "complete"], default=None)
    p_exp_list.add_argument("--limit", type=int, default=20)
    p_exp_list.set_defaults(func=cmd_experiment)
    p_exp_snap = exp_sub.add_parser("snapshot", help="print current eval/BT gate snapshot")
    p_exp_snap.set_defaults(func=cmd_experiment)
    p_exp_open = exp_sub.add_parser("open", help="open experiment")
    p_exp_open.add_argument("--text", type=str, default=None, help="hypothesis text")
    p_exp_open.add_argument("--from-desk", action="store_true", help="use desk_latest EXPERIMENT")
    p_exp_open.add_argument("--notes", type=str, default="")
    p_exp_open.set_defaults(func=cmd_experiment)
    p_exp_done = exp_sub.add_parser("complete", help="complete experiment with after snapshot")
    p_exp_done.add_argument("--id", type=str, default=None, help="full id or prefix")
    p_exp_done.add_argument("--latest", action="store_true", help="complete most recent open")
    p_exp_done.add_argument(
        "--all",
        action="store_true",
        help="complete ALL open experiments (discipline sweep)",
    )
    p_exp_done.add_argument(
        "--outcome",
        choices=["pass", "fail", "mixed", "abandoned"],
        default=None,
        help="default: auto from gate delta (or abandoned with --all)",
    )
    p_exp_done.add_argument("--notes", type=str, default="")
    p_exp_done.set_defaults(func=cmd_experiment)
    p_exp_rec = exp_sub.add_parser(
        "reconcile",
        help="enforce single-open: abandon duplicate open rows",
    )
    p_exp_rec.set_defaults(func=cmd_experiment)
    p_exp_show = exp_sub.add_parser("show", help="show one experiment JSON")
    p_exp_show.add_argument("--id", type=str, required=True)
    p_exp_show.set_defaults(func=cmd_experiment)

    p_status = sub.add_parser(
        "status",
        help="promote gate + defaults + artifact age (research snapshot)",
    )
    p_status.add_argument("--model", type=str, default=str(DEFAULT_MODEL_PATH))
    p_status.set_defaults(func=cmd_status)

    p_bench = sub.add_parser("bench", help="benchmark local Ollama + LightGBM efficiency")
    p_bench.set_defaults(func=cmd_bench)

    p_week = sub.add_parser(
        "weekly",
        help="weekly promote: fetch→train→eval→backtest→desk (never executes)",
    )
    p_week.add_argument("--config", type=str, default=None)
    p_week.add_argument(
        "--no-force-fetch",
        action="store_true",
        help="fetch without --force (default forces refresh)",
    )
    p_week.add_argument("--no-desk", action="store_true", help="skip desk + experiment open")
    p_week.add_argument("--no-signals", action="store_true", help="skip post-BT signals")
    p_week.add_argument(
        "--mock-llm",
        action="store_true",
        help="force desk --mock-llm (offline)",
    )
    p_week.add_argument(
        "--real-llm",
        action="store_true",
        help="require Ollama desk (fail open to mock only if neither flag)",
    )
    p_week.add_argument("--no-save", action="store_true")
    p_week.set_defaults(func=cmd_weekly)

    p_fills = sub.add_parser(
        "fills",
        help="paper fill slip report / calibrate BT slip_bps (n≥20 to apply)",
    )
    p_fills.add_argument("--config", type=str, default=None)
    p_fills.add_argument("--limit", type=int, default=100, help="closed orders to scan")
    p_fills.add_argument("--show", type=int, default=10, help="print last N observations")
    p_fills.add_argument(
        "--min-n",
        type=int,
        default=MIN_FILLS_FOR_CALIBRATION,
        help=f"fills required before --apply (default {MIN_FILLS_FOR_CALIBRATION})",
    )
    p_fills.add_argument(
        "--apply",
        action="store_true",
        help="write slip_calibration.json when n≥min-n (feeds bare backtest default)",
    )
    p_fills.add_argument(
        "--backfill",
        action="store_true",
        help="log closed fills vs *current* quote mid (weak; prefer execute-time)",
    )
    p_fills.add_argument("--no-broker", action="store_true", help="journal only")
    p_fills.add_argument("--no-quotes", action="store_true")
    p_fills.set_defaults(func=cmd_fills)

    p_dash = sub.add_parser("dashboard", help="launch Streamlit UI")
    p_dash.add_argument("--port", type=int, default=8501)
    p_dash.set_defaults(func=cmd_dashboard)

    return parser

