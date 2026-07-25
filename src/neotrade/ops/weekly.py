"""Weekly promote pipeline: fetch → train → eval → backtest → desk.

Never places orders. Exit codes (CLI):
  0 — all steps ok and bare backtest promote PASS
  1 — hard failure on fetch/train/eval (or desk when required)
  2 — pipeline ran but backtest promote FAIL
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from neotrade.config.load import project_root
from neotrade.learning.log import append_entry, learning_dir
from neotrade.logging_config import get_logger

log = get_logger("ops.weekly")

# Steps that must succeed for a usable weekly run
_HARD_STEPS = ("fetch", "train", "eval", "backtest")


@dataclass
class StepResult:
    """One pipeline step outcome."""

    name: str
    argv: list[str]
    exit_code: int
    ok: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WeeklyResult:
    """Summary of a weekly promote run."""

    ts: str
    steps: list[StepResult] = field(default_factory=list)
    promote: bool = False
    exit_code: int = 1
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "steps": [s.to_dict() for s in self.steps],
            "promote": self.promote,
            "exit_code": self.exit_code,
            "notes": list(self.notes),
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"weekly @ {self.ts}  promote={self.promote}  exit={self.exit_code}",
        ]
        for s in self.steps:
            flag = "ok" if s.ok else f"FAIL({s.exit_code})"
            lines.append(f"  {s.name}: {flag}  {' '.join(s.argv)}")
        for n in self.notes:
            lines.append(f"note: {n}")
        return lines


Runner = Callable[[Sequence[str]], int]


def _default_runner(argv: Sequence[str]) -> int:
    """Invoke ``neotrade`` CLI as a subprocess (isolated, real exit codes)."""
    cmd = [sys.executable, "-m", "neotrade", *argv]
    log.info("weekly step: %s", " ".join(cmd))
    proc = subprocess.run(cmd, check=False)
    return int(proc.returncode)


def _ollama_up(timeout: float = 2.0) -> bool:
    try:
        import urllib.request

        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return int(resp.status) == 200
    except (OSError, ValueError):
        return False


def run_weekly_promote(
    *,
    runner: Runner | None = None,
    force_fetch: bool = True,
    skip_desk: bool = False,
    mock_llm: bool | None = None,
    skip_signals: bool = False,
    config: str | None = None,
    save: bool = True,
) -> WeeklyResult:
    """Run production weekly cadence. Never executes trades.

    Args:
        runner: Injected command runner (argv without ``neotrade`` prefix).
        force_fetch: Pass ``--force`` to fetch.
        skip_desk: Skip desk step (still runs BT).
        mock_llm: Force desk ``--mock-llm``; default auto if Ollama down.
        skip_signals: Skip post-BT signals sanity.
        config: Optional ``--config`` path for all steps that accept it.
        save: Write ``weekly_latest.json`` + learning log.
    """
    run = runner or _default_runner
    ts = datetime.now(UTC).isoformat()
    result = WeeklyResult(ts=ts)
    result.notes.append("never executes; paper-execute is not in this pipeline")
    result.notes.append("bare backtest = production defaults (see neotrade.defaults)")

    def cfg_args() -> list[str]:
        return ["--config", config] if config else []

    def step(name: str, argv: list[str], *, required: bool = True) -> int:
        code = int(run(argv))
        ok = code == 0
        # backtest: 0=promote, 2=gate fail (still a completed BT)
        if name == "backtest":
            ok_completed = code in (0, 2)
            result.steps.append(StepResult(name=name, argv=argv, exit_code=code, ok=ok_completed))
            result.promote = code == 0
            if code == 0:
                result.notes.append("backtest promote=PASS")
            elif code == 2:
                result.notes.append("backtest promote=FAIL (exit 2)")
            else:
                result.notes.append(f"backtest hard fail exit={code}")
            return code
        result.steps.append(StepResult(name=name, argv=argv, exit_code=code, ok=ok))
        if not ok and required:
            result.notes.append(f"hard stop at {name} exit={code}")
        return code

    # 1) session (informational)
    step("session", ["session"], required=False)

    # 2) fetch
    fetch_argv = ["fetch", *cfg_args()]
    if force_fetch:
        fetch_argv.append("--force")
    if step("fetch", fetch_argv) != 0:
        result.exit_code = 1
        return _finalize(result, save=save)

    # 3) train
    if step("train", ["train", *cfg_args()]) != 0:
        result.exit_code = 1
        return _finalize(result, save=save)

    # 4) eval
    if step("eval", ["eval", *cfg_args()]) != 0:
        result.exit_code = 1
        return _finalize(result, save=save)

    # 5) bare backtest (promote path)
    bt_code = step("backtest", ["backtest", *cfg_args()])
    if bt_code not in (0, 2):
        result.exit_code = 1
        return _finalize(result, save=save)

    # 6) signals sanity (non-fatal)
    if not skip_signals:
        step("signals", ["signals", *cfg_args()], required=False)

    # 7) desk (prefer real LLM; mock if Ollama down)
    if not skip_desk:
        use_mock = mock_llm if mock_llm is not None else (not _ollama_up())
        desk_argv = ["desk", *cfg_args()]
        if use_mock:
            desk_argv.append("--mock-llm")
            result.notes.append("desk using --mock-llm (Ollama down or forced)")
        desk_code = step("desk", desk_argv, required=False)
        if desk_code != 0:
            result.notes.append(f"desk failed exit={desk_code} (non-fatal)")
        # open experiment from desk if any (non-fatal)
        step("experiment_open", ["experiment", "open", "--from-desk"], required=False)
        step("experiment_list", ["experiment", "list", "--status", "open"], required=False)

    # exit: promote drives 0 vs 2
    result.exit_code = 0 if result.promote else 2
    return _finalize(result, save=save)


def _finalize(result: WeeklyResult, *, save: bool) -> WeeklyResult:
    if save:
        path = learning_dir() / "weekly_latest.json"
        path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        append_entry("weekly_promote", result.to_dict())
        result.notes.append(f"saved: {path}")
        log.info(
            "weekly done promote=%s exit=%s path=%s",
            result.promote,
            result.exit_code,
            path,
        )
    return result


def weekly_log_path() -> Path:
    return project_root() / "data" / "learning" / "weekly_cron.log"
