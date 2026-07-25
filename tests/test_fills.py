"""Fill slip calibration unit tests."""

from __future__ import annotations

import pytest

from neotrade.broker.fills import (
    MIN_FILLS_FOR_CALIBRATION,
    calibrate_fills,
    effective_slip_bps,
    load_fills,
    make_observation,
    mid_from_quote,
    parse_filled_order,
    save_calibration,
    slip_bps_adverse,
    append_fill,
)


def test_slip_bps_adverse_buy_sell():
    assert slip_bps_adverse(side="buy", mid_px=100.0, fill_px=100.1) == pytest.approx(10.0)
    assert slip_bps_adverse(side="sell", mid_px=100.0, fill_px=99.9) == pytest.approx(10.0)
    # price improvement → negative
    assert slip_bps_adverse(side="buy", mid_px=100.0, fill_px=99.9) == pytest.approx(-10.0)


def test_mid_from_quote():
    assert mid_from_quote(10.0, 10.2) == pytest.approx(10.1)
    assert mid_from_quote(None, None, last=9.5) == pytest.approx(9.5)
    assert mid_from_quote(None, None) is None


def test_parse_filled_order():
    raw = {
        "id": "abc",
        "symbol": "aapl",
        "side": "buy",
        "status": "filled",
        "filled_avg_price": "150.25",
        "filled_qty": "2",
    }
    p = parse_filled_order(raw)
    assert p is not None
    assert p["symbol"] == "AAPL"
    assert p["fill_px"] == pytest.approx(150.25)
    assert parse_filled_order({"status": "canceled"}) is None


def test_calibrate_insufficient_n(tmp_path, monkeypatch):
    monkeypatch.setattr("neotrade.broker.fills.learning_dir", lambda: tmp_path)
    monkeypatch.setattr("neotrade.broker.fills.append_entry", lambda *a, **k: tmp_path / "e")
    for i in range(5):
        obs = make_observation(
            order_id=f"o{i}",
            symbol="AAA",
            side="buy",
            fill_px=100.05,
            mid_px=100.0,
            qty=1,
        )
        append_fill(obs)
    cal = calibrate_fills(min_n=20)
    assert cal.n == 5
    assert cal.recommended_slip_bps is None
    assert cal.median_slip_bps == pytest.approx(5.0)


def test_calibrate_ready_and_apply(tmp_path, monkeypatch):
    monkeypatch.setattr("neotrade.broker.fills.learning_dir", lambda: tmp_path)
    monkeypatch.setattr("neotrade.broker.fills.append_entry", lambda *a, **k: tmp_path / "e")
    monkeypatch.setattr(
        "neotrade.broker.fills.project_root",
        lambda: tmp_path,
    )
    # 20 fills at 8 bps adverse
    for i in range(MIN_FILLS_FOR_CALIBRATION):
        append_fill(
            make_observation(
                order_id=f"id{i}",
                symbol="BBB",
                side="sell",
                fill_px=99.92,  # 8 bps worse on sell from 100
                mid_px=100.0,
                qty=1,
            )
        )
    cal = calibrate_fills()
    assert cal.n == MIN_FILLS_FOR_CALIBRATION
    assert cal.recommended_slip_bps == pytest.approx(8.0)
    path = save_calibration(cal)
    assert path.is_file()
    assert effective_slip_bps(fallback=5.0) == pytest.approx(8.0)


def test_defaults_effective_slip_fallback(monkeypatch):
    from neotrade import defaults as D

    monkeypatch.setattr(
        "neotrade.broker.fills.load_saved_calibration",
        lambda **k: None,
    )
    assert D.effective_slip_bps() == D.BT_SLIP_BPS


def test_load_fills_dedupe(tmp_path, monkeypatch):
    monkeypatch.setattr("neotrade.broker.fills.learning_dir", lambda: tmp_path)
    monkeypatch.setattr("neotrade.broker.fills.append_entry", lambda *a, **k: tmp_path / "e")
    o1 = make_observation(
        order_id="same",
        symbol="X",
        side="buy",
        fill_px=10.0,
        mid_px=10.0,
    )
    o2 = make_observation(
        order_id="same",
        symbol="X",
        side="buy",
        fill_px=10.1,
        mid_px=10.0,
    )
    append_fill(o1)
    append_fill(o2)
    loaded = load_fills()
    assert len(loaded) == 1
    assert loaded[0].fill_px == pytest.approx(10.1)
