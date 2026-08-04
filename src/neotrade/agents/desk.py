"""Multi-agent investment desk (local Ollama + LangGraph).

Roles (in order):
  1. Ops — session, orders, blockers
  2. Quant — eval/BT gates, promote/no-promote, training recommendations
  3. PM — book vs ranked plan, actions (never auto-execute)
  4. Critic — challenge overconfidence; enforce paper/RTH/gates

LLMs may *recommend* ``neotrade train|eval|backtest`` and config experiments.
They must **never** claim to retrain LightGBM from prose, and must not invent metrics.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from neotrade.agents.desk_context import DeskPacket, gather_desk_packet
from neotrade.agents.llm import LLMClient, MockLLM, OllamaClient, default_llm
from neotrade.config.load import project_root
from neotrade.learning.log import append_entry
from neotrade.logging_config import get_logger

log = get_logger("agents.desk")

OPS_SYSTEM = """You are the OPS controller for neotrade paper trading.
Use ONLY the desk packet. Do not invent account numbers.

Respond with exact labels:
SESSION_OK: yes|no
EXECUTE_ALLOWED: yes|no
BLOCKERS: <comma list or none>
OPS_ACTION: <one line: what human should do ops-wise>
"""

QUANT_SYSTEM = """You are the QUANT lead for neotrade.
You read eval + backtest gates. You improve the *process*, not by training on text.
You are also an expert reviewer: if the human is chasing a feature that does not
raise promote honesty or paper edge, say so bluntly.

Rules:
- promote_ok=true only if packet says so; never override FAIL to PASS.
- Recommend train/eval/backtest/status/ablate when artifacts missing or stale.
- NEVER say LightGBM should train on advise/desk prose or "maturity narratives".
- Prefer concrete next experiments (thresholds, top_n, windows, regime, slip).
- Prefer measured epoch/gate diffs over new dashboards when both are options.

Respond with exact labels:
PROMOTE: yes|no|unknown
GATE_SUMMARY: <one sentence>
EDGE_NOTE: <one sentence on eval/BT edges>
TRAIN_REC: <none|neotrade train|neotrade eval|neotrade backtest|neotrade status|combo>
EXPERIMENT: <one concrete config/model experiment or none>
BLIND_SPOT: <one thing the human may be missing this week, or none>
QUANT_SCORE: <0-10>/10
"""

PM_SYSTEM = """You are the PORTFOLIO MANAGER for neotrade paper book.
Align recommendations with ranked paper plan and signals. Paper only.

Rules:
- filled positions only are inventory; open_orders are not.
- If allow_execute=false, action must not be execute.
- If promote_ok is false/unknown, do not urge aggressive new risk.
- Prefer hold/rebalance/trim/research over execute.

Respond with exact labels:
BOOK_VIEW: <one sentence>
TOP_PICKS: <comma symbols>
EXITS_OR_TRIMS: <comma symbols or none>
PM_ACTION: hold|rebalance|trim|research_only|execute_plan
CONFIDENCE: low|medium|high
PM_RATIONALE: <one sentence>
"""

CRITIC_SYSTEM = """You are the RISK CRITIC / devil's advocate and process skeptic.
Challenge PM and Quant. Catch violations of packet facts.
Flag busywork: infra, vanity metrics, or features that do not change promote/book.

