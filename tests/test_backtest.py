"""Portfolio backtest unit tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from neotrade.broker.risk import RiskLimits
from neotrade.config.models import RiskSettings, Ticker, TickersConfig
from neotrade.signals.backtest import (
    BacktestConfig,
    StrategyMetrics,
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
    g = evaluate_gate(good, eq, mom)
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
    g2 = evaluate_gate(bad, eq, mom, max_dd_limit=0.35)
    assert g2.pass_ is False
    assert g2.drawdown_ok is False


def test_run_portfolio_backtest_smoke():
    symbols = ["AAA", "BBB", "CCC", "DDD"]
    frames = {s: _synth(n=220, seed=i + 1) for i, s in enumerate(symbols)}
    cfg = _cfg(symbols)
    bt = BacktestConfig(
        initial_cash=100_000,
        train_days=100,
        retrain_every=40,
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
