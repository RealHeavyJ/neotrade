"""LangGraph: gather context → trading expert → performance analyst."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from neotrade.agents.context import MarketContext, gather_market_context
from neotrade.agents.llm import LLMClient, OllamaClient, default_llm
from neotrade.agents.recommend import AdviceReport, parse_advice

TRADER_SYSTEM = """You are the Expert Trading Agent for neotrade (paper trading only).
Use only the provided signals, account, and plan data. Do not invent prices.

Critical portfolio rules:
- positions=N means N filled holdings. open_orders are NOT positions.
- status accepted/new/pending are unfilled working orders; cash is usually still free until fill.
- Do NOT say the portfolio is fully invested solely because open_orders > 0.
- Do NOT recommend closing positions that do not appear under filled positions.
- Outside US regular hours, day market orders often sit accepted until the next session.
- Prefer actions aligned with the paper plan intents when provided.

Respond with short labeled lines exactly in this format:
THESIS: <one sentence>
TOP_PICKS: <comma-separated symbols>
AVOID: <comma-separated symbols or none>
RISKS: <comma-separated risks>
ACTION: <what to do next for paper portfolio>
"""

ANALYST_SYSTEM = """You are the Business/Performance Analyst for neotrade.
Critique the trading expert using diversification (growth vs defensive sleeves),
cash buffer, concentration, and signal quality. Paper trading only.

Critical checks:
- Separate filled positions from open (unfilled) orders.
- If positions=0 and open_orders>0, portfolio is NOT deployed yet; score patience / session timing.
- Flag bad advice that treats accepted orders as owned inventory or urges closing empty positions.
- Note modest LightGBM edge; avoid overconfidence.

Respond with short labeled lines exactly in this format:
STANCE: <bullish|cautious|defensive|neutral>
SUMMARY: <one sentence>
CHECKS: <comma-separated monitoring items>
SCORE: <0-10>/10
"""


class AdviseState(TypedDict, total=False):
    context_text: str
    trader_raw: str
    analyst_raw: str
    errors: Annotated[list[str], lambda a, b: (a or []) + (b or [])]


def build_advise_graph(llm: LLMClient | None = None) -> Any:
    client = llm or default_llm()

    def trading_expert(state: AdviseState) -> dict[str, Any]:
        try:
            text = client.complete(TRADER_SYSTEM, state.get("context_text") or "")
            return {"trader_raw": text}
        except Exception as exc:  # noqa: BLE001
            return {"trader_raw": "", "errors": [f"trader: {exc}"]}

    def performance_analyst(state: AdviseState) -> dict[str, Any]:
        user = (
            f"Market context:\n{state.get('context_text') or ''}\n\n"
            f"Trading expert output:\n{state.get('trader_raw') or '(none)'}"
        )
        try:
            text = client.complete(ANALYST_SYSTEM, user)
            return {"analyst_raw": text}
        except Exception as exc:  # noqa: BLE001
            return {"analyst_raw": "", "errors": [f"analyst: {exc}"]}

    graph = StateGraph(AdviseState)
    graph.add_node("trading_expert", trading_expert)
    graph.add_node("performance_analyst", performance_analyst)
    graph.add_edge(START, "trading_expert")
    graph.add_edge("trading_expert", "performance_analyst")
    graph.add_edge("performance_analyst", END)
    return graph.compile()


def run_advise(
    *,
    model_path: Path,
    config_path: str | Path | None = None,
    include_account: bool = True,
    llm: LLMClient | None = None,
    context: MarketContext | None = None,
) -> AdviceReport:
    client = llm or default_llm()
    ctx = context or gather_market_context(
        config_path=config_path,
        model_path=model_path,
        include_account=include_account,
    )
    app = build_advise_graph(client)
    result = app.invoke({"context_text": ctx.to_prompt_block(), "errors": []})
    model_name = ""
    if isinstance(client, OllamaClient):
        model_name = client.config.model
    elif llm is not None:
        model_name = type(llm).__name__
    report = parse_advice(
        result.get("trader_raw") or "",
        result.get("analyst_raw") or "",
        model=model_name,
    )
    report.errors = list(result.get("errors") or [])
    return report
