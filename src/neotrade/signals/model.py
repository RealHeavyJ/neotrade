"""LightGBM binary classifier for directional / relative signals.

Training builds a multi-symbol panel with lagging features plus same-day
cross-sectional ranks. Default labels are **relative** (beat cross-sectional
median forward return), aligned with ranking names by score.

Artifacts: booster text file + ``.meta.json`` (features, horizon, label_mode).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from neotrade.signals.features import (
    ALL_MODEL_FEATURES,
    CS_FEATURE_COLUMNS,
    FEATURE_COLUMNS,
    add_cross_section_features,
    build_features,
    build_labeled_frame,
    model_feature_names,
)

DEFAULT_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "metric": "binary_logloss",
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.85,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "min_child_samples": 25,
    "verbosity": -1,
    "n_jobs": 1,
    "seed": 42,
    "is_unbalance": True,
}


@dataclass
class TrainResult:
    """Outcome of :meth:`SignalModel.fit`."""

    model: SignalModel
    metrics: dict[str, float]
    n_train: int
    n_valid: int


class SignalModel:
    """Binary LightGBM wrapper for neotrade signals.

    Args:
        booster: Optional pre-loaded booster (used by :meth:`load`).
        feature_names: Column order at predict time.
        horizon: Forward-return label horizon in bars.
        params: LightGBM train params.
        label_mode: ``relative`` (default) or ``absolute``.
        include_cs: Include cross-sectional rank features when training/scoring
            a multi-name universe.
    """

    def __init__(
        self,
        booster: lgb.Booster | None = None,
        *,
        feature_names: list[str] | None = None,
        horizon: int = 5,
        params: dict[str, Any] | None = None,
        label_mode: str = "relative",
        include_cs: bool = True,
    ) -> None:
        self.include_cs = include_cs
        self.label_mode = label_mode if label_mode in {"relative", "absolute"} else "relative"
        default_feats = model_feature_names(include_cs=include_cs)
        self.feature_names = list(feature_names or default_feats)
        self.horizon = horizon
        self.params = dict(params or DEFAULT_PARAMS)
        self.booster = booster
        # last panel CS state for single-symbol predict (median ranks = 0.5)
        self._cs_neutral = 0.5

    @property
    def is_fitted(self) -> bool:
        """True when a booster is loaded or after successful :meth:`fit`."""
        return self.booster is not None

    def _build_panel(self, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
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
        panel = pd.concat(parts, axis=0).sort_index()
        if self.include_cs:
            panel = add_cross_section_features(
                panel,
                relative_label=(self.label_mode == "relative"),
            )
        elif self.label_mode == "relative":
            # relative without CS ranks still needs relative labels
            panel = add_cross_section_features(panel, relative_label=True)
            # drop CS cols if not in feature_names
            drop = [c for c in CS_FEATURE_COLUMNS if c in panel.columns and c not in self.feature_names]
            panel = panel.drop(columns=drop, errors="ignore")
        return panel

    def fit(
        self,
        frames: dict[str, pd.DataFrame],
        *,
        valid_fraction: float = 0.2,
        num_boost_round: int = 160,
        early_stopping_rounds: int = 25,
    ) -> TrainResult:
        """Train on a multi-symbol panel with a time-based validation split."""
        if not frames:
            raise ValueError("frames must be non-empty")
        if not 0.05 <= valid_fraction <= 0.5:
            raise ValueError("valid_fraction must be in [0.05, 0.5]")

        data = self._build_panel(frames)
        # ensure feature columns exist
        for col in self.feature_names:
            if col not in data.columns:
                data[col] = self._cs_neutral if col.startswith("cs_") else 0.0

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
        dvalid = lgb.Dataset(
            x_valid, label=y_valid, reference=dtrain, feature_name=self.feature_names
        )

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
            "valid_logloss": float(
                booster.best_score.get("valid", {}).get("binary_logloss", np.nan)
            ),
            "label_mode": 1.0 if self.label_mode == "relative" else 0.0,
        }
        return TrainResult(
            model=self,
            metrics=metrics,
            n_train=len(train_df),
            n_valid=len(valid_df),
        )

    def _features_for_predict(
        self,
        ohlcv: pd.DataFrame,
        *,
        cs_ranks: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        feats = build_features(ohlcv)
        for col in CS_FEATURE_COLUMNS:
            if col in self.feature_names:
                val = self._cs_neutral
                if cs_ranks and col in cs_ranks:
                    val = cs_ranks[col]
                feats[col] = val
        missing = [c for c in self.feature_names if c not in feats.columns]
        for c in missing:
            feats[c] = 0.0
        return feats.loc[:, self.feature_names]

    def predict_proba(
        self,
        ohlcv: pd.DataFrame,
        *,
        cs_ranks: dict[str, float] | None = None,
    ) -> pd.Series:
        """Return per-bar score P(label=1) aligned to feature index.

        For single-name scoring without peers, CS ranks default to 0.5.
        Prefer :meth:`score_universe_panel` for consistent cross-section ranks.
        """
        if self.booster is None:
            raise RuntimeError("model is not fitted")
        x = self._features_for_predict(ohlcv, cs_ranks=cs_ranks)
        proba = self.booster.predict(x)
        return pd.Series(proba, index=x.index, name="signal_proba")

    def latest_signal(
        self,
        ohlcv: pd.DataFrame,
        *,
        cs_ranks: dict[str, float] | None = None,
    ) -> float:
        """Return the most recent bar's signal probability."""
        series = self.predict_proba(ohlcv, cs_ranks=cs_ranks)
        if series.empty:
            raise ValueError("no feature rows available for signal")
        return float(series.iloc[-1])

    def save(self, path: Path | str) -> Path:
        """Persist booster + sidecar metadata next to ``path``."""
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
            "label_mode": self.label_mode,
            "include_cs": self.include_cs,
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return model_path

    @classmethod
    def load(cls, path: Path | str) -> SignalModel:
        """Load booster and optional ``.meta.json`` sidecar."""
        path = Path(path)
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        feature_names = list(ALL_MODEL_FEATURES)
        horizon = 5
        params = dict(DEFAULT_PARAMS)
        label_mode = "relative"
        include_cs = True
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            feature_names = list(meta.get("feature_names", feature_names))
            horizon = int(meta.get("horizon", horizon))
            params = dict(meta.get("params", params))
            label_mode = str(meta.get("label_mode", label_mode))
            include_cs = bool(meta.get("include_cs", include_cs))
        else:
            # legacy models trained on FEATURE_COLUMNS only
            feature_names = list(FEATURE_COLUMNS)
            label_mode = "absolute"
            include_cs = False
        booster = lgb.Booster(model_file=str(path))
        return cls(
            booster,
            feature_names=feature_names,
            horizon=horizon,
            params=params,
            label_mode=label_mode,
            include_cs=include_cs,
        )
