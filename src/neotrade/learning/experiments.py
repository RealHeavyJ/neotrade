"""Experiment ledger: desk EXPERIMENT → measured eval/BT outcomes.

Closes the local-LLM improvement loop without training LightGBM on prose.
All entries are journal-only (``lightgbm_eligible=false``).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neotrade.config.load import project_root
from neotrade.learning.log import append_entry, learning_dir
from neotrade.logging_config import get_logger

log = get_logger("learning.experiments")

LEDGER_NAME = "experiments.jsonl"
KIND_OPEN = "experiment_open"
KIND_COMPLETE = "experiment_complete"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ledger_path() -> Path:
    return learning_dir() / LEDGER_NAME


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def snapshot_gates(root: Path | None = None) -> dict[str, Any]:
    """Capture current eval/backtest promote metrics for before/after compare."""
    root = root or project_root()
    learning = root / "data" / "learning"
    out: dict[str, Any] = {"ts": _now()}
    ev = _read_json(learning / "eval_latest.json")
    if ev:
        out["eval"] = {
            "mean_accuracy": ev.get("mean_accuracy"),
            "edge_vs_always_long": ev.get("edge_vs_always_long"),
            "edge_vs_momentum": ev.get("edge_vs_momentum"),
            "mean_brier": ev.get("mean_brier"),
        }
    bt = _read_json(learning / "backtest_latest.json")
    if bt:
        gate = bt.get("gate") or {}
        stable = bt.get("stable_gate") or {}
        sig = bt.get("signal") or {}
        full = bool(gate.get("pass"))
        st = stable.get("pass") if stable else None
        promote = full if st is None else (full and bool(st))
        out["backtest"] = {
            "promote": promote,
            "full_gate": full,
            "stable_gate": st,
            "signal_return": sig.get("total_return"),
            "max_drawdown": sig.get("max_drawdown"),
            "sharpe": sig.get("sharpe"),
            "eq_return": (bt.get("equal_weight") or {}).get("total_return"),
            "mom_return": (bt.get("momentum") or {}).get("total_return"),
            "n_trades": sig.get("n_trades"),
        }
    desk = _read_json(learning / "desk_latest.json")
    if desk:
        out["desk"] = {
            "final_action": desk.get("final_action"),
            "promote": desk.get("promote"),
            "experiment": desk.get("experiment"),
        }
    return out


def _append_ledger(row: dict[str, Any]) -> Path:
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return path


def _load_ledger() -> list[dict[str, Any]]:
    path = _ledger_path()
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


@dataclass
class Experiment:
    """One improvement experiment tracked end-to-end."""

    id: str
    status: str  # open | complete
    hypothesis: str
    source: str = "manual"
    opened_at: str = ""
    closed_at: str = ""
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""  # pass | fail | mixed | abandoned
    notes: str = ""
    lightgbm_eligible: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary_line(self) -> str:
        flag = self.status.upper()
        out = f"[{flag}] {self.id[:8]}  {self.hypothesis[:80]}"
        if self.outcome:
            out += f"  → {self.outcome}"
        return out


def _is_noop_experiment(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in {"", "none", "n/a", "na", "null", "-", "no experiment"}


def open_experiment(
    hypothesis: str,
    *,
    source: str = "manual",
    before: dict[str, Any] | None = None,
    notes: str = "",
    replace_open: bool = True,
) -> Experiment:
    """Open a new experiment; snapshot gates as baseline.

    Discipline: at most **one** open experiment. If another is open:
      * same hypothesis → return existing
      * different hypothesis + ``replace_open`` → abandon previous, then open
      * different + not replace → raise ValueError
    """
    if _is_noop_experiment(hypothesis):
        raise ValueError("hypothesis empty or 'none' — nothing to track")
    hyp = hypothesis.strip()[:500]
    open_ones = list_experiments(status="open", limit=50)
    same = [e for e in open_ones if e.hypothesis == hyp]
    if same:
        log.info("experiment already open id=%s", same[0].id[:8])
        return same[0]
    if open_ones:
        if not replace_open:
            raise ValueError(
                f"experiment already open ({open_ones[0].id[:8]}: {open_ones[0].hypothesis[:40]}). "
                "Complete it first: neotrade experiment complete --latest"
            )
        for prev in open_ones:
            complete_experiment(
                prev.id,
                outcome="abandoned",
                notes="auto-closed: new experiment opened (single-open discipline)",
            )
            log.warning("abandoned open experiment id=%s for new hyp", prev.id[:8])

    exp = Experiment(
        id=str(uuid.uuid4()),
        status="open",
        hypothesis=hyp,
        source=source,
        opened_at=_now(),
        before=before if before is not None else snapshot_gates(),
        notes=notes[:500],
    )
    _append_ledger({"event": KIND_OPEN, **exp.to_dict()})
    append_entry(
        KIND_OPEN,
        {
            "id": exp.id,
            "hypothesis": exp.hypothesis,
            "source": exp.source,
            "lightgbm_eligible": False,
        },
    )
    log.info("experiment opened id=%s hyp=%s", exp.id[:8], exp.hypothesis[:60])
    return exp


def open_from_desk(
    *,
    desk_path: Path | None = None,
    notes: str = "",
) -> Experiment | None:
    """Open experiment from desk_latest.json EXPERIMENT field if meaningful."""
    path = desk_path or (project_root() / "data" / "learning" / "desk_latest.json")
    data = _read_json(path)
    if not data:
        raise FileNotFoundError(f"desk artifact not found: {path}")
    hyp = str(data.get("experiment") or "").strip()
    if _is_noop_experiment(hyp):
        return None
    return open_experiment(hyp, source="desk", notes=notes or "from desk_latest", replace_open=True)


def list_experiments(*, status: str | None = None, limit: int = 50) -> list[Experiment]:
    """Rebuild experiment state from ledger (last event wins per id)."""
    by_id: dict[str, Experiment] = {}
    for row in _load_ledger():
        eid = str(row.get("id") or "")
        if not eid:
            continue
        event = str(row.get("event") or "")
        if event == KIND_OPEN:
            by_id[eid] = Experiment(
                id=eid,
                status="open",
                hypothesis=str(row.get("hypothesis") or ""),
                source=str(row.get("source") or "manual"),
                opened_at=str(row.get("opened_at") or row.get("ts") or ""),
                before=dict(row.get("before") or {}),
                notes=str(row.get("notes") or ""),
            )
        elif event == KIND_COMPLETE:
            prev = by_id.get(eid)
            by_id[eid] = Experiment(
                id=eid,
                status="complete",
                hypothesis=str(row.get("hypothesis") or (prev.hypothesis if prev else "")),
                source=str(row.get("source") or (prev.source if prev else "manual")),
                opened_at=str(row.get("opened_at") or (prev.opened_at if prev else "")),
                closed_at=str(row.get("closed_at") or ""),
                before=dict(row.get("before") or (prev.before if prev else {})),
                after=dict(row.get("after") or {}),
                outcome=str(row.get("outcome") or ""),
                notes=str(row.get("notes") or (prev.notes if prev else "")),
            )
    items = list(by_id.values())
    items.sort(key=lambda e: e.opened_at or e.closed_at or "", reverse=True)
    if status:
        items = [e for e in items if e.status == status]
    return items[:limit]


def get_experiment(exp_id: str) -> Experiment | None:
    """Lookup by full or prefix id."""
    exp_id = exp_id.strip()
    for e in list_experiments(limit=500):
        if e.id == exp_id or e.id.startswith(exp_id):
            return e
    return None


def _auto_outcome(before: dict[str, Any], after: dict[str, Any]) -> str:
    """Heuristic outcome from gate snapshots."""
    b_bt = before.get("backtest") or {}
    a_bt = after.get("backtest") or {}
    if not a_bt:
        return "mixed"
    b_prom = b_bt.get("promote")
    a_prom = a_bt.get("promote")
    b_ret = b_bt.get("signal_return")
    a_ret = a_bt.get("signal_return")
    if a_prom is True and b_prom is not True:
        return "pass"
    if a_prom is False and b_prom is True:
        return "fail"
    if isinstance(a_ret, (int, float)) and isinstance(b_ret, (int, float)):
        if a_ret > b_ret + 0.01:
            return "pass"
        if a_ret < b_ret - 0.01:
            return "fail"
    if a_prom is True:
        return "pass"
    if a_prom is False:
        return "fail"
    return "mixed"


def complete_experiment(
    exp_id: str,
    *,
    outcome: str | None = None,
    notes: str = "",
    after: dict[str, Any] | None = None,
) -> Experiment:
    """Close experiment with after snapshot and outcome."""
    exp = get_experiment(exp_id)
    if exp is None:
        raise FileNotFoundError(f"experiment not found: {exp_id}")
    if exp.status == "complete":
        return exp
    after_snap = after if after is not None else snapshot_gates()
    oc = (outcome or "").strip().lower()
    if oc not in {"pass", "fail", "mixed", "abandoned"}:
        oc = _auto_outcome(exp.before, after_snap)
    exp.status = "complete"
    exp.closed_at = _now()
    exp.after = after_snap
    exp.outcome = oc
    if notes:
        exp.notes = (exp.notes + " | " + notes).strip(" |")[:800]
    _append_ledger({"event": KIND_COMPLETE, **exp.to_dict()})
    append_entry(
        KIND_COMPLETE,
        {
            "id": exp.id,
            "hypothesis": exp.hypothesis,
            "outcome": exp.outcome,
            "lightgbm_eligible": False,
        },
    )
    log.info("experiment complete id=%s outcome=%s", exp.id[:8], exp.outcome)
    return exp


def complete_latest_open(
    *,
    outcome: str | None = None,
    notes: str = "",
) -> Experiment | None:
    """Complete the most recently opened experiment."""
    open_ones = list_experiments(status="open", limit=20)
    if not open_ones:
        return None
    return complete_experiment(open_ones[0].id, outcome=outcome, notes=notes)


def complete_all_open(
    *,
    outcome: str = "abandoned",
    notes: str = "bulk complete — discipline sweep",
) -> list[Experiment]:
    """Close every open experiment (agents must not leave orphans)."""
    done: list[Experiment] = []
    # re-list each time because complete mutates ledger
    while True:
        open_ones = list_experiments(status="open", limit=100)
        if not open_ones:
            break
        done.append(
            complete_experiment(open_ones[0].id, outcome=outcome, notes=notes)
        )
    log.info("complete_all_open n=%s outcome=%s", len(done), outcome)
    return done


def reconcile_open_experiments(
    *,
    keep: str = "newest",
    abandon_notes: str = "reconcile: single-open discipline",
) -> list[Experiment]:
    """Ensure at most one open experiment; abandon the rest.

    Args:
        keep: ``newest`` (default) or ``oldest``.
    """
    open_ones = list_experiments(status="open", limit=100)
    if len(open_ones) <= 1:
        return []
    # list is newest-first
    if keep == "oldest":
        keeper = open_ones[-1]
        drop = open_ones[:-1]
    else:
        keeper = open_ones[0]
        drop = open_ones[1:]
    abandoned: list[Experiment] = []
    for e in drop:
        abandoned.append(
            complete_experiment(
                e.id,
                outcome="abandoned",
                notes=f"{abandon_notes}; kept={keeper.id[:8]}",
            )
        )
    log.warning(
        "reconcile abandoned=%s kept=%s",
        len(abandoned),
        keeper.id[:8],
    )
    return abandoned


def assert_no_open_experiments() -> None:
    """Raise if any experiment is still open (for strict agent close)."""
    open_ones = list_experiments(status="open", limit=10)
    if open_ones:
        ids = ", ".join(e.id[:8] for e in open_ones)
        raise RuntimeError(
            f"{len(open_ones)} open experiment(s): {ids}. "
            "Complete with: neotrade experiment complete --all"
        )


def format_compare(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Human lines comparing gate snapshots."""
    lines: list[str] = []
    b_bt = before.get("backtest") or {}
    a_bt = after.get("backtest") or {}
    b_ev = before.get("eval") or {}
    a_ev = after.get("eval") or {}
    if b_bt or a_bt:
        lines.append(
            f"BT promote: {b_bt.get('promote')} → {a_bt.get('promote')}  "
            f"sig_ret: {b_bt.get('signal_return')} → {a_bt.get('signal_return')}"
        )
        lines.append(
            f"BT sharpe: {b_bt.get('sharpe')} → {a_bt.get('sharpe')}  "
            f"maxDD: {b_bt.get('max_drawdown')} → {a_bt.get('max_drawdown')}"
        )
    if b_ev or a_ev:
        lines.append(
            f"eval edge_al: {b_ev.get('edge_vs_always_long')} → {a_ev.get('edge_vs_always_long')}"
        )
    if not lines:
        lines.append("(no eval/backtest snapshots to compare — run eval && backtest)")
    return lines


def maybe_open_from_desk_report(experiment: str, *, source: str = "desk") -> Experiment | None:
    """Called after desk run: open ledger row if EXPERIMENT is real (single-open)."""
    if _is_noop_experiment(experiment):
        # Still reconcile orphans so desk never leaves a mess
        reconcile_open_experiments()
        return None
    hyp = experiment.strip()
    try:
        return open_experiment(hyp, source=source, replace_open=True)
    except ValueError:
        return None


def discipline_status() -> dict[str, Any]:
    """Summary for desk packet / agent close checklist."""
    open_ones = list_experiments(status="open", limit=20)
    completed = list_experiments(status="complete", limit=5)
    return {
        "open_count": len(open_ones),
        "open_ids": [e.id[:8] for e in open_ones],
        "open_hypotheses": [e.hypothesis[:80] for e in open_ones],
        "disciplined": len(open_ones) <= 1,
        "recent_complete": [
            {"id": e.id[:8], "outcome": e.outcome, "hyp": e.hypothesis[:60]}
            for e in completed[:3]
        ],
    }
