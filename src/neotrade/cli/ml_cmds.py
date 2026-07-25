"""ML CLI: train, eval, backtest, signals."""
from __future__ import annotations

import argparse
import sys

from neotrade import defaults as D
from neotrade.broker import default_risk_limits
from neotrade.cli.common import log, resolve_model_path
from neotrade.config import load_tickers_config
from neotrade.config.load import project_root
from neotrade.data import load_universe_ohlcv
from neotrade.learning.log import append_retrain_event
from neotrade.signals import SignalModel, score_universe
from neotrade.signals.backtest import BacktestConfig, run_portfolio_backtest, save_backtest_report
from neotrade.signals.eval import run_feature_ablation, run_signal_eval


def cmd_train(args: argparse.Namespace) -> int:
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
    out = resolve_model_path(args.output)
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


def cmd_eval(args: argparse.Namespace) -> int:
    """Walk-forward eval + baselines + calibration (does not overwrite model)."""
    cfg = load_tickers_config(args.config)
    root = project_root()
    bars = load_universe_ohlcv(cfg, force_refresh=False, root=root)
    if bars.errors:
        for err in bars.errors:
            print(f"warn: {err}", file=sys.stderr)
    if getattr(args, "ablate", False):
        try:
            ab = run_feature_ablation(
                bars.frames,
                horizon=args.horizon,
                n_folds=args.folds,
                num_boost_round=min(int(args.rounds), 80),
                relative_label=not args.absolute_label,
                save=not args.no_save,
            )
        except (ValueError, RuntimeError) as exc:
            log.error("ablation failed: %s", exc)
            print(f"ablation failed: {exc}", file=sys.stderr)
            return 1
        for line in ab.summary_lines():
            print(line)
        if not args.no_save:
            print("saved: data/learning/ablation_latest.json")
        return 0
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


def cmd_backtest(args: argparse.Namespace) -> int:
    """Walk-forward portfolio backtest + promotion gate (no live orders).

    Bare ``neotrade backtest`` uses production-strict defaults (2y, slip, stress,
    multi-window). Flags are opt-outs for ablation — see ``neotrade.defaults``.
    """
    cfg = load_tickers_config(args.config)
    root = project_root()
    risk = default_risk_limits(cfg)
    # Production path is strict; --fast is explicit ablation only
    if getattr(args, "fast", False):
        period = args.period or "1y"
        args.windows = 1
        args.cost_bps = 0.0
        args.slip_bps = 0.0
        args.cost_stress_bps = 0.0
        args.slip_stress_bps = 0.0
        args.no_regime = True
        print("warn: --fast ablation (not valid for promote)", file=sys.stderr)
    else:
        period = args.period if args.period is not None else (cfg.data.default_period or D.BT_PERIOD)

    force = bool(args.force_refresh)
    if period != cfg.data.default_period:
        print(f"data period: {period} (config default was {cfg.data.default_period})")
        force = True
    bars = load_universe_ohlcv(
        cfg,
        force_refresh=force,
        root=root,
        period=period,
    )
    if bars.errors:
        for err in bars.errors:
            print(f"warn: {err}", file=sys.stderr)
    train_days = D.train_days_for_period(period, explicit=args.train_days)
    print(
        f"bt: period={period} train_days={train_days} "
        f"cost={args.cost_bps}bps slip={args.slip_bps}bps "
        f"windows={args.windows} regime={not args.no_regime} "
        f"stress cost/slip={args.cost_stress_bps}/{args.slip_stress_bps}"
    )
    bt = BacktestConfig(
        initial_cash=float(args.cash),
        horizon=int(args.horizon),
        train_days=train_days,
        retrain_every=int(args.retrain_every),
        rebalance_every=int(args.rebalance_every),
        num_boost_round=int(args.rounds),
        cost_bps=float(args.cost_bps),
        slip_bps=float(args.slip_bps) if args.slip_bps is not None else D.effective_slip_bps(),
        buy_threshold=float(args.buy_threshold) if args.buy_threshold is not None else risk.buy_threshold,
        sell_threshold=float(args.sell_threshold) if args.sell_threshold is not None else risk.sell_threshold,
        fill=str(args.fill),
        momentum_top_n=int(args.momentum_top_n),
        n_windows=int(args.windows),
        min_window_pass_frac=float(args.min_window_pass),
        use_regime=not args.no_regime,
        cost_stress_bps=float(args.cost_stress_bps),
        slip_stress_bps=float(args.slip_stress_bps),
        min_sharpe=float(args.min_sharpe),
        require_both_baselines=bool(args.require_both),
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
        "backtest done promote=%s full_gate=%s signal_ret=%.4f",
        report.promote,
        report.gate.pass_,
        report.signal.total_return,
    )
    # exit 0 only if full + stable gates pass (smarter promote)
    return 0 if report.promote else 2


def cmd_signals(args: argparse.Namespace) -> int:
    """Print ranked buy/hold/sell table from the trained signal model."""
    cfg = load_tickers_config(args.config)
    root = project_root()
    model_path = resolve_model_path(args.model)
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


