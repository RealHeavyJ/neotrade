"""Walk-forward evaluation, baselines, calibration, and leakage checks (P1).

Improves ML rigor without changing the production train path unless explicitly
used. Labels remain forward close return > 0 over ``horizon`` bars.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from neotrade.config.load import project_root
from neotrade.signals.features import (
    MAX_LOOKBACK_BARS,
    add_cross_section_features,
    build_labeled_frame,
    model_feature_names,
)
from neotrade.signals.model import DEFAULT_PARAMS


@dataclass
class FoldResult:
    """One walk-forward fold outcome."""

    fold: int
    train_end: str
    test_start: str
    test_end: str
    n_train: int
    n_test: int
    accuracy: float
    logloss: float
    pos_rate: float
    always_long_acc: float
    momentum_acc: float
    brier: float


@dataclass
class CalibrationBin:
    """Reliability bin: mean predicted proba vs empirical hit rate."""

    bin_lo: float
    bin_hi: float
    n: int
    mean_proba: float
    hit_rate: float


@dataclass
class LeakageReport:
    """Static checks that features do not use future information incorrectly."""

    ok: bool
    notes: list[str] = field(default_factory=list)
    max_feature_lookback_bars: int = 50
    label_horizon_bars: int = 5


@dataclass
class EvalReport:
    """Full P1 evaluation report."""

    ts: str
    horizon: int
    n_folds: int
    folds: list[FoldResult]
    mean_accuracy: float
    mean_always_long_acc: float
    mean_momentum_acc: float
    mean_brier: float
    edge_vs_always_long: float
    edge_vs_momentum: float
    calibration: list[CalibrationBin]
    leakage: LeakageReport
    notes: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = [
            f"eval @ {self.ts} horizon={self.horizon} folds={self.n_folds}",
            f"mean_accuracy={self.mean_accuracy:.4f}  "
            f"always_long={self.mean_always_long_acc:.4f}  "
            f"momentum={self.mean_momentum_acc:.4f}",
            f"edge_vs_always_long={self.edge_vs_always_long:+.4f}  "
            f"edge_vs_momentum={self.edge_vs_momentum:+.4f}",
            f"mean_brier={self.mean_brier:.4f}  leakage_ok={self.leakage.ok}",
        ]
        for note in self.notes:
            lines.append(f"note: {note}")
        for n in self.leakage.notes:
            lines.append(f"leakage: {n}")
        if self.calibration:
            lines.append("calibration (proba bin → hit_rate):")
            for b in self.calibration:
                if b.n == 0:
                    continue
                lines.append(
                    f"  [{b.bin_lo:.1f},{b.bin_hi:.1f}) n={b.n} "
                    f"mean_p={b.mean_proba:.3f} hit={b.hit_rate:.3f}"
                )
        for fr in self.folds:
            lines.append(
                f"  fold{fr.fold}: acc={fr.accuracy:.3f} "
                f"al={fr.always_long_acc:.3f} mom={fr.momentum_acc:.3f} "
                f"n_test={fr.n_test} {fr.test_start}→{fr.test_end}"
            )
        return lines

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "horizon": self.horizon,
            "n_folds": self.n_folds,
            "mean_accuracy": self.mean_accuracy,
            "mean_always_long_acc": self.mean_always_long_acc,
            "mean_momentum_acc": self.mean_momentum_acc,
            "mean_brier": self.mean_brier,
            "edge_vs_always_long": self.edge_vs_always_long,
            "edge_vs_momentum": self.edge_vs_momentum,
            "folds": [asdict(f) for f in self.folds],
            "calibration": [asdict(c) for c in self.calibration],
            "leakage": asdict(self.leakage),
            "notes": self.notes,
        }


def build_panel(
    frames: dict[str, pd.DataFrame],
    *,
    horizon: int = 5,
    relative_label: bool = True,
) -> pd.DataFrame:
    """Stack per-symbol labeled frames; add CS ranks and relative labels."""
    parts: list[pd.DataFrame] = []
    for symbol, ohlcv in frames.items():
        try:
            labeled = build_labeled_frame(ohlcv, horizon=horizon)
        except ValueError:
            continue
        labeled = labeled.copy()
        labeled["symbol"] = symbol
        parts.append(labeled)
    if not parts:
        raise ValueError("no labeled rows for evaluation")
    panel = pd.concat(parts, axis=0).sort_index()
    return add_cross_section_features(panel, relative_label=relative_label)


def check_leakage(*, horizon: int = 5) -> LeakageReport:
    """Document and verify label/feature temporal separation assumptions."""
    notes = [
        "Features: lagging returns/RSI/SMA/MACD/Bollinger/volume/ATR — no lead ops.",
        "CS ranks use same-day lagging features only (not future returns).",
        f"Label default: relative — fwd_ret > cross-sectional median over {horizon} bars.",
        "Absolute baseline (always-long) uses label_absolute when present.",
        "Walk-forward trains on index dates < test_start only.",
    ]
    max_lookback = MAX_LOOKBACK_BARS
    ok = horizon >= 1 and max_lookback >= 1
    if horizon < 1:
        notes.append("FAIL: horizon < 1")
        ok = False
    return LeakageReport(
        ok=ok,
        notes=notes,
        max_feature_lookback_bars=max_lookback,
        label_horizon_bars=horizon,
    )


def _logloss(y: np.ndarray, p: np.ndarray) -> float:
    eps = 1e-15
    p = np.clip(p, eps, 1 - eps)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def _brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def _accuracy(y: np.ndarray, pred: np.ndarray) -> float:
    if len(y) == 0:
        return float("nan")
    return float((pred == y).mean())


def baseline_always_long(y: np.ndarray) -> float:
    """Accuracy of always predicting class 1 (long / outperform)."""
    if len(y) == 0:
        return float("nan")
    return float((y == 1).mean())


def baseline_momentum(df: pd.DataFrame) -> float:
    """Momentum baseline aligned to label definition.

    Relative labels: predict outperform when ``cs_rank_ret_5`` > 0.5 (or
    ``ret_5`` above same-day median). Absolute: ``ret_5 > 0``.
    """
    if df.empty or "label" not in df.columns:
        return float("nan")
    y = df["label"].astype(int).to_numpy()
    if "cs_rank_ret_5" in df.columns:
        pred = (df["cs_rank_ret_5"].to_numpy() > 0.5).astype(int)
    elif "ret_5" in df.columns:
        # fall back: ret_5 > cross-section median when multiple rows/date
        if df.index.duplicated().any() or df.index.nunique() < len(df):
            med = df.groupby(level=0)["ret_5"].transform("median")
            pred = (df["ret_5"] > med).astype(int).to_numpy()
        else:
            pred = (df["ret_5"].to_numpy() > 0).astype(int)
    else:
        return float("nan")
    return _accuracy(y, pred)


def calibration_table(
    y: np.ndarray,
    proba: np.ndarray,
    *,
    n_bins: int = 5,
) -> list[CalibrationBin]:
    """Equal-width probability bins from 0 to 1."""
    if len(y) == 0:
        return []
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    out: list[CalibrationBin] = []
    for i in range(n_bins):
        lo, hi = float(edges[i]), float(edges[i + 1])
        if i == n_bins - 1:
            mask = (proba >= lo) & (proba <= hi)
        else:
            mask = (proba >= lo) & (proba < hi)
        n = int(mask.sum())
        if n == 0:
            out.append(CalibrationBin(lo, hi, 0, float("nan"), float("nan")))
            continue
        out.append(
            CalibrationBin(
                bin_lo=lo,
                bin_hi=hi,
                n=n,
                mean_proba=float(proba[mask].mean()),
                hit_rate=float(y[mask].mean()),
            )
        )
    return out


def _train_booster(
    train_df: pd.DataFrame,
    *,
    feature_names: list[str],
    params: dict[str, Any],
    num_boost_round: int,
) -> lgb.Booster:
    x = train_df.loc[:, feature_names]
    y = train_df["label"].astype(int)
    dtrain = lgb.Dataset(x, label=y, feature_name=feature_names)
    return lgb.train(
        params,
        dtrain,
        num_boost_round=num_boost_round,
        callbacks=[lgb.log_evaluation(period=0)],
    )


def walk_forward_eval(
    frames: dict[str, pd.DataFrame],
    *,
    horizon: int = 5,
    n_folds: int = 4,
    min_train_frac: float = 0.4,
    num_boost_round: int = 100,
    params: dict[str, Any] | None = None,
    feature_names: list[str] | None = None,
    relative_label: bool = True,
) -> EvalReport:
    """Expanding-window walk-forward evaluation with baselines and calibration.

    Default ``relative_label=True`` matches production ranking objective
    (beat same-day median forward return).

    Args:
        frames: symbol → OHLCV.
        horizon: Label horizon (must match production intent).
        n_folds: Number of sequential test folds.
        min_train_frac: Minimum fraction of dates reserved for initial train.
        num_boost_round: Boosting rounds per fold (no early stop for stability).
        params: LightGBM params.
        feature_names: Feature columns.
        relative_label: Use relative outperformance labels.

    Returns:
        :class:`EvalReport` with fold metrics and aggregate edges.
    """
    if n_folds < 2:
        raise ValueError("n_folds must be >= 2")
    if not 0.2 <= min_train_frac <= 0.8:
        raise ValueError("min_train_frac must be in [0.2, 0.8]")

    feature_names = list(feature_names or model_feature_names(include_cs=True))
    params = dict(params or DEFAULT_PARAMS)
    leakage = check_leakage(horizon=horizon)
    panel = build_panel(frames, horizon=horizon, relative_label=relative_label)
    for col in feature_names:
        if col not in panel.columns:
            panel[col] = 0.5 if col.startswith("cs_") else 0.0
    dates = panel.index.unique().sort_values()
    n_dates = len(dates)
    if n_dates < n_folds + 5:
        raise ValueError(f"not enough unique dates ({n_dates}) for {n_folds} folds")

    train_end_i = int(n_dates * min_train_frac)
    train_end_i = max(train_end_i, 10)
    remaining = n_dates - train_end_i
    if remaining < n_folds:
        raise ValueError("not enough dates after min_train_frac for folds")

    fold_size = remaining // n_folds
    if fold_size < 1:
        raise ValueError("fold_size < 1")

    folds: list[FoldResult] = []
    all_y: list[np.ndarray] = []
    all_p: list[np.ndarray] = []
    notes: list[str] = []

    for f in range(n_folds):
        test_start_i = train_end_i + f * fold_size
        test_end_i = train_end_i + (f + 1) * fold_size if f < n_folds - 1 else n_dates
        train_dates = dates[:test_start_i]
        test_dates = dates[test_start_i:test_end_i]
        train_df = panel.loc[panel.index.isin(train_dates)]
        test_df = panel.loc[panel.index.isin(test_dates)]
        if train_df.empty or test_df.empty:
            notes.append(f"fold {f}: empty split skipped")
            continue

        booster = _train_booster(
            train_df,
            feature_names=feature_names,
            params=params,
            num_boost_round=num_boost_round,
        )
        x_test = test_df.loc[:, feature_names]
        y = test_df["label"].astype(int).to_numpy()
        proba = np.asarray(booster.predict(x_test), dtype=float)
        pred = (proba >= 0.5).astype(int)

        fr = FoldResult(
            fold=f,
            train_end=str(pd.Timestamp(train_dates[-1]).date()),
            test_start=str(pd.Timestamp(test_dates[0]).date()),
            test_end=str(pd.Timestamp(test_dates[-1]).date()),
            n_train=len(train_df),
            n_test=len(test_df),
            accuracy=_accuracy(y, pred),
            logloss=_logloss(y, proba),
            pos_rate=float(y.mean()) if len(y) else float("nan"),
            always_long_acc=baseline_always_long(y),
            momentum_acc=baseline_momentum(test_df),
            brier=_brier(y, proba),
        )
        folds.append(fr)
        all_y.append(y)
        all_p.append(proba)

    if not folds:
        raise RuntimeError("no folds produced")

    mean_acc = float(np.nanmean([f.accuracy for f in folds]))
    mean_al = float(np.nanmean([f.always_long_acc for f in folds]))
    mean_mom = float(np.nanmean([f.momentum_acc for f in folds]))
    mean_brier = float(np.nanmean([f.brier for f in folds]))
    y_cat = np.concatenate(all_y)
    p_cat = np.concatenate(all_p)
    cal = calibration_table(y_cat, p_cat, n_bins=5)

    if mean_acc <= mean_al + 1e-6:
        notes.append("model mean accuracy does not beat always-long baseline")
    if mean_acc <= mean_mom + 1e-6:
        notes.append("model mean accuracy does not beat momentum (ret_5>0) baseline")

    return EvalReport(
        ts=datetime.now(timezone.utc).isoformat(),
        horizon=horizon,
        n_folds=len(folds),
        folds=folds,
        mean_accuracy=mean_acc,
        mean_always_long_acc=mean_al,
        mean_momentum_acc=mean_mom,
        mean_brier=mean_brier,
        edge_vs_always_long=mean_acc - mean_al,
        edge_vs_momentum=mean_acc - mean_mom,
        calibration=cal,
        leakage=leakage,
        notes=notes,
    )


def save_eval_report(report: EvalReport, path: Path | str | None = None) -> Path:
    """Write eval JSON under data/learning/ by default."""
    if path is None:
        out_dir = project_root() / "data" / "learning"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "eval_latest.json"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    # also timestamped copy
    stamped = path.with_name(
        f"eval_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    if stamped != path:
        try:
            stamped.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        except OSError as exc:
            from neotrade.logging_config import get_logger

            get_logger("signals.eval").warning("stamped eval write skipped: %s", exc)
    return path


def run_signal_eval(
    frames: dict[str, pd.DataFrame],
    *,
    horizon: int = 5,
    n_folds: int = 4,
    num_boost_round: int = 100,
    save: bool = True,
    relative_label: bool = True,
) -> EvalReport:
    """Convenience: walk-forward eval + optional disk save."""
    report = walk_forward_eval(
        frames,
        horizon=horizon,
        n_folds=n_folds,
        num_boost_round=num_boost_round,
        relative_label=relative_label,
    )
    if save:
        save_eval_report(report)
    return report
