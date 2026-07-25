from neotrade.broker.alpaca import AccountSnapshot, Position
from neotrade.broker.plan import build_trade_plan
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
