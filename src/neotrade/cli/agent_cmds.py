"""Agent CLI: advise, desk, experiment ledger."""
from __future__ import annotations

import argparse
import json
import sys

from neotrade.agents import run_advise, run_desk
from neotrade.agents.desk import DeskMockLLM
from neotrade.agents.llm import MockLLM, OllamaClient, OllamaConfig
from neotrade.cli.common import log, resolve_model_path
from neotrade.learning.experiments import (
    complete_all_open,
    complete_experiment,
    complete_latest_open,
    discipline_status,
    format_compare,
    get_experiment,
    list_experiments,
    open_experiment,
    open_from_desk,
    reconcile_open_experiments,
    snapshot_gates,
)
from neotrade.learning.policy import policy_blurb, record_advice_run

def cmd_advise(args: argparse.Namespace) -> int:
    """Run local LangGraph trading expert + performance analyst (Ollama)."""
    model_path = resolve_model_path(args.model)
    if args.mock_llm:
        llm = MockLLM()
    else:
        cfg = OllamaConfig.from_env()
        if args.llm_model:
            cfg = OllamaConfig(
                host=cfg.host,
                model=args.llm_model,
                temperature=cfg.temperature,
                timeout=cfg.timeout,
            )
        llm = OllamaClient(cfg)
        if not llm.ping():
            print(
                f"Ollama not reachable at {cfg.host}. "
                "Install Ollama, run `ollama serve`, pull a small model "
                f"(e.g. `ollama pull {cfg.model}`), or use --mock-llm.",
                file=sys.stderr,
            )
            return 1
    try:
        report = run_advise(
            model_path=model_path,
            config_path=args.config,
            include_account=not args.no_account,
            llm=llm,
        )
    except FileNotFoundError as exc:
        log.error("%s", exc)
        print(str(exc), file=sys.stderr)
        return 1
    except (RuntimeError, OSError, ValueError) as exc:
        log.error("advise failed: %s", exc)
        print(f"advise failed: {exc}", file=sys.stderr)
        return 1
    print(report.render())
    print(f"\npolicy: {policy_blurb()}")
    rating = getattr(args, "rating", None)
    notes = getattr(args, "notes", "") or ""
    try:
        path = record_advice_run(
            report,
            source="cli",
            rating=rating,
            notes=notes or "auto from neotrade advise",
        )
        print(f"logged: {path}")
    except (OSError, ValueError) as exc:
        log.warning("advice log skipped: %s", exc)
    log.info("advise done stance=%s model=%s rating=%s", report.stance, report.model, rating)
    return 1 if report.errors and not report.trader_raw else 0


def cmd_desk(args: argparse.Namespace) -> int:
    """Multi-agent desk: ops + quant + PM + critic (local LLM; no auto-execute)."""
    model_path = resolve_model_path(args.model)
    if args.mock_llm:
        llm: object = DeskMockLLM()
    else:
        cfg = OllamaConfig.from_env()
        if args.llm_model:
            cfg = OllamaConfig(
                host=cfg.host,
                model=args.llm_model,
                temperature=cfg.temperature,
                timeout=cfg.timeout,
            )
        llm = OllamaClient(cfg)
        if not llm.ping():
            print(
                f"Ollama not reachable at {cfg.host}. "
                f"Start Ollama or use --mock-llm.",
                file=sys.stderr,
            )
            return 1
    try:
        report = run_desk(
            model_path=model_path,
            config_path=args.config,
            include_account=not args.no_account,
            llm=llm,  # type: ignore[arg-type]
            save=not args.no_save,
        )
    except FileNotFoundError as exc:
        log.error("%s", exc)
        print(str(exc), file=sys.stderr)
        return 1
    except (RuntimeError, OSError, ValueError) as exc:
        log.error("desk failed: %s", exc)
        print(f"desk failed: {exc}", file=sys.stderr)
        return 1
    print(report.render())
    print(f"\npolicy: {policy_blurb()}")
    if not args.no_save:
        print("saved: data/learning/desk_latest.json")
        # Surface auto-opened experiment if any
        open_exps = list_experiments(status="open", limit=3)
        if open_exps and report.experiment and report.experiment.lower() not in {"none", "n/a"}:
            print(f"experiment open: {open_exps[0].id[:8]}  {open_exps[0].hypothesis[:70]}")
            print("  after you change config / re-run BT: neotrade experiment complete --latest")
    log.info(
        "desk done action=%s promote=%s allow_execute=%s",
        report.final_action,
        report.promote,
        report.allow_execute,
    )
    return 1 if report.errors and not report.critic_raw else 0


