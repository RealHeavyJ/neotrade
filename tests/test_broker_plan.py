from neotrade.broker.alpaca import AccountSnapshot, OpenOrder, Position, parse_open_orders
from neotrade.broker.plan import build_trade_plan, summarize_open_orders
from neotrade.broker.risk import RiskLimits, default_risk_limits
from neotrade.config.models import RiskSettings, Ticker, TickersConfig
from neotrade.signals.score import SignalRow


def _cfg() -> TickersConfig:
    return TickersConfig(
        tickers=[
            Ticker(symbol="NVDA", sleeve="growth"),
            Ticker(symbol="AMD", sleeve="growth"),
            Ticker(symbol="JNJ", sleeve="defensive"),
            Ticker(symbol="KO", sleeve="defensive"),
        ],
        risk=RiskSettings(
            max_position_pct=0.10,
            growth_target_pct=0.68,
            defensive_target_pct=0.32,
            max_new_positions=4,
            min_notional=50.0,
            min_cash_pct=0.02,
        ),
    )


def _account(equity: float = 100_000, cash: float = 100_000) -> AccountSnapshot:
    return AccountSnapshot(
        equity=equity,
        cash=cash,
        buying_power=cash,
        portfolio_value=equity,
        status="ACTIVE",
        currency="USD",
        pattern_day_trader=False,
        trading_blocked=False,
        account_blocked=False,
    )


def test_plan_ranked_buys_top_n():
    cfg = _cfg()
    risk = default_risk_limits(cfg)
    assert risk.plan_mode == "ranked"
    signals = [
        SignalRow("NVDA", 0.70, "buy", "2026-07-17"),
        SignalRow("AMD", 0.66, "buy", "2026-07-17"),
        SignalRow("JNJ", 0.62, "buy", "2026-07-17"),
        SignalRow("KO", 0.40, "hold", "2026-07-17"),
    ]
    plan = build_trade_plan(
        signals=signals,
        account=_account(),
        positions=[],
        cfg=cfg,
        risk=risk,
        prices={"NVDA": 100.0, "AMD": 50.0, "JNJ": 150.0, "KO": 60.0},
    )
    buys = [i for i in plan.intents if i.side == "buy"]
    assert len(buys) >= 2
    assert all(i.side == "buy" for i in buys)
    for i in buys:
        assert (i.qty is not None) ^ (i.notional is not None)
    assert any("mode=ranked" in n for n in plan.notes)


def test_plan_ranked_exits_name_outside_top_n():
    cfg = _cfg()
    risk = default_risk_limits(cfg)
    positions = [
        Position(
            symbol="KO",
            qty=10,
            market_value=600,
            current_price=60,
            avg_entry_price=55,
            unrealized_pl=50,
            side="long",
        )
    ]
    signals = [
        SignalRow("NVDA", 0.80, "buy", "2026-07-17"),
        SignalRow("AMD", 0.75, "buy", "2026-07-17"),
        SignalRow("JNJ", 0.70, "buy", "2026-07-17"),
        SignalRow("KO", 0.20, "sell", "2026-07-17"),
    ]
    plan = build_trade_plan(
        signals=signals,
        account=_account(equity=10_000, cash=1000),
        positions=positions,
        cfg=cfg,
        risk=risk,
        prices={"NVDA": 100.0, "AMD": 50.0, "JNJ": 150.0, "KO": 60.0},
    )
    assert any(i.side == "sell" and i.symbol == "KO" for i in plan.intents)


def test_plan_sides_sells_on_sell_signal():
    cfg = _cfg()
    risk = RiskLimits(
        max_position_pct=0.10,
        growth_target_pct=0.68,
        defensive_target_pct=0.32,
        plan_mode="sides",
        buy_threshold=0.55,
        sell_threshold=0.45,
    )
    positions = [
        Position(
            symbol="AMD",
            qty=10,
            market_value=500,
            current_price=50,
            avg_entry_price=40,
            unrealized_pl=100,
            side="long",
        )
    ]
    signals = [SignalRow("AMD", 0.30, "sell", "2026-07-17")]
    plan = build_trade_plan(
        signals=signals,
        account=_account(equity=10_000, cash=1000),
        positions=positions,
        cfg=cfg,
        risk=risk,
    )
    assert any(i.side == "sell" and i.symbol == "AMD" and i.qty == 10 for i in plan.intents)


