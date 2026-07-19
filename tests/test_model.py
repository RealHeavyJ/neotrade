from pathlib import Path

import numpy as np
import pandas as pd

from neotrade.signals.model import SignalModel
from neotrade.signals.score import score_universe, side_from_proba


def _synth(n: int = 150, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2023-01-03", periods=n)
    # mild momentum so model can fit something
    shock = rng.normal(0, 0.01, size=n)
    mom = np.zeros(n)
    for i in range(1, n):
        mom[i] = 0.3 * mom[i - 1] + shock[i]
    close = 50 * np.cumprod(1 + mom)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * 1.005
    low = np.minimum(open_, close) * 0.995
    volume = rng.integers(500_000, 2_000_000, size=n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


def test_side_thresholds():
    assert side_from_proba(0.7) == "buy"
    assert side_from_proba(0.3) == "sell"
    assert side_from_proba(0.5) == "hold"


def test_fit_predict_save_load(tmp_path: Path):
    frames = {"AAA": _synth(seed=1), "BBB": _synth(seed=2)}
    model = SignalModel(horizon=5)
    result = model.fit(frames, num_boost_round=40, early_stopping_rounds=10)
    assert result.n_train > 0
    assert result.n_valid > 0
    assert model.is_fitted
    proba = model.latest_signal(frames["AAA"])
    assert 0.0 <= proba <= 1.0

    path = tmp_path / "signal.txt"
    model.save(path)
    loaded = SignalModel.load(path)
    p2 = loaded.latest_signal(frames["AAA"])
    assert abs(p2 - proba) < 1e-6

    scored = score_universe(loaded, frames)
    assert len(scored.rows) == 2
    assert scored.rows[0].proba >= scored.rows[1].proba
