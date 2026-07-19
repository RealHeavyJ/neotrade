"""LightGBM signal features, model, and scoring."""

from __future__ import annotations

from typing import TYPE_CHECKING

from neotrade.signals.features import FEATURE_COLUMNS, build_features
from neotrade.signals.score import SignalRow, score_universe

if TYPE_CHECKING:
    from neotrade.signals.model import SignalModel

__all__ = [
    "FEATURE_COLUMNS",
    "SignalModel",
    "SignalRow",
    "build_features",
    "score_universe",
]


def __getattr__(name: str):
    if name == "SignalModel":
        from neotrade.signals.model import SignalModel as _SignalModel

        return _SignalModel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
