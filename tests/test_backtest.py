"""Portfolio backtest unit tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from neotrade.broker.plan import OrderIntent
from neotrade.broker.risk import RiskLimits
from neotrade.config.models import RiskSettings, Ticker, TickersConfig
from neotrade.signals.backtest import (
    BacktestConfig,
    StrategyMetrics,
    _apply_intents,
    apply_slippage,
    evaluate_gate,
    run_portfolio_backtest,
)


def _synth(n: int = 200, seed: int = 0, drift: float = 0.0004) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-01-02", periods=n)
    shock = rng.normal(0, 0.012, size=n)
    mom = np.zeros(n)
    for i in range(1, n):
        mom[i] = 0.2 * mom[i - 1] + shock[i] + drift
    close = 50 * np.cumprod(1 + mom)
    open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.001, size=n))
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    volume = rng.integers(500_000, 2_000_000, size=n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


def _cfg(symbols: list[str]) -> TickersConfig:
    tickers = []
    for i, s in enumerate(symbols):
        sleeve = "growth" if i % 2 == 0 else "defensive"
        tickers.append(Ticker(symbol=s, sleeve=sleeve))  # type: ignore[arg-type]
    return TickersConfig(
        tickers=tickers,
        risk=RiskSettings(
            max_position_pct=0.15,
            growth_target_pct=0.6,
            defensive_target_pct=0.4,
            max_new_positions=4,
            min_notional=50.0,
        ),
    )


def test_evaluate_gate_pass_and_fail():
    good = StrategyMetrics(
        name="s",
        total_return=0.2,
        cagr=0.15,
        max_drawdown=0.1,
        sharpe=0.8,
        volatility=0.2,
        turnover=1.0,
        n_days=100,
        final_equity=120_000,
    )
    eq = StrategyMetrics(
        name="e",
        total_return=0.05,
        cagr=0.04,
        max_drawdown=0.1,
        sharpe=0.3,
        volatility=0.15,
        turnover=0.0,
        n_days=100,
        final_equity=105_000,
    )
    mom = StrategyMetrics(
        name="m",
        total_return=0.08,
        cagr=0.06,
        max_drawdown=0.12,
        sharpe=0.4,
        volatility=0.18,
        turnover=2.0,
        n_days=100,
        final_equity=108_000,
    )
    g = evaluate_gate(good, eq, mom, min_sharpe=0.35)
    assert g.pass_ is True
    assert g.beat_equal_weight is True

    bad = StrategyMetrics(
        name="s",
        total_return=-0.1,
        cagr=-0.1,
        max_drawdown=0.5,
        sharpe=-0.5,
        volatility=0.3,
        turnover=5.0,
        n_days=100,
        final_equity=90_000,
    )
    g2 = evaluate_gate(bad, eq, mom, max_dd_limit=0.35, min_sharpe=0.35)
    assert g2.pass_ is False
    assert g2.drawdown_ok is False


def test_evaluate_gate_require_both():
    sig = StrategyMetrics(
        name="s",
        total_return=0.10,
        cagr=0.1,
        max_drawdown=0.1,
        sharpe=1.0,
        volatility=0.2,
        turnover=1.0,
        n_days=50,
        final_equity=110_000,
    )
    eq = StrategyMetrics(
        name="e",
        total_return=0.05,
        cagr=0.05,
        max_drawdown=0.1,
        sharpe=0.5,
        volatility=0.15,
        turnover=0.0,
        n_days=50,
        final_equity=105_000,
    )
    mom = StrategyMetrics(
        name="m",
        total_return=0.20,
        cagr=0.2,
        max_drawdown=0.1,
        sharpe=0.8,
        volatility=0.2,
        turnover=1.0,
        n_days=50,
        final_equity=120_000,
    )
    g = evaluate_gate(sig, eq, mom, require_both_baselines=True, min_sharpe=0.35)
    assert g.pass_ is False  # beats eq but not mom
    g2 = evaluate_gate(sig, eq, mom, require_both_baselines=False, min_sharpe=0.35)
    assert g2.pass_ is True


def test_run_portfolio_backtest_smoke():
    symbols = ["AAA", "BBB", "CCC", "DDD"]
    frames = {s: _synth(n=220, seed=i + 1) for i, s in enumerate(symbols)}
    cfg = _cfg(symbols)
    bt = BacktestConfig(
        initial_cash=100_000,
        train_days=100,
        retrain_every=40,
        rebalance_every=15,
        num_boost_round=30,
        cost_bps=5.0,
        fill="next_open",
    )
    report = run_portfolio_backtest(frames, cfg, risk=default_risk_limits_safe(cfg), bt=bt)
    assert report.signal.n_days > 20
    assert report.signal.final_equity > 0
    # equity_curve points; n_days is return periods (len-1)
    assert len(report.equity_curve) >= report.signal.n_days
    assert abs(len(report.equity_curve) - report.signal.n_days) <= 1
    assert report.gate.reasons
    d = report.to_dict()
    assert "gate" in d and "pass" in d["gate"]
    lines = report.summary_lines()
    assert any("signal:" in ln for ln in lines)


def test_summarize_oos_windows_and_summary_lines():
    from neotrade.signals.backtest import (
        WindowResult,
        format_oos_window_summary_lines,
        summarize_oos_windows,
    )

    wins = [
        WindowResult("W0", "a", "b", 0.08, 0.23, 0.05, 0.4, 0.47, False),
        WindowResult("W1", "c", "d", 0.42, 0.38, 0.39, 0.11, 1.92, True),
        WindowResult("W2", "e", "f", 0.78, 0.31, 0.44, 0.25, 1.93, True),
    ]
    stats = summarize_oos_windows(wins, min_sharpe=0.35)
    assert stats is not None
    assert stats["n"] == 3
    assert stats["n_pass"] == 2
    assert stats["sharpe_min"] == pytest.approx(0.47)
    assert stats["sharpe_max"] == pytest.approx(1.93)
    assert stats["worst_label"] == "W0"
    assert stats["worst_edge_vs_eq"] == pytest.approx(0.08 - 0.23)
    assert stats["pct_sharpe_above_min"] == pytest.approx(1.0)
    lines = format_oos_window_summary_lines(stats)
    assert any("oos_windows:" in ln for ln in lines)
    assert any("worst=W0" in ln for ln in lines)
    assert any("full-sample Sharpe" in ln for ln in lines)
    # dict path (from JSON)
    stats2 = summarize_oos_windows([w.to_dict() for w in wins])
    assert stats2 is not None
    assert stats2["n_pass"] == 2


def default_risk_limits_safe(cfg: TickersConfig) -> RiskLimits:
    from neotrade.broker.risk import default_risk_limits

    return default_risk_limits(cfg)


def test_backtest_requires_enough_history():
    frames = {"A": _synth(n=50, seed=1), "B": _synth(n=50, seed=2)}
    cfg = _cfg(["A", "B"])
    with pytest.raises(ValueError, match="not enough history"):
        run_portfolio_backtest(
            frames,
            cfg,
            bt=BacktestConfig(train_days=120, min_history=80),
        )


def test_apply_slippage_adverse():
    assert apply_slippage(100.0, side="buy", slip_bps=10) == pytest.approx(100.1)
    assert apply_slippage(100.0, side="sell", slip_bps=10) == pytest.approx(99.9)


def test_apply_intents_slippage_worsens_cash_vs_mid():
    buy = OrderIntent(
        symbol="AAA",
        side="buy",
        qty=10.0,
        notional=None,
        reason="t",
        sleeve="growth",
    )
    qty0: dict[str, float] = {}
    cash0 = 10_000.0
    # no slip
    q1, c1, t1, n1 = _apply_intents(
        qty=qty0,
        cash=cash0,
        intents=[buy],
        fill_prices={"AAA": 100.0},
        cost_bps=0.0,
        slip_bps=0.0,
    )
    # with slip
    q2, c2, t2, n2 = _apply_intents(
        qty={},
        cash=cash0,
        intents=[buy],
        fill_prices={"AAA": 100.0},
        cost_bps=0.0,
        slip_bps=50.0,  # 0.5%
    )
    assert n1 == n2 == 1
    assert q1["AAA"] == pytest.approx(10.0)
    assert q2["AAA"] == pytest.approx(10.0)
    assert c2 < c1  # paid more with slippage
    assert t2 > t1
