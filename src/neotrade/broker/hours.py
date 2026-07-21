"""US equity session clock for neotrade paper trading gates.

Policy (v1):
    * **Regular trading hours (RTH)** only for order submit.
    * No pre-market / after-hours execution (opt-in not offered).
    * Holidays: lightweight fixed set + weekends; not a full exchange calendar.

Longer term: agents may *monitor* quotes anytime the free Alpaca MD API allows;
this module only gates **plan messaging** and **execute**.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# US RTH for NYSE/Nasdaq equities (no early-close handling in v1)
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)

# Common full-market holidays (extend yearly as needed; not exhaustive early closes)
_US_MARKET_HOLIDAYS: frozenset[date] = frozenset(
    {
        date(2025, 1, 1),
        date(2025, 1, 20),
        date(2025, 2, 17),
        date(2025, 4, 18),
        date(2025, 5, 26),
        date(2025, 6, 19),
        date(2025, 7, 4),
        date(2025, 9, 1),
        date(2025, 11, 27),
        date(2025, 12, 25),
        date(2026, 1, 1),
        date(2026, 1, 19),
        date(2026, 2, 16),
        date(2026, 4, 3),
        date(2026, 5, 25),
        date(2026, 6, 19),
        date(2026, 7, 3),  # observed Independence Day
        date(2026, 9, 7),
        date(2026, 11, 26),
        date(2026, 12, 25),
        date(2027, 1, 1),
        date(2027, 1, 18),
        date(2027, 2, 15),
        date(2027, 3, 26),
        date(2027, 5, 31),
        date(2027, 6, 18),
        date(2027, 7, 5),  # observed
        date(2027, 9, 6),
        date(2027, 11, 25),
        date(2027, 12, 24),  # observed Christmas
    }
)


class SessionPhase(str, Enum):
    """Coarse US equity session phase in America/New_York."""

    CLOSED = "closed"  # weekend, holiday, or overnight outside extended
    PRE_MARKET = "pre_market"  # 04:00–09:30 ET (informational; execute blocked)
    RTH = "rth"  # 09:30–16:00 ET
    AFTER_HOURS = "after_hours"  # 16:00–20:00 ET (informational; execute blocked)


@dataclass(frozen=True)
class SessionStatus:
    """Snapshot of the US equity session for gates and UI.

    Attributes:
        now_et: Clock used for the decision (timezone-aware ET).
        phase: Coarse session phase.
        is_rth: True only during regular trading hours on a trading day.
        is_trading_day: True if weekday and not in holiday set.
        allow_execute: True only when paper market orders should be submitted.
        label: Short human label for CLI/dashboard.
        detail: One-line explanation.
        next_rth_open_et: Best-effort next RTH open (None if unknown).
    """

    now_et: datetime
    phase: SessionPhase
    is_rth: bool
    is_trading_day: bool
    allow_execute: bool
    label: str
    detail: str
    next_rth_open_et: datetime | None = None

    def summary_line(self) -> str:
        """Single line for CLI banners."""
        flag = "EXECUTE_OK" if self.allow_execute else "EXECUTE_BLOCKED"
        return (
            f"session={self.phase.value} et={self.now_et.strftime('%Y-%m-%d %H:%M %Z')} "
            f"{flag} — {self.detail}"
        )


def _as_et(when: datetime | None = None) -> datetime:
    if when is None:
        return datetime.now(tz=ET)
    if when.tzinfo is None:
        return when.replace(tzinfo=timezone.utc).astimezone(ET)
    return when.astimezone(ET)


def is_market_holiday(day: date) -> bool:
    """Return True if ``day`` is in the lightweight US full-holiday set."""
    return day in _US_MARKET_HOLIDAYS


def is_trading_day(day: date) -> bool:
    """Weekday and not a known full-market holiday."""
    if day.weekday() >= 5:
        return False
    return not is_market_holiday(day)


def _next_rth_open_after(now_et: datetime) -> datetime:
    """Next 09:30 ET on a trading day at or after ``now_et``'s calendar logic."""
    candidate = now_et.date()
    # If we're before open on a trading day, today's open; else walk forward.
    for _ in range(14):
        if is_trading_day(candidate):
            open_dt = datetime.combine(candidate, RTH_OPEN, tzinfo=ET)
            if now_et < open_dt:
                return open_dt
            if candidate == now_et.date() and now_et.time() < RTH_OPEN:
                return open_dt
        candidate = candidate + timedelta(days=1)
        open_dt = datetime.combine(candidate, RTH_OPEN, tzinfo=ET)
        if is_trading_day(candidate):
            return open_dt
    return datetime.combine(now_et.date() + timedelta(days=1), RTH_OPEN, tzinfo=ET)


def get_session_status(when: datetime | None = None) -> SessionStatus:
    """Compute session status for ``when`` (default: now).

    Args:
        when: Aware or naive datetime. Naive is treated as UTC.

    Returns:
        :class:`SessionStatus` with execute permission for RTH only.
    """
    now_et = _as_et(when)
    day = now_et.date()
    t = now_et.time()
    trading = is_trading_day(day)
    next_open = _next_rth_open_after(now_et)

    if not trading:
        reason = "weekend" if day.weekday() >= 5 else "market holiday"
        return SessionStatus(
            now_et=now_et,
            phase=SessionPhase.CLOSED,
            is_rth=False,
            is_trading_day=False,
            allow_execute=False,
            label="closed",
            detail=f"market closed ({reason}); paper execute blocked until RTH",
            next_rth_open_et=next_open,
        )

    if RTH_OPEN <= t < RTH_CLOSE:
        return SessionStatus(
            now_et=now_et,
            phase=SessionPhase.RTH,
            is_rth=True,
            is_trading_day=True,
            allow_execute=True,
            label="RTH",
            detail="regular trading hours — paper execute allowed",
            next_rth_open_et=None,
        )

    if time(4, 0) <= t < RTH_OPEN:
        return SessionStatus(
            now_et=now_et,
            phase=SessionPhase.PRE_MARKET,
            is_rth=False,
            is_trading_day=True,
            allow_execute=False,
            label="pre-market",
            detail="pre-market — neotrade blocks execute (RTH only; no extended hours)",
            next_rth_open_et=next_open,
        )

    if RTH_CLOSE <= t < time(20, 0):
        return SessionStatus(
            now_et=now_et,
            phase=SessionPhase.AFTER_HOURS,
            is_rth=False,
            is_trading_day=True,
            allow_execute=False,
            label="after-hours",
            detail="after-hours — neotrade blocks execute (RTH only; no extended hours)",
            next_rth_open_et=next_open,
        )

    return SessionStatus(
        now_et=now_et,
        phase=SessionPhase.CLOSED,
        is_rth=False,
        is_trading_day=True,
        allow_execute=False,
        label="closed",
        detail="overnight closed — paper execute blocked until next RTH open",
        next_rth_open_et=next_open,
    )


def assert_execute_allowed(when: datetime | None = None) -> SessionStatus:
    """Return status if execute is allowed; raise ``RuntimeError`` otherwise.

    Raises:
        RuntimeError: Outside US RTH (includes pre/post and closed).
    """
    status = get_session_status(when)
    if not status.allow_execute:
        nxt = ""
        if status.next_rth_open_et is not None:
            nxt = f" next_rth_open={status.next_rth_open_et.strftime('%Y-%m-%d %H:%M %Z')}"
        raise RuntimeError(
            f"paper execute blocked: {status.detail}.{nxt} "
            f"(session={status.phase.value})"
        )
    return status
