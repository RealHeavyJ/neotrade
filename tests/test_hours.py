from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from neotrade.broker.hours import (
    ET,
    SessionPhase,
    assert_execute_allowed,
    get_session_status,
    is_trading_day,
)

ETZ = ZoneInfo("America/New_York")


def _et(y, m, d, hh, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=ETZ)


def test_weekday_rth_allows_execute():
    # 2026-07-20 is Monday
    st = get_session_status(_et(2026, 7, 20, 10, 0))
    assert st.phase == SessionPhase.RTH
    assert st.is_rth is True
    assert st.allow_execute is True
    assert "EXECUTE_OK" in st.summary_line()


def test_after_hours_blocks_execute():
    st = get_session_status(_et(2026, 7, 20, 17, 0))
    assert st.phase == SessionPhase.AFTER_HOURS
    assert st.allow_execute is False
    with pytest.raises(RuntimeError, match="blocked"):
        assert_execute_allowed(_et(2026, 7, 20, 17, 0))


def test_pre_market_blocks_execute():
    st = get_session_status(_et(2026, 7, 20, 8, 0))
    assert st.phase == SessionPhase.PRE_MARKET
    assert st.allow_execute is False


def test_weekend_closed():
    # 2026-07-19 Sunday
    st = get_session_status(_et(2026, 7, 19, 12, 0))
    assert st.phase == SessionPhase.CLOSED
    assert st.is_trading_day is False
    assert st.allow_execute is False
    assert st.next_rth_open_et is not None


def test_holiday_closed():
    # 2026-07-03 observed Independence Day in our table
    st = get_session_status(_et(2026, 7, 3, 11, 0))
    assert st.allow_execute is False
    assert st.is_trading_day is False


def test_rth_boundary_open_inclusive():
    st = get_session_status(_et(2026, 7, 20, 9, 30))
    assert st.allow_execute is True


def test_rth_boundary_close_exclusive():
    st = get_session_status(_et(2026, 7, 20, 16, 0))
    assert st.allow_execute is False
    assert st.phase == SessionPhase.AFTER_HOURS


def test_is_trading_day_weekend():
    assert is_trading_day(_et(2026, 7, 18, 12).date()) is False  # Saturday


def test_assert_execute_allowed_rth_ok():
    st = assert_execute_allowed(_et(2026, 7, 20, 11, 0))
    assert st.allow_execute is True
    assert st.now_et.tzinfo is not None
