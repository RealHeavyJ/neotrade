"""Production-smart defaults for neotrade.

Principle
---------
**Defaults are the strictest practical settings** used for promote decisions and
daily ops. CLI flags are *opt-outs* for ablation, debugging, or faster smoke runs
— not the path to a “real” result.

Agents and docs should point here rather than scattering magic numbers.
"""

from __future__ import annotations

from typing import Final

# --- Market data ---
DATA_PERIOD: Final[str] = "2y"  # longer OOS for multi-window BT
DATA_INTERVAL: Final[str] = "1d"
DATA_MAX_AGE_HOURS: Final[float] = 24.0

# --- LightGBM train ---
TRAIN_HORIZON: Final[int] = 5
TRAIN_ROUNDS: Final[int] = 160
TRAIN_VALID_FRACTION: Final[float] = 0.2
TRAIN_LABEL_MODE: Final[str] = "relative"  # relative | absolute

# --- Eval ---
EVAL_FOLDS: Final[int] = 4
EVAL_ROUNDS: Final[int] = 100

# --- Portfolio backtest (promote path) ---
BT_CASH: Final[float] = 100_000.0
BT_TRAIN_DAYS: Final[int] = 180  # matches 2y history
BT_RETRAIN_EVERY: Final[int] = 21
BT_REBALANCE_EVERY: Final[int] = 14  # less churn; better 2y promote stability
BT_ROUNDS: Final[int] = 100
BT_COST_BPS: Final[float] = 5.0
BT_SLIP_BPS: Final[float] = 5.0
BT_COST_STRESS_BPS: Final[float] = 10.0
BT_SLIP_STRESS_BPS: Final[float] = 15.0
BT_FILL: Final[str] = "next_open"
BT_WINDOWS: Final[int] = 3
BT_MIN_WINDOW_PASS: Final[float] = 0.67
BT_MIN_SHARPE: Final[float] = 0.35
BT_USE_REGIME: Final[bool] = True
BT_REQUIRE_BOTH_BASELINES: Final[bool] = False  # True = harder; opt-in via --require-both
BT_PERIOD: Final[str] = DATA_PERIOD

# --- Risk / plan (also in tickers.yaml; keep aligned) ---
RISK_PLAN_MODE: Final[str] = "ranked"
RISK_TOP_N: Final[int] = 7  # broader book beats eq on 2y WF; 5 was too concentrated
RISK_MAX_POSITION_PCT: Final[float] = 0.15  # 1/7 ≈ 0.14; headroom under 0.15
RISK_MIN_CASH_PCT: Final[float] = 0.01
RISK_BUY_THRESHOLD: Final[float] = 0.50
RISK_SELL_THRESHOLD: Final[float] = 0.40

# --- Monitor / stream ---
MONITOR_INTERVAL_S: Final[float] = 15.0
STREAM_MAX_SYMBOLS: Final[int] = 30


def train_days_for_period(period: str, *, explicit: int | None = None) -> int:
    """Resolve train window from data period unless user set an explicit value."""
    if explicit is not None:
        return explicit
    p = (period or DATA_PERIOD).lower()
    if p in {"5y", "max"}:
        return 252
    if p in {"2y", "24mo"}:
        return 180
    if p in {"1y", "12mo"}:
        return 120
    return BT_TRAIN_DAYS
