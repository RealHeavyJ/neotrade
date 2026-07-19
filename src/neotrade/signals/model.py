"""LightGBM binary classifier for directional signals.

Training labels come from :func:`~neotrade.signals.features.build_labeled_frame`
(forward return > 0). Artifacts are plain-text boosters plus a ``.meta.json``
sidecar for feature names and horizon.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from neotrade.signals.features import FEATURE_COLUMNS, build_features, build_labeled_frame

DEFAULT_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "metric": "binary_logloss",
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "min_child_samples": 20,
    "verbosity": -1,
    "n_jobs": 1,
    "seed": 42,
}


@dataclass
class TrainResult:
    """Outcome of :meth:`SignalModel.fit`."""

    model: SignalModel
    metrics: dict[str, float]
    n_train: int
    n_valid: int


class SignalModel:
    """Binary LightGBM wrapper for neotrade directional signals.

    Args:
        booster: Optional pre-loaded booster (used by :meth:`load`).
        feature_names: Column order expected at predict time.
        horizon: Label forward-return horizon in bars.
        params: LightGBM train params (defaults favor small-memory Neo).
    """

    def __init__(
        self,
        booster: lgb.Booster | None = None,
        *,
        feature_names: list[str] | None = None,
        horizon: int = 5,
        params: dict[str, Any] | None = None,
    ) -> None:
        self.booster = booster
        self.feature_names = list(feature_names or FEATURE_COLUMNS)
        self.horizon = horizon
        self.params = dict(params or DEFAULT_PARAMS)

    @property
    def is_fitted(self) -> bool:
        """True when a booster is loaded or after successful :meth:`fit`."""
        return self.booster is not None

    def fit(
        self,
        frames: dict[str, pd.DataFrame],
        *,
        valid_fraction: float = 0.2,
        num_boost_round: int = 120,
        early_stopping_rounds: int = 20,
    ) -> TrainResult:
        """Train on a map of symbol → OHLCV with a time-based validation split.

        Args:
            frames: Per-symbol OHLCV history.
            valid_fraction: Fraction of unique dates held out at the end.
            num_boost_round: Max boosting rounds.
            early_stopping_rounds: Early stop patience (0 disables).

        Returns:
            :class:`TrainResult` with validation metrics.
        """
        if not frames:
            raise ValueError("frames must be non-empty")
        if not 0.05 <= valid_fraction <= 0.5:
            raise ValueError("valid_fraction must be in [0.05, 0.5]")

        parts: list[pd.DataFrame] = []
        for symbol, ohlcv in frames.items():
            try:
                labeled = build_labeled_frame(ohlcv, horizon=self.horizon)
            except ValueError:
                continue
            labeled = labeled.copy()
            labeled["symbol"] = symbol
            parts.append(labeled)
        if not parts:
            raise ValueError("no labeled rows produced from frames")

        data = pd.concat(parts, axis=0).sort_index()
        # Time-based split: last valid_fraction of unique dates for validation
        dates = data.index.unique().sort_values()
        cut = int(len(dates) * (1.0 - valid_fraction))
        cut = max(1, min(cut, len(dates) - 1))
        cut_date = dates[cut]
        train_df = data.loc[data.index < cut_date]
        valid_df = data.loc[data.index >= cut_date]
        if train_df.empty or valid_df.empty:
            raise ValueError("train/valid split produced empty set")

        x_train = train_df.loc[:, self.feature_names]
        y_train = train_df["label"].astype(int)
        x_valid = valid_df.loc[:, self.feature_names]
        y_valid = valid_df["label"].astype(int)

        dtrain = lgb.Dataset(x_train, label=y_train, feature_name=self.feature_names)
        dvalid = lgb.Dataset(x_valid, label=y_valid, reference=dtrain, feature_name=self.feature_names)

        callbacks: list[Any] = [lgb.log_evaluation(period=0)]
        if early_stopping_rounds > 0:
            callbacks.append(lgb.early_stopping(early_stopping_rounds, verbose=False))

        booster = lgb.train(
            self.params,
            dtrain,
            num_boost_round=num_boost_round,
            valid_sets=[dvalid],
            valid_names=["valid"],
            callbacks=callbacks,
        )
        self.booster = booster

        proba = booster.predict(x_valid)
        pred = (proba >= 0.5).astype(int)
        y = y_valid.to_numpy()
        acc = float((pred == y).mean()) if len(y) else 0.0
        pos_rate = float(y.mean()) if len(y) else 0.0
        metrics = {
            "valid_accuracy": acc,
            "valid_pos_rate": pos_rate,
            "best_iteration": float(booster.best_iteration or num_boost_round),
            "valid_logloss": float(booster.best_score.get("valid", {}).get("binary_logloss", np.nan)),
        }
        return TrainResult(
            model=self,
            metrics=metrics,
            n_train=len(train_df),
            n_valid=len(valid_df),
        )

    def predict_proba(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Return per-bar P(up) aligned to feature index."""
        if self.booster is None:
            raise RuntimeError("model is not fitted")
        feats = build_features(ohlcv)
        x = feats.loc[:, self.feature_names]
        proba = self.booster.predict(x)
        return pd.Series(proba, index=feats.index, name="signal_proba")

    def latest_signal(self, ohlcv: pd.DataFrame) -> float:
        """Return the most recent bar's signal probability."""
        series = self.predict_proba(ohlcv)
        if series.empty:
            raise ValueError("no feature rows available for signal")
        return float(series.iloc[-1])

    def save(self, path: Path | str) -> Path:
        """Persist booster + sidecar metadata next to ``path``.

        Writes ``path`` (booster text) and ``path.suffix + ".meta.json"``.
        """
        if self.booster is None:
            raise RuntimeError("cannot save unfitted model")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        model_path = path.with_suffix(".txt") if path.suffix == "" else path
        meta_path = model_path.with_suffix(model_path.suffix + ".meta.json")
        self.booster.save_model(str(model_path))
        meta = {
            "feature_names": self.feature_names,
            "horizon": self.horizon,
            "params": self.params,
            "best_iteration": self.booster.best_iteration,
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return model_path

    @classmethod
    def load(cls, path: Path | str) -> SignalModel:
        """Load booster and optional ``.meta.json`` sidecar."""
        path = Path(path)
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        feature_names = list(FEATURE_COLUMNS)
        horizon = 5
        params = dict(DEFAULT_PARAMS)
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            feature_names = list(meta.get("feature_names", feature_names))
            horizon = int(meta.get("horizon", horizon))
            params = dict(meta.get("params", params))
        booster = lgb.Booster(model_file=str(path))
        return cls(booster, feature_names=feature_names, horizon=horizon, params=params)
