from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from neotrade.agents.context import MarketContext, gather_market_context
from neotrade.agents.graph import build_advise_graph, run_advise
from neotrade.agents.llm import MockLLM
from neotrade.agents.recommend import parse_advice
from neotrade.broker.alpaca import AccountSnapshot
from neotrade.config.models import RiskSettings, Ticker, TickersConfig
from neotrade.signals.score import ScoreResult, SignalRow


def _synth_ohlcv(n: int = 150, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-01-02", periods=n)
    rets = rng.normal(0.0005, 0.01, size=n)
    close = 100 * np.cumprod(1 + rets)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    volume = rng.integers(1_000_000, 2_000_000, size=n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


def test_parse_advice():
    trader = (
        "THESIS: Buy leaders.\n"
        "TOP_PICKS: ARM, TSM\n"
        "AVOID: none\n"
        "RISKS: gap risk, crowding\n"
        "ACTION: follow paper-plan\n"
    )
    analyst = (
        "STANCE: cautious\n"
        "SUMMARY: Keep sleeves balanced.\n"
        "CHECKS: cash, concentration\n"
        "SCORE: 7/10\n"
    )
    r = parse_advice(trader, analyst, model="mock")
    assert r.stance == "cautious"
    assert r.top_picks == ["ARM", "TSM"]
    assert "gap risk" in r.risks[0] or r.risks == ["gap risk", "crowding"]
    assert "paper-plan" in r.action


def test_graph_with_mock_llm():
    llm = MockLLM()
    app = build_advise_graph(llm)
    out = app.invoke({"context_text": "Signals:\n  ARM 0.60 buy", "errors": []})
    assert out["trader_raw"]
    assert out["analyst_raw"]
    assert len(llm.calls) == 2


def test_context_prompt_defines_open_orders():
    ctx = MarketContext(
        universe="test",
        signals=[SignalRow("ARM", 0.6, "buy", "2026-07-17")],
        account_lines=[
            "filled_positions=0 open_unfilled_orders=8",
            "portfolio_state=cash_with_working_orders",
        ],
        notes=["Open orders are not fills."],
    )
    block = ctx.to_prompt_block()
    assert "open_orders are unfilled" in block or "Open orders are not fills" in block
    assert "filled_positions=0" in block


def test_run_advise_with_injected_context(tmp_path):
    ctx = MarketContext(
        universe="test",
        signals=[SignalRow("ARM", 0.6, "buy", "2026-07-17")],
        plan_lines=["intents: 1"],
    )
    # dummy model path unused when context injected
    report = run_advise(
        model_path=tmp_path / "missing.txt",
        include_account=False,
        llm=MockLLM(),
        context=ctx,
    )
    assert report.trader_raw
    assert report.analyst_raw
    assert report.stance in {"cautious", "bullish", "defensive", "neutral", "unknown"} or report.stance


def test_score_result_not_used_as_market_context_signals():
    """Regression: ScoreResult is not a list — MarketContext needs SignalRow list.

    Bug: assigning score_universe() directly to ctx.signals made signals[:25]
    raise TypeError: 'ScoreResult' object is not subscriptable.
    """
    scored = ScoreResult(
        rows=[
            SignalRow("ARM", 0.60, "buy", "2026-07-17"),
            SignalRow("TSM", 0.55, "buy", "2026-07-17"),
        ]
    )
    # Wrong pattern (historical bug) — ScoreResult is list-like now, but context
    # must still store a real list for type clarity and plan builders.
    assert isinstance(scored, ScoreResult)
    ctx = MarketContext(universe="test", signals=list(scored.rows))
    assert isinstance(ctx.signals, list)
    assert all(isinstance(s, SignalRow) for s in ctx.signals)
    block = ctx.to_prompt_block()
    assert "ARM" in block and "TSM" in block
    # Slicing MarketContext.signals must work (advise prompt path)
    assert len(ctx.signals[:25]) == 2


def test_gather_market_context_with_account_uses_ctx_signals(tmp_path):
    """Regression: build_trade_plan must use ctx.signals, not undefined `signals`.

    Bug: NameError: name 'signals' is not defined when include_account=True.
    """
    from neotrade.signals.model import SignalModel

    frames = {"ARM": _synth_ohlcv(seed=1), "JNJ": _synth_ohlcv(seed=2)}
    model = SignalModel(horizon=5)
    model.fit(frames, num_boost_round=30, early_stopping_rounds=5)
    model_path = tmp_path / "signal.txt"
    model.save(model_path)

    cfg = TickersConfig(
        tickers=[
            Ticker(symbol="ARM", sleeve="growth"),
            Ticker(symbol="JNJ", sleeve="defensive"),
        ],
        risk=RiskSettings(),
    )
    acct = AccountSnapshot(
        equity=100_000,
        cash=100_000,
        buying_power=100_000,
        portfolio_value=100_000,
        status="ACTIVE",
        currency="USD",
        pattern_day_trader=False,
        trading_blocked=False,
        account_blocked=False,
    )
    client = MagicMock()
    client.get_account.return_value = acct
    client.list_positions.return_value = []
    client.list_orders.return_value = [
        {"side": "buy", "symbol": "ARM", "qty": "10", "status": "accepted", "filled_qty": "0"}
    ]

    with (
        patch("neotrade.agents.context.load_universe_ohlcv") as load_bars,
        patch("neotrade.agents.context.AlpacaPaperClient", return_value=client),
        patch("neotrade.agents.context.prices_for_plan", return_value={"ARM": 100.0, "JNJ": 150.0}),
    ):
        load_bars.return_value = MagicMock(frames=frames, errors=[])
        ctx = gather_market_context(
            model_path=model_path,
            include_account=True,
            cfg=cfg,
        )

    assert isinstance(ctx.signals, list)
    assert len(ctx.signals) >= 1
    assert any("filled_positions=0" in line for line in ctx.account_lines)
    assert any("WORKING" in line or "open_unfilled" in line for line in ctx.account_lines)
    # plan built successfully (no NameError); may be empty intents with notes
    assert isinstance(ctx.plan_lines, list)
    assert len(ctx.plan_lines) >= 1


def test_run_advise_builds_context_without_nameerror(tmp_path):
    """End-to-end advise path with mocked score + account (both regressions)."""
    from neotrade.signals.model import SignalModel

    frames = {"ARM": _synth_ohlcv(seed=3)}
    model = SignalModel(horizon=5)
    model.fit(frames, num_boost_round=30, early_stopping_rounds=5)
    model_path = tmp_path / "signal.txt"
    model.save(model_path)

    cfg = TickersConfig(tickers=[Ticker(symbol="ARM", sleeve="growth")])
    acct = AccountSnapshot(
        equity=50_000,
        cash=50_000,
        buying_power=50_000,
        portfolio_value=50_000,
        status="ACTIVE",
        currency="USD",
        pattern_day_trader=False,
        trading_blocked=False,
        account_blocked=False,
    )
    client = MagicMock()
    client.get_account.return_value = acct
    client.list_positions.return_value = []
    client.list_orders.return_value = []

    with (
        patch("neotrade.agents.context.load_tickers_config", return_value=cfg),
        patch("neotrade.agents.context.load_universe_ohlcv") as load_bars,
        patch("neotrade.agents.context.AlpacaPaperClient", return_value=client),
        patch("neotrade.agents.context.prices_for_plan", return_value={"ARM": 200.0}),
    ):
        load_bars.return_value = MagicMock(frames=frames, errors=[])
        report = run_advise(
            model_path=model_path,
            include_account=True,
            llm=MockLLM(),
        )

    assert report.trader_raw
    assert report.analyst_raw
    assert not any("signals" in e.lower() and "not defined" in e.lower() for e in report.errors)