Respond with exact labels:
CRITIQUE: <one sentence strongest objection>
OVERRIDE: none|force_hold|force_research|block_execute
FINAL_ACTION: hold|rebalance|trim|research_only|execute_plan
FINAL_CONFIDENCE: low|medium|high
HUMAN_TODO: <single next step for the human>
BLIND_SPOT: <one miss (process, risk, or overbuilding) or none>
CRITIC_SCORE: <0-10>/10
"""


class DeskState(TypedDict, total=False):
    packet_text: str
    ops_raw: str
    quant_raw: str
    pm_raw: str
    critic_raw: str
    errors: Annotated[list[str], lambda a, b: (a or []) + (b or [])]


@dataclass
class DeskReport:
    """Structured multi-agent desk output."""

    ts: str
    packet_summary: str
    ops_raw: str = ""
    quant_raw: str = ""
    pm_raw: str = ""
    critic_raw: str = ""
    final_action: str = "research_only"
    final_confidence: str = "low"
    promote: str = "unknown"
    human_todo: str = ""
    train_rec: str = "none"
    experiment: str = "none"
    model: str = ""
    errors: list[str] = field(default_factory=list)
    allow_execute: bool = False

    def render(self) -> str:
        lines = [
            "=== neotrade desk ===",
            f"ts: {self.ts}",
            f"model: {self.model or 'n/a'}",
            f"allow_execute: {self.allow_execute}",
            f"promote: {self.promote}",
            f"final_action: {self.final_action}  confidence: {self.final_confidence}",
            f"human_todo: {self.human_todo or 'n/a'}",
            f"train_rec: {self.train_rec}",
            f"experiment: {self.experiment}",
            "",
            "## Ops",
            self.ops_raw.strip() or "(empty)",
            "",
            "## Quant",
            self.quant_raw.strip() or "(empty)",
            "",
            "## PM",
            self.pm_raw.strip() or "(empty)",
            "",
            "## Critic",
            self.critic_raw.strip() or "(empty)",
            "",
            "## Packet (facts)",
            self.packet_summary[:4000],
        ]
        if self.errors:
            lines.append("")
            lines.append("errors: " + "; ".join(self.errors))
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _field(text: str, key: str) -> str:
    key_u = key.upper()
    for line in text.splitlines():
        s = line.strip()
        if s.upper().startswith(key_u + ":"):
            return s.split(":", 1)[1].strip()
    return ""


def _normalize_action(raw: str, *, allow_execute: bool, promote: str) -> str:
    a = (raw or "research_only").strip().lower().replace(" ", "_")
    allowed = {"hold", "rebalance", "trim", "research_only", "execute_plan"}
    if a not in allowed:
        a = "research_only"
    if a == "execute_plan" and (not allow_execute or promote == "no"):
        a = "hold" if promote == "no" else "research_only"
    return a


def parse_desk_report(
    *,
    packet: DeskPacket,
    ops: str,
    quant: str,
    pm: str,
    critic: str,
    model: str,
    errors: list[str] | None = None,
) -> DeskReport:
    promote = (_field(quant, "PROMOTE") or "unknown").lower()
    if promote not in {"yes", "no", "unknown"}:
        promote = "unknown"
    # Trust packet over LLM if conflict
    if packet.promote_ok is True and promote == "no":
        pass  # critic may still block
    if packet.promote_ok is False:
        promote = "no"
    if packet.promote_ok is None and promote == "yes":
        promote = "unknown"

    final = _field(critic, "FINAL_ACTION") or _field(pm, "PM_ACTION") or "research_only"
    conf = (_field(critic, "FINAL_CONFIDENCE") or _field(pm, "CONFIDENCE") or "low").lower()
    if conf not in {"low", "medium", "high"}:
        conf = "low"
    override = (_field(critic, "OVERRIDE") or "none").lower()
    if "block_execute" in override or "force_hold" in override:
        final = "hold"
    if "force_research" in override:
        final = "research_only"

    final = _normalize_action(final, allow_execute=packet.allow_execute, promote=promote)
    todo = _field(critic, "HUMAN_TODO") or _field(ops, "OPS_ACTION") or "Review packet and paper-plan"
    train_rec = _field(quant, "TRAIN_REC") or "none"
    experiment = _field(quant, "EXPERIMENT") or "none"

    return DeskReport(
        ts=packet.ts,
        packet_summary=packet.to_prompt_block(),
        ops_raw=ops,
        quant_raw=quant,
        pm_raw=pm,
        critic_raw=critic,
        final_action=final,
        final_confidence=conf,
        promote=promote,
        human_todo=todo,
        train_rec=train_rec,
        experiment=experiment,
        model=model,
        errors=list(errors or []),
        allow_execute=packet.allow_execute,
    )


class DeskMockLLM(MockLLM):
    """Deterministic multi-role responses for tests."""

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        s = system.lower()
        if "ops controller" in s:
            # Match fact line only (HARD RULES text also contains "allow_execute=true")
            allow = "no"
            for line in user.splitlines():
                if line.strip().lower().startswith("allow_execute="):
                    allow = "yes" if "true" in line.lower() else "no"
                    break
            return (
                f"SESSION_OK: yes\nEXECUTE_ALLOWED: {allow}\n"
                "BLOCKERS: none\nOPS_ACTION: run daily checklist; no execute off RTH\n"
            )
        if "quant lead" in s:
            promote = "unknown"
            for line in user.splitlines():
                ls = line.strip().lower()
                if ls.startswith("promote_ok="):
                    if "true" in ls:
                        promote = "yes"
                    elif "false" in ls:
                        promote = "no"
                    break
            return (
                f"PROMOTE: {promote}\n"
                "GATE_SUMMARY: Use packet gates only.\n"
                "EDGE_NOTE: Prefer stable multi-window BT.\n"
                "TRAIN_REC: neotrade eval && neotrade backtest\n"
                "EXPERIMENT: try --rebalance-every 7 if turnover high\n"
                "QUANT_SCORE: 7/10\n"
            )
        if "portfolio manager" in s:
            return (
                "BOOK_VIEW: Align to ranked plan; respect cash and losers.\n"
                "TOP_PICKS: NVDA, AMD\n"
                "EXITS_OR_TRIMS: none\n"
                "PM_ACTION: hold\n"
                "CONFIDENCE: medium\n"
                "PM_RATIONALE: Wait for RTH and gate PASS before adding risk.\n"
            )
        return (
            "CRITIQUE: Do not override promote FAIL.\n"
            "OVERRIDE: none\n"
            "FINAL_ACTION: hold\n"
            "FINAL_CONFIDENCE: medium\n"
            "HUMAN_TODO: Review paper-plan; no execute unless RTH and promote yes\n"
            "CRITIC_SCORE: 8/10\n"
        )


def build_desk_graph(llm: LLMClient | None = None) -> Any:
    client = llm or default_llm()

    def ops_node(state: DeskState) -> dict[str, Any]:
        try:
            text = client.complete(OPS_SYSTEM, state.get("packet_text") or "")
            return {"ops_raw": text}
        except (RuntimeError, OSError, ValueError, TimeoutError) as exc:
            log.error("ops failed: %s", exc)
            return {"ops_raw": "", "errors": [f"ops: {exc}"]}

    def quant_node(state: DeskState) -> dict[str, Any]:
        user = (
            f"{state.get('packet_text') or ''}\n\nOPS:\n{state.get('ops_raw') or ''}"
        )
        try:
            text = client.complete(QUANT_SYSTEM, user)
            return {"quant_raw": text}
        except (RuntimeError, OSError, ValueError, TimeoutError) as exc:
            log.error("quant failed: %s", exc)
            return {"quant_raw": "", "errors": [f"quant: {exc}"]}

    def pm_node(state: DeskState) -> dict[str, Any]:
        user = (
            f"{state.get('packet_text') or ''}\n\n"
            f"OPS:\n{state.get('ops_raw') or ''}\n\n"
            f"QUANT:\n{state.get('quant_raw') or ''}"
        )
        try:
            text = client.complete(PM_SYSTEM, user)
            return {"pm_raw": text}
        except (RuntimeError, OSError, ValueError, TimeoutError) as exc:
            log.error("pm failed: %s", exc)
            return {"pm_raw": "", "errors": [f"pm: {exc}"]}

    def critic_node(state: DeskState) -> dict[str, Any]:
        user = (
            f"{state.get('packet_text') or ''}\n\n"
            f"OPS:\n{state.get('ops_raw') or ''}\n\n"
            f"QUANT:\n{state.get('quant_raw') or ''}\n\n"
            f"PM:\n{state.get('pm_raw') or ''}"
        )
        try:
            text = client.complete(CRITIC_SYSTEM, user)
            return {"critic_raw": text}
        except (RuntimeError, OSError, ValueError, TimeoutError) as exc:
            log.error("critic failed: %s", exc)
            return {"critic_raw": "", "errors": [f"critic: {exc}"]}

    g = StateGraph(DeskState)
    g.add_node("ops", ops_node)
    g.add_node("quant", quant_node)
    g.add_node("pm", pm_node)
    g.add_node("critic", critic_node)
    g.add_edge(START, "ops")
    g.add_edge("ops", "quant")
    g.add_edge("quant", "pm")
    g.add_edge("pm", "critic")
    g.add_edge("critic", END)
    return g.compile()


def run_desk(
    *,
    model_path: Path,
    config_path: str | Path | None = None,
    include_account: bool = True,
    llm: LLMClient | None = None,
    packet: DeskPacket | None = None,
    save: bool = True,
) -> DeskReport:
    """Run full desk graph and optionally persist JSON + learning log."""
    client = llm or default_llm()
    pkt = packet or gather_desk_packet(
        model_path=model_path,
        config_path=config_path,
        include_account=include_account,
    )
    app = build_desk_graph(client)
    result = app.invoke({"packet_text": pkt.to_prompt_block(), "errors": []})
    model_name = ""
    if isinstance(client, OllamaClient):
        model_name = client.config.model
    elif isinstance(client, MockLLM):
        model_name = type(client).__name__

    report = parse_desk_report(
        packet=pkt,
        ops=result.get("ops_raw") or "",
        quant=result.get("quant_raw") or "",
        pm=result.get("pm_raw") or "",
        critic=result.get("critic_raw") or "",
        model=model_name,
        errors=list(result.get("errors") or []),
    )

    if save:
        out_dir = project_root() / "data" / "learning"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = out_dir / f"desk_{stamp}.json"
        latest = out_dir / "desk_latest.json"
        payload = report.to_dict()
        # keep packet full but cap huge curves if any
        try:
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            latest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            log.warning("desk json save failed: %s", exc)
            report.errors.append(f"save: {exc}")
        try:
            append_entry(
                "desk_run",
                {
                    "final_action": report.final_action,
                    "promote": report.promote,
                    "train_rec": report.train_rec,
                    "experiment": report.experiment,
                    "allow_execute": report.allow_execute,
                    "model": report.model,
                    "lightgbm_eligible": False,
                },
            )
        except OSError as exc:
            log.warning("desk learning log failed: %s", exc)
        # Discipline: reconcile orphans, then at most one open experiment
        try:
            from neotrade.learning.experiments import (
                discipline_status,
                maybe_open_from_desk_report,
                reconcile_open_experiments,
            )

            abandoned = reconcile_open_experiments()
            if abandoned:
                log.warning("desk reconciled abandoned=%s open experiments", len(abandoned))
            exp = maybe_open_from_desk_report(report.experiment, source="desk")
            if exp is not None:
                log.info("desk experiment id=%s status=%s", exp.id[:8], exp.status)
            status = discipline_status()
            if not status["disciplined"]:
                report.errors.append(
                    f"experiment discipline fail: {status['open_count']} open"
                )
        except (OSError, ValueError, KeyError, RuntimeError, TypeError) as exc:
            log.warning("desk experiment discipline skipped: %s", exc)

    return report
