"""Optional X (Twitter) social research module — desk context + archive.

Phase A/B: fetch/cache/grade posts, surface on desk. LightGBM training is
**not** wired; numeric aggregates may be used later only after ablation.

See ``docs/social_module.md`` and :mod:`neotrade.social.policy`.
"""

from __future__ import annotations

from neotrade.social.policy import (
    NEVER_USE_FOR_LIGHTGBM,
    POLICY_SUMMARY,
    social_enabled,
    social_llm_enabled,
)

__all__ = [
    "NEVER_USE_FOR_LIGHTGBM",
    "POLICY_SUMMARY",
    "social_enabled",
    "social_llm_enabled",
]
