"""Unit tests for quote monitor poller (P4)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from neotrade.broker.hours import SessionPhase, SessionStatus, get_session_status
from neotrade.config.models import Ticker, TickersConfig
from neotrade.data.quotes import QuoteRow, QuoteSnapshot
from neotrade.monitor.poller import (
    MIN_INTERVAL_S,
    MonitorConfig,
    QuoteMonitor,
)

ET = ZoneInfo("America/New_York")


def _session_rth() -> SessionStatus:
    return get_session_status(datetime(2026, 7, 20, 11, 0, tzinfo=ET))


def _snap(prices: dict[str, float], feed: str = "iex") -> QuoteSnapshot:
    rows = [
        QuoteRow(symbol=s, price=p, source=f"alpaca:{feed}", sleeve="growth")
        for s, p in sorted(prices.items())
    ]
    return QuoteSnapshot(rows=rows, feed=feed, errors=[])


def test_poll_once_positive():
    cfg = TickersConfig(tickers=[Ticker(symbol="ARM"), Ticker(symbol="TSM")])
    snaps = [_snap({"ARM": 100.0, "TSM": 200.0})]

    def fetch(*_a, **_k):
        return snaps[0]

    mon = QuoteMonitor(
        MonitorConfig(interval_s=15, move_pct=1.0, log_path=None),
        cfg=cfg,
        fetch_fn=fetch,
        session_fn=_session_rth,
    )
    tick = mon.poll_once()
    assert tick.tick_index == 1
    assert tick.priced_count() == 2
    assert tick.session.phase == SessionPhase.RTH
    assert tick.moves == []
    assert "tick=1" in tick.summary_line()


def test_move_alert_when_threshold_crossed():
    """Positive: large move vs prior tick produces MoveAlert."""
    cfg = TickersConfig(tickers=[Ticker(symbol="ARM")])
    prices_seq = [{"ARM": 100.0}, {"ARM": 103.0}]  # +3%
    idx = {"i": 0}

    def fetch(*_a, **_k):
        p = prices_seq[min(idx["i"], len(prices_seq) - 1)]
        idx["i"] += 1
        return _snap(p)

    mon = QuoteMonitor(
        MonitorConfig(interval_s=5, move_pct=1.0, log_path=None),
        cfg=cfg,
        fetch_fn=fetch,
        session_fn=_session_rth,
        sleep_fn=lambda _s: None,
    )
    t1 = mon.poll_once()
    assert t1.moves == []
    t2 = mon.poll_once()
    assert len(t2.moves) == 1
    assert t2.moves[0].symbol == "ARM"
    assert abs(t2.moves[0].pct - 3.0) < 0.01


def test_no_move_below_threshold():
    """Negative: small move does not alert."""
    cfg = TickersConfig(tickers=[Ticker(symbol="ARM")])
    prices_seq = [{"ARM": 100.0}, {"ARM": 100.5}]  # +0.5%
    idx = {"i": 0}

    def fetch(*_a, **_k):
        p = prices_seq[min(idx["i"], len(prices_seq) - 1)]
        idx["i"] += 1
        return _snap(p)

    mon = QuoteMonitor(
        MonitorConfig(interval_s=5, move_pct=1.0, log_path=None),
        cfg=cfg,
        fetch_fn=fetch,
        session_fn=_session_rth,
        sleep_fn=lambda _s: None,
    )
    mon.poll_once()
    t2 = mon.poll_once()
    assert t2.moves == []


def test_interval_clamped_to_minimum():
    """Negative: sub-min interval is raised (rate-limit safety)."""
    cfg = MonitorConfig(interval_s=1.0)
    assert cfg.clamped_interval() == MIN_INTERVAL_S


def test_iter_ticks_respects_max_ticks():
    cfg = TickersConfig(tickers=[Ticker(symbol="ARM")])
    sleeps: list[float] = []

    def fetch(*_a, **_k):
        return _snap({"ARM": 100.0})

    mon = QuoteMonitor(
        MonitorConfig(interval_s=10, log_path=None),
        cfg=cfg,
        fetch_fn=fetch,
        session_fn=_session_rth,
        sleep_fn=lambda s: sleeps.append(s),
    )
    ticks = list(mon.iter_ticks(max_ticks=3))
    assert len(ticks) == 3
    assert ticks[-1].tick_index == 3
    # sleep between ticks only (not after last)
    assert len(sleeps) == 2
    assert sleeps[0] == 10.0


def test_monitor_never_calls_broker_execute():
    """Safety: poller has no execute path (structural)."""
    import neotrade.monitor.poller as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "submit_market_order" not in src
    assert "paper-execute" not in src


def test_jsonl_log_written(tmp_path: Path):
    cfg = TickersConfig(tickers=[Ticker(symbol="ARM")])
    log = tmp_path / "mon.jsonl"

    def fetch(*_a, **_k):
        return _snap({"ARM": 50.0})

    mon = QuoteMonitor(
        MonitorConfig(interval_s=5, log_path=log),
        cfg=cfg,
        fetch_fn=fetch,
        session_fn=_session_rth,
    )
    mon.poll_once()
    assert log.is_file()
    line = log.read_text(encoding="utf-8").strip()
    assert "ARM" in line
    assert "tick_index" in line
