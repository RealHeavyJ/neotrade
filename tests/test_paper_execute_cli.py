"""CLI integration tests for paper-execute gates (confirm + RTH)."""

from __future__ import annotations

from argparse import Namespace
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from neotrade.broker.hours import SessionPhase, SessionStatus, get_session_status
from neotrade.main import _cmd_paper_execute, main

ET = ZoneInfo("America/New_York")


def _rth_status() -> SessionStatus:
    return get_session_status(datetime(2026, 7, 20, 11, 0, tzinfo=ET))


def _after_hours_status() -> SessionStatus:
    return get_session_status(datetime(2026, 7, 20, 17, 0, tzinfo=ET))


def test_paper_execute_without_confirm_returns_2():
    """Negative: missing --confirm → exit 2 (before session check)."""
    args = Namespace(confirm=False)
    assert _cmd_paper_execute(args) == 2


def test_paper_execute_outside_rth_returns_3():
    """Negative: outside RTH with --confirm → exit 3; no broker calls."""
    args = Namespace(
        confirm=True,
        config=None,
        model="models/signal.txt",
        buy_threshold=None,
        sell_threshold=None,
    )
    with (
        patch("neotrade.cli.broker_cmds.assert_execute_allowed", side_effect=RuntimeError("paper execute blocked: after-hours")),
        patch("neotrade.cli.broker_cmds.load_signals_for_paper") as load_sig,
        patch("neotrade.cli.broker_cmds.AlpacaPaperClient") as client_cls,
    ):
        code = _cmd_paper_execute(args)
    assert code == 3
    load_sig.assert_not_called()
    client_cls.assert_not_called()


def test_paper_execute_rth_with_no_intents_returns_0():
    """Positive: RTH + confirm + empty plan → 0 (allowed path, nothing to submit)."""
    from neotrade.broker.alpaca import AccountSnapshot
    from neotrade.broker.plan import TradePlan
    from neotrade.broker.risk import RiskLimits
    from neotrade.config.models import Ticker, TickersConfig

    args = Namespace(
        confirm=True,
        config=None,
        model="models/signal.txt",
        buy_threshold=None,
        sell_threshold=None,
    )
    cfg = TickersConfig(tickers=[Ticker(symbol="ARM", sleeve="growth")])
    risk = RiskLimits()
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
    empty_plan = TradePlan(equity=100_000, cash=100_000, notes=["no actionable intents"])

    with (
        patch("neotrade.cli.broker_cmds.assert_execute_allowed", return_value=_rth_status()),
        patch(
            "neotrade.cli.broker_cmds.load_signals_for_paper",
            return_value=(cfg, risk, [], {}),
        ),
        patch("neotrade.cli.broker_cmds.AlpacaPaperClient", return_value=client),
        patch("neotrade.cli.broker_cmds.build_trade_plan", return_value=empty_plan),
    ):
        code = _cmd_paper_execute(args)

    assert code == 0
    client.submit_market_order.assert_not_called()


def test_main_paper_execute_no_confirm_systemexit_2():
    """Negative: full CLI argv without --confirm → SystemExit 2."""
    with pytest.raises(SystemExit) as ei:
        main(["paper-execute"])
    assert ei.value.code == 2


def test_main_paper_execute_blocked_session_systemexit_3():
    """Negative: full CLI with --confirm outside RTH → SystemExit 3."""
    with (
        patch(
            "neotrade.cli.broker_cmds.assert_execute_allowed",
            side_effect=RuntimeError("paper execute blocked: closed"),
        ),
        pytest.raises(SystemExit) as ei,
    ):
        main(["paper-execute", "--confirm"])
    assert ei.value.code == 3


def test_session_phases_match_gate_policy():
    """Sanity: after-hours status is not executable; RTH is."""
    assert _after_hours_status().allow_execute is False
    assert _after_hours_status().phase == SessionPhase.AFTER_HOURS
    assert _rth_status().allow_execute is True
    assert _rth_status().phase == SessionPhase.RTH
