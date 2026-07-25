"""Desk multi-agent unit tests."""

from __future__ import annotations

from pathlib import Path

from neotrade.agents.desk import DeskMockLLM, parse_desk_report, run_desk
from neotrade.agents.desk_context import DeskPacket
from neotrade.broker.hours import get_session_status
from neotrade.signals.score import SignalRow


def _packet(**kwargs) -> DeskPacket:
    st = get_session_status()
    base = dict(
        ts="2026-07-25T00:00:00Z",
        session_line=st.summary_line(),
        allow_execute=False,
        universe="test",
        regime_line="regime=neutral",
        account_lines=["equity=$100,000 cash=$20,000 filled_positions=2"],
        signal_lines=["NVDA proba=0.70 side=buy"],
        plan_lines=["mode=ranked top_n=5"],
        eval_lines=["edge_vs_always_long=0.02"],
        backtest_lines=["promote=True", "full_gate_pass=True"],
        promote_ok=True,
        notes=[],
        top_signals=[SignalRow("NVDA", 0.7, "buy", "2026-07-25")],
    )
    base.update(kwargs)
    return DeskPacket(**base)


def test_parse_forces_no_promote_when_packet_fail():
    pkt = _packet(promote_ok=False, allow_execute=True)
    report = parse_desk_report(
        packet=pkt,
        ops="EXECUTE_ALLOWED: yes\nOPS_ACTION: go\n",
        quant="PROMOTE: yes\nTRAIN_REC: none\nEXPERIMENT: none\n",
        pm="PM_ACTION: execute_plan\nCONFIDENCE: high\n",
        critic="FINAL_ACTION: execute_plan\nFINAL_CONFIDENCE: high\nOVERRIDE: none\nHUMAN_TODO: execute\n",
        model="mock",
    )
    assert report.promote == "no"
    assert report.final_action != "execute_plan"


def test_parse_blocks_execute_off_rth():
    pkt = _packet(promote_ok=True, allow_execute=False)
    report = parse_desk_report(
        packet=pkt,
        ops="EXECUTE_ALLOWED: no\n",
        quant="PROMOTE: yes\nTRAIN_REC: none\nEXPERIMENT: none\n",
        pm="PM_ACTION: execute_plan\nCONFIDENCE: high\n",
        critic="FINAL_ACTION: execute_plan\nFINAL_CONFIDENCE: high\nOVERRIDE: none\nHUMAN_TODO: x\n",
        model="mock",
    )
    assert report.final_action in {"hold", "research_only", "rebalance", "trim"}


def test_run_desk_with_mock_and_injected_packet(tmp_path: Path, monkeypatch):
    from neotrade.agents import desk as desk_mod

    monkeypatch.setattr(desk_mod, "project_root", lambda: tmp_path)
    (tmp_path / "data" / "learning").mkdir(parents=True)
    pkt = _packet(promote_ok=True, allow_execute=False)
    report = run_desk(
        model_path=tmp_path / "missing.txt",
        llm=DeskMockLLM(),
        packet=pkt,
        save=True,
    )
    assert report.ops_raw
    assert report.quant_raw
    assert report.pm_raw
    assert report.critic_raw
    assert report.human_todo
    assert (tmp_path / "data" / "learning" / "desk_latest.json").is_file()