def cmd_experiment(args: argparse.Namespace) -> int:
    """Track desk/manual experiments → measured eval/BT outcomes."""
    action = args.experiment_action
    try:
        if action == "list":
            # Always reconcile so list never shows multi-open chaos
            abandoned = reconcile_open_experiments()
            if abandoned:
                print(f"reconciled: abandoned {len(abandoned)} duplicate open row(s)")
            rows = list_experiments(status=args.status, limit=args.limit)
            if not rows:
                print("no experiments")
                st = discipline_status()
                print(f"discipline: open_count={st['open_count']} ok={st['disciplined']}")
                return 0
            for e in rows:
                print(e.summary_line())
            st = discipline_status()
            print(f"discipline: open_count={st['open_count']} ok={st['disciplined']}")
            return 0 if st["disciplined"] else 1
        if action == "snapshot":
            snap = snapshot_gates()
            print(json.dumps(snap, indent=2))
            return 0
        if action == "open":
            if args.from_desk:
                exp = open_from_desk(notes=args.notes or "")
                if exp is None:
                    print("desk experiment is none/empty — nothing opened")
                    return 0
            else:
                if not args.text:
                    print("provide --text 'hypothesis' or --from-desk", file=sys.stderr)
                    return 2
                exp = open_experiment(args.text, source="cli", notes=args.notes or "")
            print(f"opened {exp.id}")
            print(f"  hypothesis: {exp.hypothesis}")
            print("  before snapshot captured (eval/BT if present)")
            print("  single-open rule: prior opens auto-abandoned if any")
            return 0
        if action == "complete":
            if getattr(args, "all", False):
                done = complete_all_open(
                    outcome=args.outcome or "abandoned",
                    notes=args.notes or "complete --all",
                )
                if not done:
                    print("no open experiments")
                    return 0
                for exp in done:
                    print(f"completed {exp.id[:8]} outcome={exp.outcome}")
                print("discipline: open_count=0 ok=True")
                return 0
            if args.latest:
                exp = complete_latest_open(outcome=args.outcome, notes=args.notes or "")
                if exp is None:
                    print("no open experiments", file=sys.stderr)
                    return 1
            else:
                if not args.id:
                    print("provide --id PREFIX, --latest, or --all", file=sys.stderr)
                    return 2
                exp = complete_experiment(args.id, outcome=args.outcome, notes=args.notes or "")
            print(f"completed {exp.id[:8]} outcome={exp.outcome}")
            for line in format_compare(exp.before, exp.after):
                print(f"  {line}")
            # sweep any remaining orphans
            extra = complete_all_open(
                outcome="abandoned",
                notes="auto-sweep after complete",
            )
            if extra:
                print(f"swept {len(extra)} remaining open row(s) → abandoned")
            return 0
        if action == "reconcile":
            abandoned = reconcile_open_experiments()
            print(f"abandoned={len(abandoned)}")
            for e in abandoned:
                print(f"  {e.id[:8]} → abandoned")
            st = discipline_status()
            print(f"discipline: open_count={st['open_count']} ok={st['disciplined']}")
            if st["open_count"] == 1:
                print(f"kept open: {st['open_ids'][0]}  {st['open_hypotheses'][0]}")
            return 0 if st["disciplined"] else 1
        if action == "show":
            if not args.id:
                print("provide --id", file=sys.stderr)
                return 2
            exp = get_experiment(args.id)
            if exp is None:
                print("not found", file=sys.stderr)
                return 1
            print(json.dumps(exp.to_dict(), indent=2))
            if exp.status == "complete":
                for line in format_compare(exp.before, exp.after):
                    print(line)
            return 0
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"unknown experiment action: {action}", file=sys.stderr)
    return 2


