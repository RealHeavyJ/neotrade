"""Portfolio walk-forward backtest for neotrade signals + risk plan.

Maximizes long-term value by:
  * Reusing production features, relative labels, and :func:`build_trade_plan`
  * Walk-forward retrain (no peeking)
  * Next-open fills + proportional costs
  * Baselines: equal-weight buy-hold, top-N momentum
  * Promotion gate metrics for model ship/no-ship

Does **not** place live/paper orders. Advise prose is never used.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from neotrade.broker.alpaca import AccountSnapshot, Position
from neotrade.broker.plan import build_trade_plan
from neotrade.broker.risk import RiskLimits, default_risk_limits, sleeve_map
from neotrade.config.load import project_root
from neotrade.config.models import TickersConfig
from neotrade.logging_config import get_logger
from neotrade.signals.features import (
    add_cross_section_features,
    build_features,
    build_labeled_frame,
    model_feature_names,
)
from neotrade.signals.model import DEFAULT_PARAMS
from neotrade.signals.regime import detect_regime_from_close_panel
from neotrade.signals.score import SignalRow, side_from_proba

log = get_logger("signals.backtest")

TRADING_DAYS_PER_YEAR = 252


@dataclass
class BacktestConfig:
    """Knobs for portfolio walk-forward backtest.

    Defaults come from :mod:`neotrade.defaults` (strict promote path).
    """

    initial_cash: float = 100_000.0
    horizon: int = 5
    train_days: int = 180
    retrain_every: int = 21
    rebalance_every: int = 14
    num_boost_round: int = 100
    cost_bps: float = 5.0
    slip_bps: float = 5.0
    buy_threshold: float = 0.50
    sell_threshold: float = 0.40
    fill: str = "next_open"
    min_history: int = 80
    momentum_top_n: int = 7
    n_windows: int = 3
    min_window_pass_frac: float = 0.67
    require_both_baselines: bool = False
    min_sharpe: float = 0.35
    use_regime: bool = True
    cost_stress_bps: float = 10.0
    slip_stress_bps: float = 15.0

    @classmethod
    def production(cls) -> BacktestConfig:
        """Strict defaults used by bare ``neotrade backtest``."""
        from neotrade import defaults as d

        return cls(
            initial_cash=d.BT_CASH,
            horizon=d.TRAIN_HORIZON,
            train_days=d.BT_TRAIN_DAYS,
            retrain_every=d.BT_RETRAIN_EVERY,
            rebalance_every=d.BT_REBALANCE_EVERY,
            num_boost_round=d.BT_ROUNDS,
            cost_bps=d.BT_COST_BPS,
            slip_bps=d.effective_slip_bps(),
            buy_threshold=d.RISK_BUY_THRESHOLD,
            sell_threshold=d.RISK_SELL_THRESHOLD,
            fill=d.BT_FILL,
            n_windows=d.BT_WINDOWS,
            min_window_pass_frac=d.BT_MIN_WINDOW_PASS,
            require_both_baselines=d.BT_REQUIRE_BOTH_BASELINES,
            min_sharpe=d.BT_MIN_SHARPE,
            use_regime=d.BT_USE_REGIME,
            cost_stress_bps=d.BT_COST_STRESS_BPS,
            slip_stress_bps=d.BT_SLIP_STRESS_BPS,
        )


@dataclass
class StrategyMetrics:
    """Summary performance for one equity curve."""

    name: str
    total_return: float
    cagr: float
    max_drawdown: float
    sharpe: float
    volatility: float
    turnover: float
    n_days: int
    final_equity: float
    n_trades: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GateResult:
    """Ship/no-ship recommendation for the signal strategy."""

    pass_: bool
    reasons: list[str] = field(default_factory=list)
    beat_equal_weight: bool = False
    beat_momentum: bool = False
    drawdown_ok: bool = False
    sharpe_ok: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["pass"] = d.pop("pass_")
        return d


@dataclass
class WindowResult:
    """One chronological sub-window backtest summary."""

    label: str
    start: str
    end: str
    signal_return: float
    eq_return: float
    mom_return: float
    max_drawdown: float
    sharpe: float
    gate_pass: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BacktestReport:
    """Full backtest output for CLI / learning log / gates."""

    ts: str
    config: dict[str, Any]
    signal: StrategyMetrics
    equal_weight: StrategyMetrics
    momentum: StrategyMetrics
    gate: GateResult
    equity_curve: list[dict[str, float | str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    windows: list[WindowResult] = field(default_factory=list)
    stable_gate: GateResult | None = None

    def summary_lines(self) -> list[str]:
        g = "PASS" if self.gate.pass_ else "FAIL"
        lines = [
            f"backtest @ {self.ts}  full_sample_gate={g}",
            (
                f"signal:  ret={self.signal.total_return:+.2%}  cagr={self.signal.cagr:+.2%}  "
                f"maxDD={self.signal.max_drawdown:.2%}  sharpe={self.signal.sharpe:.2f}  "
                f"turn={self.signal.turnover:.2f}  trades={self.signal.n_trades}"
            ),
            (
                f"eq_wt:   ret={self.equal_weight.total_return:+.2%}  cagr={self.equal_weight.cagr:+.2%}  "
                f"maxDD={self.equal_weight.max_drawdown:.2%}  sharpe={self.equal_weight.sharpe:.2f}"
            ),
            (
                f"mom_top: ret={self.momentum.total_return:+.2%}  cagr={self.momentum.cagr:+.2%}  "
                f"maxDD={self.momentum.max_drawdown:.2%}  sharpe={self.momentum.sharpe:.2f}"
            ),
            (
                f"edge_ret vs eq={self.signal.total_return - self.equal_weight.total_return:+.2%}  "
                f"vs mom={self.signal.total_return - self.momentum.total_return:+.2%}"
            ),
        ]
        for r in self.gate.reasons:
            lines.append(f"gate: {r}")
        if self.windows:
            n_pass = sum(1 for w in self.windows if w.gate_pass)
            lines.append(
                f"stable_windows: {n_pass}/{len(self.windows)} PASS "
                f"(need ≥{self.config.get('min_window_pass_frac', 0.67):.0%})"
            )
            for w in self.windows:
                flag = "PASS" if w.gate_pass else "FAIL"
                lines.append(
                    f"  {w.label} [{w.start}→{w.end}] {flag} "
                    f"sig={w.signal_return:+.1%} eq={w.eq_return:+.1%} mom={w.mom_return:+.1%} "
                    f"dd={w.max_drawdown:.1%} sh={w.sharpe:.2f}"
                )
        if self.stable_gate is not None:
            sg = "PASS" if self.stable_gate.pass_ else "FAIL"
            lines.append(f"stable_gate={sg}")
            for r in self.stable_gate.reasons:
                lines.append(f"stable: {r}")
        for n in self.notes:
            lines.append(f"note: {n}")
        return lines

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "config": self.config,
            "signal": self.signal.to_dict(),
            "equal_weight": self.equal_weight.to_dict(),
            "momentum": self.momentum.to_dict(),
            "gate": self.gate.to_dict(),
            "stable_gate": self.stable_gate.to_dict() if self.stable_gate else None,
            "windows": [w.to_dict() for w in self.windows],
            "equity_curve": self.equity_curve,
            "notes": self.notes,
        }

    @property
    def promote(self) -> bool:
        """True only if full-sample and multi-window stable gates pass."""
        if not self.gate.pass_:
            return False
        if self.stable_gate is not None:
            return self.stable_gate.pass_
        return True


def _metrics_from_equity(
    name: str,
    equity: pd.Series,
    *,
    traded_notional: float = 0.0,
    n_trades: int = 0,
) -> StrategyMetrics:
    eq = equity.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(eq) < 2:
        return StrategyMetrics(
            name=name,
            total_return=0.0,
            cagr=0.0,
            max_drawdown=0.0,
            sharpe=0.0,
            volatility=0.0,
            turnover=0.0,
            n_days=len(eq),
            final_equity=float(eq.iloc[-1]) if len(eq) else 0.0,
            n_trades=n_trades,
        )
    rets = eq.pct_change().dropna()
    total_return = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    n = len(rets)
    years = max(n / TRADING_DAYS_PER_YEAR, 1e-9)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1.0) if eq.iloc[0] > 0 else 0.0
    vol = float(rets.std() * np.sqrt(TRADING_DAYS_PER_YEAR)) if len(rets) else 0.0
    mean_r = float(rets.mean()) if len(rets) else 0.0
    sharpe = float(mean_r / rets.std() * np.sqrt(TRADING_DAYS_PER_YEAR)) if rets.std() > 1e-12 else 0.0
    peak = eq.cummax()
    dd = (eq / peak - 1.0).min()
    max_dd = float(abs(dd)) if dd < 0 else 0.0
    avg_equity = float(eq.mean()) if eq.mean() else 1.0
    turnover = float(traded_notional / (avg_equity * max(n, 1)))
    return StrategyMetrics(
        name=name,
        total_return=total_return,
        cagr=cagr,
        max_drawdown=max_dd,
        sharpe=sharpe,
        volatility=vol,
        turnover=turnover,
        n_days=int(n),
        final_equity=float(eq.iloc[-1]),
        n_trades=n_trades,
    )


def evaluate_gate(
    signal: StrategyMetrics,
    equal_weight: StrategyMetrics,
    momentum: StrategyMetrics,
    *,
    max_dd_limit: float = 0.35,
    min_sharpe: float = 0.35,
    min_edge: float = 0.0,
    require_both_baselines: bool = False,
) -> GateResult:
    """Promotion gate: beat baselines on return with risk controls.

    Stricter defaults than v1: min Sharpe 0.35; optional require both baselines.
    """
    reasons: list[str] = []
    edge_eq = signal.total_return - equal_weight.total_return
    edge_mom = signal.total_return - momentum.total_return
    beat_eq = edge_eq > min_edge + 1e-6
    beat_mom = edge_mom > min_edge + 1e-6
    dd_ok = signal.max_drawdown <= max_dd_limit + 1e-9
    sharpe_ok = signal.sharpe >= min_sharpe - 1e-9

    if beat_eq:
        reasons.append(f"beats equal-weight (edge {edge_eq:+.2%})")
    else:
        reasons.append(f"does not beat equal-weight (edge {edge_eq:+.2%})")
    if beat_mom:
        reasons.append(f"beats momentum-top (edge {edge_mom:+.2%})")
    else:
        reasons.append(f"does not beat momentum-top (edge {edge_mom:+.2%})")
    if dd_ok:
        reasons.append(f"maxDD {signal.max_drawdown:.2%} <= limit {max_dd_limit:.0%}")
    else:
        reasons.append(f"maxDD {signal.max_drawdown:.2%} exceeds limit {max_dd_limit:.0%}")
    if sharpe_ok:
        reasons.append(f"sharpe {signal.sharpe:.2f} >= {min_sharpe:.2f}")
    else:
        reasons.append(f"sharpe {signal.sharpe:.2f} < {min_sharpe:.2f}")

    if require_both_baselines:
        beat_ok = beat_eq and beat_mom
    else:
        beat_ok = beat_eq or beat_mom
    pass_ = beat_ok and dd_ok and sharpe_ok
    if pass_:
        reasons.insert(0, "PROMOTION_GATE_PASS")
    else:
        reasons.insert(0, "PROMOTION_GATE_FAIL")
    return GateResult(
        pass_=pass_,
        reasons=reasons,
        beat_equal_weight=beat_eq,
        beat_momentum=beat_mom,
        drawdown_ok=dd_ok,
        sharpe_ok=sharpe_ok,
    )


def _align_price_panels(
    frames: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Return close/open panels (dates x symbols), inner-joined on dates."""
    closes: dict[str, pd.Series] = {}
    opens: dict[str, pd.Series] = {}
    for sym, df in frames.items():
        if df is None or df.empty or "Close" not in df.columns:
            continue
        c = df["Close"].astype(float).copy()
        c.index = pd.to_datetime(c.index)
        o = df["Open"].astype(float).copy() if "Open" in df.columns else c.copy()
        o.index = pd.to_datetime(o.index)
        closes[sym] = c
        opens[sym] = o
    if len(closes) < 2:
        raise ValueError("need at least 2 symbols with OHLCV for backtest")
    close_px = pd.DataFrame(closes).sort_index().dropna(how="all")
    open_px = pd.DataFrame(opens).reindex(close_px.index).sort_index()
    # drop dates with too few prints
    mask = close_px.notna().sum(axis=1) >= max(2, len(closes) // 3)
    close_px = close_px.loc[mask]
    open_px = open_px.loc[close_px.index]
    return close_px, open_px, list(close_px.columns)


def _positions_from_qty(
    qty: dict[str, float],
    prices: dict[str, float],
) -> list[Position]:
    out: list[Position] = []
    for sym, q in qty.items():
        if q <= 1e-12:
            continue
        px = float(prices.get(sym) or 0.0)
        mv = q * px
        out.append(
            Position(
                symbol=sym,
                qty=float(q),
                market_value=mv,
                current_price=px,
                avg_entry_price=px,
                unrealized_pl=0.0,
                side="long",
            )
        )
    return out


def _account(equity: float, cash: float) -> AccountSnapshot:
    return AccountSnapshot(
        equity=equity,
        cash=cash,
        buying_power=cash,
        portfolio_value=equity,
        status="ACTIVE",
        currency="USD",
        pattern_day_trader=False,
        trading_blocked=False,
        account_blocked=False,
    )


def apply_slippage(price: float, *, side: str, slip_bps: float) -> float:
    """Adverse mid→fill move: buys pay up, sells receive down."""
    if price <= 0:
        return price
    slip = max(0.0, float(slip_bps)) / 10_000.0
    side_l = side.lower()
    if side_l == "buy":
        return price * (1.0 + slip)
    if side_l == "sell":
        return price * (1.0 - slip)
    return price


def _apply_intents(
    *,
    qty: dict[str, float],
    cash: float,
    intents: list,
    fill_prices: dict[str, float],
    cost_bps: float,
    slip_bps: float = 0.0,
) -> tuple[dict[str, float], float, float, int]:
    """Execute intents at slipped fill prices + fees.

    Returns:
        qty, cash, traded_notional (at slipped prices), n_trades
    """
    traded = 0.0
    n_trades = 0
    fee_rate = cost_bps / 10_000.0
    qty = dict(qty)

    # sells first
    for intent in intents:
        if intent.side != "sell":
            continue
        sym = intent.symbol.upper()
        mid = fill_prices.get(sym)
        if mid is None or mid <= 0:
            continue
        px = apply_slippage(mid, side="sell", slip_bps=slip_bps)
        q = abs(float(intent.qty or 0.0))
        held = qty.get(sym, 0.0)
        q = min(q, held)
        if q <= 1e-12:
            continue
        notional = q * px
        fee = notional * fee_rate
        cash += notional - fee
        qty[sym] = held - q
        if qty[sym] <= 1e-12:
            qty.pop(sym, None)
        traded += notional
        n_trades += 1

    for intent in intents:
        if intent.side != "buy":
            continue
        sym = intent.symbol.upper()
        mid = fill_prices.get(sym)
        if mid is None or mid <= 0:
            continue
        px = apply_slippage(mid, side="buy", slip_bps=slip_bps)
        if intent.qty is not None and intent.qty > 0:
            q = float(intent.qty)
            notional = q * px
        elif intent.notional is not None and intent.notional > 0:
            # notional is budget at mid; reprice shares at slipped px
            budget = float(intent.notional)
            q = budget / px
            notional = q * px
        else:
            continue
        fee = notional * fee_rate
        total = notional + fee
        if total > cash + 1e-6:
            if cash <= fee + 1e-6:
                continue
            # scale quantity to available cash at slipped price + fee
            q = cash / (px * (1.0 + fee_rate)) if fee_rate > 0 else cash / px
            notional = q * px
            fee = notional * fee_rate
            total = notional + fee
        if q <= 1e-12 or total > cash + 1e-6:
            continue
        cash -= total
        qty[sym] = qty.get(sym, 0.0) + q
        traded += notional
        n_trades += 1

    return qty, cash, traded, n_trades


def _mark_equity(qty: dict[str, float], cash: float, prices: dict[str, float]) -> float:
    mv = 0.0
    for sym, q in qty.items():
        px = prices.get(sym)
        if px is not None and q > 0:
            mv += q * px
    return cash + mv


def _build_history_frames(
    frames: dict[str, pd.DataFrame],
    symbols: list[str],
    asof: pd.Timestamp,
) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = frames.get(sym)
        if df is None or df.empty:
            continue
        d = df.copy()
        d.index = pd.to_datetime(d.index)
        hist = d.loc[d.index <= asof]
        if len(hist) >= 60:
            out[sym] = hist
    return out


def _train_booster(
    frames: dict[str, pd.DataFrame],
    *,
    horizon: int,
    feature_names: list[str],
    num_boost_round: int,
    params: dict[str, Any],
) -> lgb.Booster | None:
    parts: list[pd.DataFrame] = []
    for sym, ohlcv in frames.items():
        try:
            lab = build_labeled_frame(ohlcv, horizon=horizon)
        except ValueError:
            continue
        lab = lab.copy()
        lab["symbol"] = sym
        parts.append(lab)
    if not parts:
        return None
    panel = pd.concat(parts, axis=0).sort_index()
    panel = add_cross_section_features(panel, relative_label=True)
    for col in feature_names:
        if col not in panel.columns:
            panel[col] = 0.5 if col.startswith("cs_") else 0.0
    # drop last horizon days incomplete labels already dropped
    x = panel.loc[:, feature_names]
    y = panel["label"].astype(int)
    if len(x) < 50:
        return None
    dtrain = lgb.Dataset(x, label=y, feature_name=feature_names)
    return lgb.train(
        params,
        dtrain,
        num_boost_round=num_boost_round,
        callbacks=[lgb.log_evaluation(period=0)],
    )


def _score_day(
    booster: lgb.Booster,
    frames_hist: dict[str, pd.DataFrame],
    *,
    feature_names: list[str],
    buy_threshold: float,
    sell_threshold: float,
    w_model: float = 0.40,
    w_mom: float = 0.60,
) -> list[SignalRow]:
    parts: list[pd.DataFrame] = []
    for sym, ohlcv in frames_hist.items():
        try:
            feats = build_features(ohlcv)
            if feats.empty:
                continue
            row = feats.iloc[[-1]].copy()
            row["symbol"] = sym
            row["fwd_ret"] = 0.0
            row["label"] = 0
            parts.append(row)
        except ValueError:
            continue
    if not parts:
        return []
    panel = pd.concat(parts, axis=0)
    as_of = panel.index.max()
    panel.index = pd.DatetimeIndex([as_of] * len(panel))
    panel = add_cross_section_features(panel, relative_label=False)
    for col in feature_names:
        if col not in panel.columns:
            panel[col] = 0.5 if col.startswith("cs_") else 0.0
    x = panel.loc[:, feature_names]
    proba = np.asarray(booster.predict(x), dtype=float)
    as_of_s = str(pd.Timestamp(as_of).date())
    rows: list[SignalRow] = []
    tw = float(w_model) + float(w_mom)
    if tw <= 0:
        w_model, w_mom, tw = 0.4, 0.6, 1.0
    w_model, w_mom = float(w_model) / tw, float(w_mom) / tw
    for i, (_, prow) in enumerate(panel.iterrows()):
        p_model = float(proba[i])
        mom_r = float(prow["cs_rank_ret_20"]) if "cs_rank_ret_20" in prow.index else 0.5
        if math.isnan(mom_r):  # NaN
            mom_r = 0.5
        p = float(min(1.0, max(0.0, w_model * p_model + w_mom * mom_r)))
        rows.append(
            SignalRow(
                symbol=str(prow["symbol"]),
                proba=p,
                side=side_from_proba(p, buy_threshold=buy_threshold, sell_threshold=sell_threshold),
                as_of=as_of_s,
            )
        )
    rows.sort(key=lambda r: r.proba, reverse=True)
    return rows


def _equal_weight_curve(
    close_px: pd.DataFrame,
    *,
    initial_cash: float,
    start_i: int,
    cost_bps: float = 0.0,
    slip_bps: float = 0.0,
) -> pd.Series:
    """Buy equal weight at start_i, hold to end (same entry friction as signal)."""
    dates = close_px.index
    row0 = close_px.iloc[start_i]
    valid = row0.dropna()
    if valid.empty:
        return pd.Series(dtype=float)
    fee_rate = cost_bps / 10_000.0
    # entry: pay adverse slip + fee once (buy-and-hold)
    n = len(valid)
    budget = initial_cash / n
    shares: dict[str, float] = {}
    cash_left = initial_cash
    for sym, px in valid.items():
        mid = float(px)
        if mid <= 0:
            continue
        fill = apply_slippage(mid, side="buy", slip_bps=slip_bps)
        notional = budget / (1.0 + fee_rate)
        fee = notional * fee_rate
        spend = notional + fee
        if spend > cash_left + 1e-9:
            continue
        shares[sym] = notional / fill
        cash_left -= spend
    eq = []
    idx = []
    for i in range(start_i, len(dates)):
        px = close_px.iloc[i]
        total = cash_left
        for sym, q in shares.items():
            p = px.get(sym)
            if pd.notna(p):
                total += q * float(p)
        eq.append(total)
        idx.append(dates[i])
    return pd.Series(eq, index=pd.DatetimeIndex(idx), dtype=float)


def _momentum_top_curve(
    close_px: pd.DataFrame,
    *,
    initial_cash: float,
    start_i: int,
    top_n: int,
    rebalance_every: int,
    cost_bps: float,
    slip_bps: float = 0.0,
) -> tuple[pd.Series, float, int]:
    """Rebalance every N days into top-N by 20d return (same friction as signal)."""
    dates = close_px.index
    cash = initial_cash
    qty: dict[str, float] = {}
    traded_total = 0.0
    n_trades = 0
    fee_rate = cost_bps / 10_000.0
    eq_vals: list[float] = []
    eq_idx: list[Any] = []

    for i in range(start_i, len(dates)):
        px_row = close_px.iloc[i]
        prices = {s: float(px_row[s]) for s in close_px.columns if pd.notna(px_row[s])}
        if (i - start_i) % max(rebalance_every, 1) == 0 and i >= 21:
            past = close_px.iloc[max(0, i - 20) : i + 1]
            rets = past.pct_change(20).iloc[-1].dropna().sort_values(ascending=False)
            picks = list(rets.head(top_n).index)
            # liquidate all at slipped sell
            for sym, q in list(qty.items()):
                mid = prices.get(sym)
                if mid and q > 0:
                    fill = apply_slippage(mid, side="sell", slip_bps=slip_bps)
                    notional = q * fill
                    cash += notional * (1.0 - fee_rate)
                    traded_total += notional
                    n_trades += 1
            qty.clear()
            if picks:
                per = cash / len(picks)
                for sym in picks:
                    mid = prices.get(sym)
                    if not mid or mid <= 0 or per <= 0:
                        continue
                    fill = apply_slippage(mid, side="buy", slip_bps=slip_bps)
                    notional = per / (1.0 + fee_rate)
                    fee = notional * fee_rate
                    if notional + fee > cash:
                        continue
                    cash -= notional + fee
                    qty[sym] = notional / fill
                    traded_total += notional
                    n_trades += 1
        eq_vals.append(_mark_equity(qty, cash, prices))
        eq_idx.append(dates[i])
    return pd.Series(eq_vals, index=pd.DatetimeIndex(eq_idx), dtype=float), traded_total, n_trades


def run_portfolio_backtest(
    frames: dict[str, pd.DataFrame],
    cfg: TickersConfig,
    *,
    risk: RiskLimits | None = None,
    bt: BacktestConfig | None = None,
) -> BacktestReport:
    """Walk-forward portfolio backtest using production plan rules."""
    risk = risk or default_risk_limits(cfg)
    bt = bt or BacktestConfig()
    risk.validate()
    _ = sleeve_map(cfg)  # validate sleeves early

    close_px, open_px, symbols = _align_price_panels(frames)
    # restrict to configured universe symbols present in data
    uni = [s for s in cfg.symbols() if s in symbols]
    if len(uni) < 2:
        raise ValueError("fewer than 2 universe symbols have price history")
    close_px = close_px[uni]
    open_px = open_px[uni]
    frames = {s: frames[s] for s in uni if s in frames}

    feature_names = model_feature_names(include_cs=True)
    params = dict(DEFAULT_PARAMS)
    dates = list(close_px.index)
    n = len(dates)
    start_i = max(bt.train_days, bt.min_history)
    if n < start_i + 30:
        raise ValueError(f"not enough history: {n} days, need > {start_i + 30}")

    cash = float(bt.initial_cash)
    qty: dict[str, float] = {}
    booster: lgb.Booster | None = None
    last_train_i = -10_000
    traded_total = 0.0
    n_trades = 0
    eq_vals: list[float] = []
    eq_idx: list[Any] = []
    notes: list[str] = [
        f"fill={bt.fill}",
        (
            f"train_days={bt.train_days} retrain_every={bt.retrain_every} "
            f"rebalance_every={bt.rebalance_every} "
            f"cost_bps={bt.cost_bps} slip_bps={bt.slip_bps}"
        ),
        "signal decisions at close t; fills next open/close with adverse slippage + fees",
        f"plan_mode={risk.plan_mode} top_n={risk.top_n}; relative LightGBM scores",
    ]

    pending_intents: list = []
    pending_fill_i: int | None = None
    last_rebalance_i = -10_000

    for i in range(start_i, n):
        asof = pd.Timestamp(dates[i])
        # 1) fill pending from prior decision
        if pending_intents and pending_fill_i is not None and i == pending_fill_i:
            if bt.fill == "next_open":
                row = open_px.iloc[i]
            else:
                row = close_px.iloc[i]
            fill_prices = {s: float(row[s]) for s in uni if pd.notna(row[s])}
            qty, cash, traded, nt = _apply_intents(
                qty=qty,
                cash=cash,
                intents=pending_intents,
                fill_prices=fill_prices,
                cost_bps=bt.cost_bps,
                slip_bps=bt.slip_bps,
            )
            traded_total += traded
            n_trades += nt
            pending_intents = []
            pending_fill_i = None

        # 2) mark at close
        close_row = close_px.iloc[i]
        close_prices = {s: float(close_row[s]) for s in uni if pd.notna(close_row[s])}
        equity = _mark_equity(qty, cash, close_prices)
        eq_vals.append(equity)
        eq_idx.append(asof)

        # 3) retrain if needed
        if booster is None or (i - last_train_i) >= bt.retrain_every:
            hist = _build_history_frames(frames, uni, asof)
            booster = _train_booster(
                hist,
                horizon=bt.horizon,
                feature_names=feature_names,
                num_boost_round=bt.num_boost_round,
                params=params,
            )
            last_train_i = i
            if booster is None:
                notes.append(f"train failed at {asof.date()}")
                continue

        # 4) score + plan only on rebalance schedule (cuts churn vs daily)
        if i >= n - 1:
            continue
        if (i - last_rebalance_i) < bt.rebalance_every and last_rebalance_i > 0:
            continue
        hist = _build_history_frames(frames, uni, asof)
        # Regime adjusts blend + book size (no lookahead: panel through asof only)
        if bt.use_regime:
            reg = detect_regime_from_close_panel(
                close_px,
                i,
                base_top_n=risk.top_n,
                base_min_cash=risk.min_cash_pct,
                base_max_pos=risk.max_position_pct,
            )
            w_model, w_mom = reg.w_model, reg.w_mom
            day_risk = RiskLimits(
                max_position_pct=reg.max_position_pct,
                growth_target_pct=risk.growth_target_pct,
                defensive_target_pct=risk.defensive_target_pct,
                max_new_positions=risk.max_new_positions,
                min_notional=risk.min_notional,
                min_cash_pct=reg.min_cash_pct,
                buy_threshold=bt.buy_threshold,
                sell_threshold=bt.sell_threshold,
                plan_mode=risk.plan_mode,
                top_n=reg.top_n,
                rebalance_band_pct=risk.rebalance_band_pct,
                paper_only=risk.paper_only,
            )
        else:
            w_model, w_mom = 0.40, 0.60
            day_risk = risk
        try:
            signals = _score_day(
                booster,
                hist,
                feature_names=feature_names,
                buy_threshold=bt.buy_threshold,
                sell_threshold=bt.sell_threshold,
                w_model=w_model,
                w_mom=w_mom,
            )
        except (ValueError, KeyError, TypeError, RuntimeError) as exc:
            log.warning("score day failed %s: %s", asof.date(), exc)
            continue
        if not signals:
            continue
        positions = _positions_from_qty(qty, close_prices)
        acct = _account(equity, cash)
        plan = build_trade_plan(
            signals=signals,
            account=acct,
            positions=positions,
            cfg=cfg,
            risk=day_risk,
            prices=close_prices,
        )
        last_rebalance_i = i
        if plan.intents:
            pending_intents = list(plan.intents)
            pending_fill_i = i + 1

    signal_eq = pd.Series(eq_vals, index=pd.DatetimeIndex(eq_idx), dtype=float)
    if signal_eq.empty:
        raise RuntimeError("backtest produced empty equity curve")

    # Same cost+slip as signal so promote is a fair horse race
    eq_curve = _equal_weight_curve(
        close_px,
        initial_cash=bt.initial_cash,
        start_i=start_i,
        cost_bps=bt.cost_bps,
        slip_bps=bt.slip_bps,
    )
    mom_curve, mom_traded, mom_trades = _momentum_top_curve(
        close_px,
        initial_cash=bt.initial_cash,
        start_i=start_i,
        top_n=bt.momentum_top_n,
        rebalance_every=bt.retrain_every,
        cost_bps=bt.cost_bps,
        slip_bps=bt.slip_bps,
    )

    # align lengths for fair comparison
    common = signal_eq.index.intersection(eq_curve.index).intersection(mom_curve.index)
    signal_eq = signal_eq.reindex(common).dropna()
    eq_curve = eq_curve.reindex(common).dropna()
    mom_curve = mom_curve.reindex(common).dropna()
    common = signal_eq.index.intersection(eq_curve.index).intersection(mom_curve.index)
    signal_eq = signal_eq.loc[common]
    eq_curve = eq_curve.loc[common]
    mom_curve = mom_curve.loc[common]

    sig_m = _metrics_from_equity("signal_plan", signal_eq, traded_notional=traded_total, n_trades=n_trades)
    eq_m = _metrics_from_equity("equal_weight", eq_curve)
    mom_m = _metrics_from_equity("momentum_top", mom_curve, traded_notional=mom_traded, n_trades=mom_trades)
    gate = evaluate_gate(
        sig_m,
        eq_m,
        mom_m,
        min_sharpe=bt.min_sharpe,
        require_both_baselines=bt.require_both_baselines,
    )

    # Cost + slip stress: same path with harsher frictions — must still beat ≥1 baseline
    stress_cost = max(bt.cost_stress_bps, bt.cost_bps)
    stress_slip = max(bt.slip_stress_bps, bt.slip_bps)
    if (stress_cost > bt.cost_bps + 1e-9 or stress_slip > bt.slip_bps + 1e-9) and gate.pass_:
        stress_bt = BacktestConfig(
            initial_cash=bt.initial_cash,
            horizon=bt.horizon,
            train_days=bt.train_days,
            retrain_every=bt.retrain_every,
            rebalance_every=bt.rebalance_every,
            num_boost_round=bt.num_boost_round,
            cost_bps=stress_cost,
            slip_bps=stress_slip,
            buy_threshold=bt.buy_threshold,
            sell_threshold=bt.sell_threshold,
            fill=bt.fill,
            min_history=bt.min_history,
            momentum_top_n=bt.momentum_top_n,
            n_windows=1,
            use_regime=bt.use_regime,
            cost_stress_bps=stress_cost,
            slip_stress_bps=stress_slip,
            min_sharpe=bt.min_sharpe,
            require_both_baselines=bt.require_both_baselines,
        )
        try:
            stress = _run_single_window(frames, cfg, risk=risk, bt=stress_bt, skip_stability=True)
            stress_gate = evaluate_gate(
                stress.signal,
                stress.equal_weight,
                stress.momentum,
                min_sharpe=0.0,
                require_both_baselines=False,
            )
            if not (stress_gate.beat_equal_weight or stress_gate.beat_momentum):
                gate = GateResult(
                    pass_=False,
                    reasons=[
                        "PROMOTION_GATE_FAIL",
                        (
                            f"friction stress cost={stress_cost:.0f}bps "
                            f"slip={stress_slip:.0f}bps: loses both baselines"
                        ),
                        *gate.reasons[1:],
                    ],
                    beat_equal_weight=gate.beat_equal_weight,
                    beat_momentum=gate.beat_momentum,
                    drawdown_ok=gate.drawdown_ok,
                    sharpe_ok=gate.sharpe_ok,
                )
                notes.append(
                    f"friction_stress cost={stress_cost:.0f} slip={stress_slip:.0f} failed baselines"
                )
            else:
                notes.append(
                    f"friction_stress cost={stress_cost:.0f} slip={stress_slip:.0f} ok "
                    f"(sig={stress.signal.total_return:+.1%})"
                )
        except (ValueError, RuntimeError) as exc:
            notes.append(f"friction stress skipped: {exc}")

    curve_out = [
        {
            "date": str(pd.Timestamp(d).date()),
            "signal": float(signal_eq.loc[d]),
            "equal_weight": float(eq_curve.loc[d]),
            "momentum": float(mom_curve.loc[d]),
        }
        for d in signal_eq.index
    ]

    report = BacktestReport(
        ts=datetime.now(UTC).isoformat(),
        config={
            "initial_cash": bt.initial_cash,
            "horizon": bt.horizon,
            "train_days": bt.train_days,
            "retrain_every": bt.retrain_every,
            "rebalance_every": bt.rebalance_every,
            "num_boost_round": bt.num_boost_round,
            "cost_bps": bt.cost_bps,
            "slip_bps": bt.slip_bps,
            "cost_stress_bps": bt.cost_stress_bps,
            "slip_stress_bps": bt.slip_stress_bps,
            "buy_threshold": bt.buy_threshold,
            "sell_threshold": bt.sell_threshold,
            "fill": bt.fill,
            "momentum_top_n": bt.momentum_top_n,
            "plan_mode": risk.plan_mode,
            "top_n": risk.top_n,
            "use_regime": bt.use_regime,
            "n_windows": bt.n_windows,
            "min_window_pass_frac": bt.min_window_pass_frac,
            "min_sharpe": bt.min_sharpe,
            "n_symbols": len(uni),
            "start": str(pd.Timestamp(common[0]).date()) if len(common) else "",
            "end": str(pd.Timestamp(common[-1]).date()) if len(common) else "",
        },
        signal=sig_m,
        equal_weight=eq_m,
        momentum=mom_m,
        gate=gate,
        equity_curve=curve_out,
        notes=notes,
    )

    if bt.n_windows >= 2 and not getattr(bt, "_skip_stability", False):
        report.windows, report.stable_gate = _multi_window_stability(
            frames, cfg, risk=risk, bt=bt, full_gate=gate
        )
        if report.stable_gate and not report.stable_gate.pass_:
            # overall promote fails if unstable even if full sample passed
            pass
    return report


def _run_single_window(
    frames: dict[str, pd.DataFrame],
    cfg: TickersConfig,
    *,
    risk: RiskLimits,
    bt: BacktestConfig,
    skip_stability: bool = True,
) -> BacktestReport:
    """Internal: one full run without nested multi-window or cost stress."""
    _ = skip_stability
    bt2 = BacktestConfig(
        initial_cash=bt.initial_cash,
        horizon=bt.horizon,
        train_days=bt.train_days,
        retrain_every=bt.retrain_every,
        rebalance_every=bt.rebalance_every,
        num_boost_round=bt.num_boost_round,
        cost_bps=bt.cost_bps,
        slip_bps=bt.slip_bps,
        buy_threshold=bt.buy_threshold,
        sell_threshold=bt.sell_threshold,
        fill=bt.fill,
        min_history=bt.min_history,
        momentum_top_n=bt.momentum_top_n,
        n_windows=1,
        use_regime=bt.use_regime,
        cost_stress_bps=bt.cost_bps,
        slip_stress_bps=bt.slip_bps,
        min_sharpe=bt.min_sharpe,
        require_both_baselines=bt.require_both_baselines,
    )
    return run_portfolio_backtest(frames, cfg, risk=risk, bt=bt2)


def _slice_frames(
    frames: dict[str, pd.DataFrame],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for sym, df in frames.items():
        d = df.copy()
        d.index = pd.to_datetime(d.index)
        sl = d.loc[(d.index >= start) & (d.index <= end)]
        if len(sl) >= 80:
            out[sym] = sl
    return out


def _multi_window_stability(
    frames: dict[str, pd.DataFrame],
    cfg: TickersConfig,
    *,
    risk: RiskLimits,
    bt: BacktestConfig,
    full_gate: GateResult,
) -> tuple[list[WindowResult], GateResult]:
    """Sequential non-overlapping windows; require most to PASS gate."""
    close_px, _open_px, symbols = _align_price_panels(frames)
    uni = [s for s in cfg.symbols() if s in symbols]
    close_px = close_px[uni]
    dates = close_px.index
    n = len(dates)
    n_win = max(2, int(bt.n_windows))
    # Overlapping expanding windows ending at sample end (works on ~1y history)
    # W0: first 60% · W1: middle 60% · W2: last 60% (approx)
    min_len = max(100, bt.train_days // 2 + 50)
    if n < min_len + 30:
        return [], GateResult(
            pass_=full_gate.pass_,
            reasons=["stable: insufficient history for multi-window; using full sample only"],
            beat_equal_weight=full_gate.beat_equal_weight,
            beat_momentum=full_gate.beat_momentum,
            drawdown_ok=full_gate.drawdown_ok,
            sharpe_ok=full_gate.sharpe_ok,
        )

    win_len = max(min_len, int(n * 0.55))
    if win_len >= n:
        win_len = n - 10
    step = max(1, (n - win_len) // max(n_win - 1, 1))
    windows: list[WindowResult] = []
    for w in range(n_win):
        i0 = min(w * step, n - win_len)
        i1 = i0 + win_len
        if i1 > n:
            i1 = n
            i0 = max(0, i1 - win_len)
        start, end = pd.Timestamp(dates[i0]), pd.Timestamp(dates[i1 - 1])
        sliced = _slice_frames(frames, start, end)
        if len(sliced) < 2:
            continue
        try:
            sub_train = min(bt.train_days, max(50, (i1 - i0) // 3))
            sub_bt = BacktestConfig(
                initial_cash=bt.initial_cash,
                horizon=bt.horizon,
                train_days=sub_train,
                retrain_every=bt.retrain_every,
                rebalance_every=bt.rebalance_every,
                num_boost_round=bt.num_boost_round,
                cost_bps=bt.cost_bps,
                slip_bps=bt.slip_bps,
                buy_threshold=bt.buy_threshold,
                sell_threshold=bt.sell_threshold,
                fill=bt.fill,
                min_history=min(bt.min_history, 50),
                momentum_top_n=bt.momentum_top_n,
                n_windows=1,
                use_regime=bt.use_regime,
                cost_stress_bps=bt.cost_bps,
                slip_stress_bps=bt.slip_bps,
                min_sharpe=max(0.0, bt.min_sharpe - 0.1),
                require_both_baselines=False,
            )
            rep = run_portfolio_backtest(sliced, cfg, risk=risk, bt=sub_bt)
            windows.append(
                WindowResult(
                    label=f"W{w}",
                    start=str(start.date()),
                    end=str(end.date()),
                    signal_return=rep.signal.total_return,
                    eq_return=rep.equal_weight.total_return,
                    mom_return=rep.momentum.total_return,
                    max_drawdown=rep.signal.max_drawdown,
                    sharpe=rep.signal.sharpe,
                    gate_pass=rep.gate.pass_,
                )
            )
        except (ValueError, RuntimeError) as exc:
            log.warning("window %s failed: %s", w, exc)
            windows.append(
                WindowResult(
                    label=f"W{w}",
                    start=str(start.date()),
                    end=str(end.date()),
                    signal_return=float("nan"),
                    eq_return=float("nan"),
                    mom_return=float("nan"),
                    max_drawdown=float("nan"),
                    sharpe=float("nan"),
                    gate_pass=False,
                )
            )

    if not windows:
        return [], GateResult(
            pass_=False,
            reasons=["PROMOTION_GATE_FAIL", "stable: no windows completed"],
            beat_equal_weight=False,
            beat_momentum=False,
            drawdown_ok=False,
            sharpe_ok=False,
        )

    n_pass = sum(1 for w in windows if w.gate_pass)
    frac = n_pass / len(windows)
    need = bt.min_window_pass_frac
    reasons = [
        f"windows_pass={n_pass}/{len(windows)} ({frac:.0%}) need>={need:.0%}",
    ]
    if full_gate.pass_:
        reasons.append("full_sample_gate=PASS")
    else:
        reasons.append("full_sample_gate=FAIL")
    stable_ok = frac + 1e-9 >= need and full_gate.pass_
    if stable_ok:
        reasons.insert(0, "STABLE_GATE_PASS")
    else:
        reasons.insert(0, "STABLE_GATE_FAIL")
    return windows, GateResult(
        pass_=stable_ok,
        reasons=reasons,
        beat_equal_weight=full_gate.beat_equal_weight,
        beat_momentum=full_gate.beat_momentum,
        drawdown_ok=full_gate.drawdown_ok,
        sharpe_ok=full_gate.sharpe_ok,
    )


def save_backtest_report(report: BacktestReport, path: Path | str | None = None) -> Path:
    """Write backtest JSON under data/learning/."""
    if path is None:
        out_dir = project_root() / "data" / "learning"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "backtest_latest.json"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    stamped = path.with_name(
        f"backtest_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    try:
        stamped.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    except OSError as exc:
        log.warning("stamped backtest write skipped: %s", exc)
    return path
