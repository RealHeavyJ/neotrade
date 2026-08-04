"""neotrade: local-first paper-trading decision support for MacBook Neo.

Package layout:
    config   — YAML universe + risk schema
    data     — OHLCV cache, Alpaca market data, quotes
    signals  — LightGBM features / train / score
    broker   — Alpaca paper client + risk plan
    agents   — LangGraph + Ollama advise
    dashboard — Streamlit UI
    perf / learning — bench + append-only event logs

CLI: ``neotrade`` console script → :mod:`neotrade.main`.
"""

__version__ = "0.1.0"