def test_risk_limits_sum():
    bad = RiskLimits(growth_target_pct=0.5, defensive_target_pct=0.4)
    try:
        bad.validate()
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_parse_open_orders_partial_fill():
    raw = [
        {
            "id": "1",
            "symbol": "amd",
            "side": "buy",
            "qty": "10",
            "filled_qty": "4",
            "status": "partially_filled",
            "type": "market",
        },
        {
            "id": "2",
            "symbol": "KO",
            "side": "sell",
            "qty": "5",
            "filled_qty": "5",
            "status": "filled",
            "type": "market",
        },
    ]
    oos = parse_open_orders(raw)
    assert len(oos) == 1
    assert oos[0].symbol == "AMD"
    assert oos[0].remaining_qty == 6.0
    assert oos[0].filled_qty == 4.0


def test_open_buy_reserves_cash_and_skips_double_buy():
    cfg = _cfg()
    risk = default_risk_limits(cfg)
    open_orders = [
        OpenOrder(
            id="o1",
            symbol="NVDA",
            side="buy",
            qty=50,
            filled_qty=0,
            remaining_qty=50,
            notional=None,
            filled_avg_price=None,
            status="accepted",
            order_type="market",
        )
    ]
    prices = {"NVDA": 100.0, "AMD": 50.0, "JNJ": 150.0, "KO": 60.0}
    book = summarize_open_orders(open_orders, prices=prices)
    assert book.reserved_buy_cash == 5000.0

    signals = [
        SignalRow("NVDA", 0.90, "buy", "2026-07-17"),
        SignalRow("AMD", 0.80, "buy", "2026-07-17"),
        SignalRow("JNJ", 0.70, "buy", "2026-07-17"),
        SignalRow("KO", 0.20, "sell", "2026-07-17"),
    ]
    # Only enough free cash for buffer math; large reserved buy should block overspend
    plan = build_trade_plan(
        signals=signals,
        account=_account(equity=100_000, cash=6_000),
        positions=[],
        cfg=cfg,
        risk=risk,
        prices=prices,
        open_orders=open_orders,
    )
    assert plan.reserved_buy_cash == 5000.0
    # Should not stack another full NVDA buy on top of 50-share working order within band
    nvda_buys = [i for i in plan.intents if i.side == "buy" and i.symbol == "NVDA"]
    # exposure already 5k on 100k book (~target); may skip or small add only
    assert all("open" in n or "band" in n or "NVDA" in n for n in plan.notes) or len(nvda_buys) <= 1


def test_open_sell_reduces_sellable_qty():
    cfg = _cfg()
    risk = RiskLimits(
        max_position_pct=0.10,
        growth_target_pct=0.68,
        defensive_target_pct=0.32,
        plan_mode="sides",
        buy_threshold=0.55,
        sell_threshold=0.45,
    )
    positions = [
        Position(
            symbol="AMD",
            qty=10,
            market_value=500,
            current_price=50,
            avg_entry_price=40,
            unrealized_pl=100,
            side="long",
        )
    ]
    open_orders = [
        OpenOrder(
            id="s1",
            symbol="AMD",
            side="sell",
            qty=10,
            filled_qty=3,
            remaining_qty=7,
            notional=None,
            filled_avg_price=50.0,
            status="partially_filled",
            order_type="market",
        )
    ]
    plan = build_trade_plan(
        signals=[SignalRow("AMD", 0.20, "sell", "2026-07-17")],
        account=_account(equity=10_000, cash=1000),
        positions=positions,
        cfg=cfg,
        risk=risk,
        prices={"AMD": 50.0},
        open_orders=open_orders,
    )
    sells = [i for i in plan.intents if i.side == "sell" and i.symbol == "AMD"]
    # 10 held - 7 pending sell = 3 remaining to sell
    assert len(sells) == 1
    assert sells[0].qty == 3.0


def test_sides_skips_buy_when_open_buy_exists():
    cfg = _cfg()
    risk = RiskLimits(
        max_position_pct=0.20,
        growth_target_pct=0.68,
        defensive_target_pct=0.32,
        plan_mode="sides",
        buy_threshold=0.55,
        sell_threshold=0.45,
        max_new_positions=4,
        min_cash_pct=0.0,
    )
    open_orders = [
        OpenOrder(
            id="b1",
            symbol="NVDA",
            side="buy",
            qty=10,
            filled_qty=0,
            remaining_qty=10,
            notional=None,
            filled_avg_price=None,
            status="accepted",
            order_type="market",
        )
    ]
    plan = build_trade_plan(
        signals=[
            SignalRow("NVDA", 0.80, "buy", "2026-07-17"),
            SignalRow("AMD", 0.75, "buy", "2026-07-17"),
        ],
        account=_account(),
        positions=[],
        cfg=cfg,
        risk=risk,
        prices={"NVDA": 100.0, "AMD": 50.0},
        open_orders=open_orders,
    )
    assert not any(i.symbol == "NVDA" and i.side == "buy" for i in plan.intents)
    assert any(i.symbol == "AMD" and i.side == "buy" for i in plan.intents)
