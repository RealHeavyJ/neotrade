# Tasks - neotrade

## Restart here (next session)
1. Operator day? → `DAILY_TODO.md` only  
2. Coding day? → `PROGRESS.md` (top) + this file + `CONTEXT.md`  
3. `source .venv/bin/activate && pytest -q`  
4. One track only (below)

## Complete (v1 foundation) — do not redo
- [x] Scaffold, config, neotrade-core-22
- [x] OHLCV cache; Alpaca MD REST quotes/bars; yfinance fallback
- [x] LightGBM features/train/signals
- [x] Alpaca paper client, risk sleeves, plan/execute
- [x] LangGraph agents + Ollama llama3.2:3b
- [x] Streamlit dashboard + bench + learning file hooks
- [x] Open-order-aware agent prompts
- [x] `DAILY_TODO.md` + dep verification (libomp OK)

## Next (priority)
1. [ ] **Market-hours gate** — block or warn plan/execute outside RTH; surface session in account/dashboard  
2. [ ] **Advise learning policy** (design → light code) — dashboard rating optional; never auto-feed prose into LightGBM  
3. [ ] WebSocket live quotes (optional)  
4. [ ] LightGBM walk-forward / calibration (optional edge work)  
5. [ ] Logging polish / user-guide / market-hours launch helper

## Explicitly deferred
- Cloud LLMs for runtime agents  
- Live (non-paper) trading  
- Feeding advise text into signal model training  

## Status
**v1 runnable locally.** Next code: market-hours gate unless user chooses otherwise.  
Ops: post-open fill check per `DAILY_TODO.md`.

Last updated: 2026-07-19
