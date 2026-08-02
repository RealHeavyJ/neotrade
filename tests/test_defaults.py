"""Production defaults consistency."""

from neotrade import defaults as D
from neotrade.signals.backtest import BacktestConfig


def test_backtest_production_matches_module_defaults():
    bt = BacktestConfig.production()
    assert bt.train_days == D.BT_TRAIN_DAYS
    assert bt.slip_bps == D.BT_SLIP_BPS
    assert bt.cost_bps == D.BT_COST_BPS
    assert bt.n_windows == D.BT_WINDOWS
    assert bt.use_regime is D.BT_USE_REGIME
    assert bt.use_regime is False
    assert bt.slip_stress_bps == D.BT_SLIP_STRESS_BPS


def test_train_days_for_period():
    assert D.train_days_for_period("2y") == 180
    assert D.train_days_for_period("1y") == 120
    assert D.train_days_for_period("5y") == 252
    assert D.train_days_for_period("2y", explicit=99) == 99


def test_data_period_default_is_2y():
    assert D.DATA_PERIOD == "2y"
    assert D.BT_PERIOD == "2y"


def test_promote_path_book_defaults():
    """top_n=7 + rebalance 14 tuned for bare 2y promote PASS."""
    assert D.RISK_TOP_N == 7
    assert D.BT_REBALANCE_EVERY == 14
    bt = BacktestConfig.production()
    assert bt.rebalance_every == 14
    assert bt.momentum_top_n == 7


def test_feature_exclude_vol_group():
    from neotrade.signals.features import FEATURE_GROUPS, model_feature_names

    assert D.FEATURE_EXCLUDE_GROUPS == ("vol",)
    names = model_feature_names()
    for col in FEATURE_GROUPS["vol"]:
        assert col not in names
    assert len(names) == len(model_feature_names(exclude_groups=())) - len(FEATURE_GROUPS["vol"])
