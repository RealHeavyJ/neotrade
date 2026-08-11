"""Read-only LightGBM / feature card for operator learning (no train side effects)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from neotrade import defaults as D
from neotrade.config.load import project_root
from neotrade.signals.features import model_feature_names
from neotrade.signals.model import DEFAULT_PARAMS


@dataclass
class ModelCard:
    """Snapshot of production defaults + on-disk model meta (if present)."""

    model_path: str | None
    meta_path: str | None
    meta_present: bool
    label_mode: str
    horizon: int
    include_cs: bool
    n_features: int
    feature_names: list[str]
    exclude_groups: tuple[str, ...]
    params: dict[str, Any]
    best_iteration: int | None = None
    source: str = "defaults"  # defaults | meta
    notes: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        """Compact card for ``neotrade status`` / teaching."""
        excl = ",".join(self.exclude_groups) if self.exclude_groups else "(none)"
        p = self.params
        lines = [
            "--- model card (read-only) ---",
            f"source={self.source} path={self.model_path or 'missing'}",
            (
                f"label_mode={self.label_mode} horizon={self.horizon} "
                f"include_cs={self.include_cs} n_features={self.n_features}"
            ),
            f"exclude_groups={excl}",
            (
                f"lgb: objective={p.get('objective')} num_leaves={p.get('num_leaves')} "
                f"min_child_samples={p.get('min_child_samples')} "
                f"learning_rate={p.get('learning_rate')} "
                f"feature_fraction={p.get('feature_fraction')} "
                f"bagging_fraction={p.get('bagging_fraction')} "
                f"seed={p.get('seed')}"
            ),
        ]
        if "max_depth" in p and p.get("max_depth") is not None:
            lines.append(f"lgb: max_depth={p.get('max_depth')}")
        else:
            lines.append("lgb: max_depth=(unset — leaf-wise, no hard depth cap)")
        if self.best_iteration is not None:
            lines.append(f"best_iteration={self.best_iteration}")
        # short feature list for learning (grouped if long)
        names = self.feature_names
        if len(names) <= 12:
            lines.append(f"features: {', '.join(names)}")
        else:
            head = ", ".join(names[:8])
            lines.append(f"features ({len(names)}): {head}, … (+{len(names) - 8} more)")
        lines.append(
            "read: card describes the signal model only — improve/overfit = eval + "
            "backtest oos_windows / promote, not these knobs alone"
        )
        lines.extend(f"note: {n}" for n in self.notes)
        return lines


def load_model_card(*, model_path: Path | str | None = None) -> ModelCard:
    """Build card from defaults + optional ``signal.txt.meta.json``."""
    root = project_root()
    path = Path(model_path) if model_path else (root / "models" / "signal.txt")
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    exclude = tuple(getattr(D, "FEATURE_EXCLUDE_GROUPS", ()) or ())
    notes: list[str] = []

    # Live defaults used for next train / BT feature list
    default_feats = model_feature_names(include_cs=True)
    label_mode = str(D.TRAIN_LABEL_MODE)
    horizon = int(D.TRAIN_HORIZON)
    include_cs = True
    params = dict(DEFAULT_PARAMS)
    best_iteration = None
    source = "defaults"
    feature_names = list(default_feats)

    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            notes.append(f"meta unreadable: {exc}")
            meta = None
        if isinstance(meta, dict):
            source = "meta"
            feature_names = list(meta.get("feature_names") or feature_names)
            horizon = int(meta.get("horizon", horizon))
            label_mode = str(meta.get("label_mode", label_mode))
            include_cs = bool(meta.get("include_cs", include_cs))
            if isinstance(meta.get("params"), dict):
                params = dict(meta["params"])
            if meta.get("best_iteration") is not None:
                try:
                    best_iteration = int(meta["best_iteration"])
                except (TypeError, ValueError):
                    best_iteration = None
            # Drift check: meta features vs current defaults
            if set(feature_names) != set(default_feats):
                only_meta = sorted(set(feature_names) - set(default_feats))
                only_def = sorted(set(default_feats) - set(feature_names))
                if only_meta or only_def:
                    notes.append(
                        "feature drift vs defaults: "
                        f"meta_only={only_meta[:6]}{'…' if len(only_meta) > 6 else ''} "
                        f"defaults_only={only_def[:6]}{'…' if len(only_def) > 6 else ''} "
                        "(re-train to align on-disk model)"
                    )
    elif not path.is_file():
        notes.append("no models/signal.txt — card shows production defaults only")
    else:
        notes.append("no .meta.json sidecar — params from DEFAULT_PARAMS; features may be legacy")

    return ModelCard(
        model_path=str(path) if path else None,
        meta_path=str(meta_path) if meta_path else None,
        meta_present=meta_path.is_file(),
        label_mode=label_mode,
        horizon=horizon,
        include_cs=include_cs,
        n_features=len(feature_names),
        feature_names=feature_names,
        exclude_groups=exclude,
        params=params,
        best_iteration=best_iteration,
        source=source,
        notes=notes,
    )
