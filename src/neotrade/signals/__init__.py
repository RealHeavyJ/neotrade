"""LightGBM signal features, model, and scoring.

Lazy-imports :class:`SignalModel` so environments without ``libomp`` can still
import :func:`build_features` and related pure-Python helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from neotrade.signals.features import FEATURE_COLUMNS, build_features
from neotrade.signals.score import ScoreResult, SignalRow, score_universe

if TYPE_CHECKING:
    from neotrade.signals.model import SignalModel

__all__ = [
    "FEATURE_COLUMNS",
    "ScoreResult",
    "SignalModel",
    "SignalRow",
    "build_features",
    "score_universe",
]


def __getattr__(name: str):
    """PEP 562 lazy attribute loader for heavy optional imports."""
    if name == "SignalModel":
        from neotrade.signals.model import SignalModel as _SignalModel

        return _SignalModel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
