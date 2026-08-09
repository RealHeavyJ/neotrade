"""LightGBM signal features, model, and scoring.

Lazy-imports :class:`SignalModel` so environments without ``libomp`` can still
import :func:`build_features` and related pure-Python helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from neotrade.signals.features import ALL_MODEL_FEATURES, FEATURE_COLUMNS, build_features
from neotrade.signals.score import ScoreResult, SignalRow, score_universe

if TYPE_CHECKING:
    from neotrade.signals.eval import EvalReport
    from neotrade.signals.model import SignalModel

__all__ = [
    "ALL_MODEL_FEATURES",
    "FEATURE_COLUMNS",
    "EvalReport",
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
    if name == "EvalReport":
        from neotrade.signals.eval import EvalReport as _EvalReport

        return _EvalReport
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
