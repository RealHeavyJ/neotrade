"""Shared CLI helpers."""
from __future__ import annotations

import argparse
from pathlib import Path

from neotrade import __version__
from neotrade.broker import default_risk_limits
from neotrade.config import load_tickers_config
from neotrade.config.load import project_root
from neotrade.data import load_universe_ohlcv, prices_for_plan
from neotrade.logging_config import get_logger
from neotrade.signals import SignalModel, score_universe

DEFAULT_MODEL_PATH = Path("models/signal.txt")
log = get_logger("cli")


def resolve_model_path(path: str | None) -> Path:
    """Resolve LightGBM artifact path relative to project root when needed."""
    p = Path(path) if path else DEFAULT_MODEL_PATH
    if not p.is_absolute():
        p = project_root() / p
    return p


def load_signals_for_paper(args: argparse.Namespace):
    """Shared path for paper-plan / paper-execute: config, risk, signals, prices."""
    cfg = load_tickers_config(args.config)
    root = project_root()
    risk = default_risk_limits(cfg)
    buy_th = getattr(args, "buy_threshold", None) or risk.buy_threshold
    sell_th = getattr(args, "sell_threshold", None) or risk.sell_threshold
    model_path = resolve_model_path(getattr(args, "model", None))
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


def cmd_version(_: argparse.Namespace) -> int:
    """Print package version."""
    print(f"neotrade v{__version__}")
    return 0
