"""Structured advice report from multi-agent run."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AdviceReport:
    trader_raw: str
    analyst_raw: str
    stance: str = "unknown"
    summary: str = ""
    top_picks: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    action: str = ""
    model: str = ""
    errors: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            "=== neotrade advice ===",
            f"stance: {self.stance}",
            f"model: {self.model or 'n/a'}",
            "",
            "## Trading expert",
            self.trader_raw.strip() or "(empty)",
            "",
            "## Performance analyst",
            self.analyst_raw.strip() or "(empty)",
            "",
            "## Parsed",
            f"summary: {self.summary or '(see above)'}",
            f"top_picks: {', '.join(self.top_picks) if self.top_picks else 'n/a'}",
            f"action: {self.action or 'n/a'}",
        ]
        if self.risks:
            lines.append("risks: " + "; ".join(self.risks))
        if self.errors:
            lines.append("errors: " + "; ".join(self.errors))
        return "\n".join(lines)


def _first_line_value(text: str, prefix: str) -> str:
    prefix_l = prefix.lower()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(prefix_l):
            _, _, rest = stripped.partition(":")
            return rest.strip()
    return ""


def parse_advice(trader: str, analyst: str, *, model: str = "") -> AdviceReport:
    report = AdviceReport(trader_raw=trader, analyst_raw=analyst, model=model)
    report.stance = _first_line_value(analyst, "STANCE") or "unknown"
    report.summary = _first_line_value(analyst, "SUMMARY") or _first_line_value(trader, "THESIS")
    picks = _first_line_value(trader, "TOP_PICKS")
    if picks:
        report.top_picks = [p.strip() for p in picks.replace(";", ",").split(",") if p.strip()]
    risks = _first_line_value(trader, "RISKS")
    if risks:
        report.risks = [r.strip() for r in risks.replace(";", ",").split(",") if r.strip()]
    report.action = _first_line_value(trader, "ACTION") or _first_line_value(analyst, "CHECKS")
    return report
