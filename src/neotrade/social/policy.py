"""Hard rules for social data vs LightGBM / promote.

Social posts and desk prose are journal/context only. Numeric aggregates may
become opt-in features later; raw text never trains the signal model.
"""

from __future__ import annotations

import os

# Kinds / fields that must never enter LightGBM training
NEVER_USE_FOR_LIGHTGBM = frozenset(
    {
        "social_prose",
        "tweet_text",
        "post_text",
        "social_summary",
        "desk_social_block",
        "llm_sentiment_reason",
    }
)

POLICY_SUMMARY = (
    "Social posts are archive + desk context. LightGBM trains on OHLCV labels only "
    "via `neotrade train`. Never feed tweet text into the signal model. Bare "
    "`neotrade backtest` promote must not depend on social data."
)

_ENV_ENABLED = "NEOTRADE_SOCIAL_ENABLED"
_ENV_LLM = "NEOTRADE_SOCIAL_LLM"
_ENV_TOKEN = "X_BEARER_TOKEN"
_ENV_TOKEN_ALT = "TWITTER_BEARER_TOKEN"


def _truthy(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def social_enabled() -> bool:
    """Whether desk should surface social (default off).

    Explicit ``neotrade social fetch`` still works when a bearer token is set.
    """
    return _truthy(os.environ.get(_ENV_ENABLED))


def social_llm_enabled() -> bool:
    """Optional Ollama grading (default off — lexicon only)."""
    return _truthy(os.environ.get(_ENV_LLM))


def bearer_token() -> str | None:
    """X API bearer token from env / ``.env``, or None.

    Loads project ``.env`` the same way Alpaca credentials do (does not
    overwrite vars already set in the process environment).
    """
    from neotrade.broker.credentials import load_dotenv

    load_dotenv()
    for key in (_ENV_TOKEN, _ENV_TOKEN_ALT):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return None


def assert_not_train_text(field: str) -> None:
    """Raise if a known prose field is proposed for training."""
    if field in NEVER_USE_FOR_LIGHTGBM:
        raise ValueError(
            f"refusing LightGBM use of social prose field {field!r}: {POLICY_SUMMARY}"
        )
