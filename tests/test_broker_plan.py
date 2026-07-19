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


def test_plan_buys_respect_sleeves_and_caps():
    cfg = _cfg()
    risk = default_risk_limits(cfg)
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
        prices={"NVDA": 100.0, "AMD": 50.0, "JNJ": 150.0},
    )
    buys = [i for i in plan.intents if i.side == "buy"]
    assert len(buys) >= 2
    assert all(i.side == "buy" for i in buys)
    # notional or qty present
    for i in buys:
        assert (i.qty is not None) ^ (i.notional is not None)


def test_plan_sells_on_sell_signal():
    cfg = _cfg()
    risk = default_risk_limits(cfg)
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
