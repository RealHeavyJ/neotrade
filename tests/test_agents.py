from neotrade.agents.context import MarketContext
from neotrade.agents.graph import build_advise_graph, run_advise
from neotrade.agents.llm import MockLLM
from neotrade.agents.recommend import parse_advice
from neotrade.signals.score import SignalRow


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
