# Tasks - neotrade

## Restart here (next session)
1. Operator day? → `DAILY_TODO.md` only  
2. Coding day? → **`QUALITY_SCORE.md`** + `AGENTS.md` + `PROGRESS.md` (top) + this file  
3. `source .venv/bin/activate && pytest -q`  
4. One track only — prefer P0–P4 (must hold/raise score ≥ 7.6)

## Complete (v1 foundation) — do not redo
- [x] Scaffold, config, neotrade-core-22
- [x] OHLCV cache; Alpaca MD REST quotes/bars; yfinance fallback
- [x] LightGBM features/train/signals
- [x] Alpaca paper client, risk sleeves, plan/execute
- [x] LangGraph agents + Ollama llama3.2:3b
- [x] Streamlit dashboard + bench + learning file hooks
- [x] Open-order-aware agent prompts
- [x] `DAILY_TODO.md` + dep verification (libomp OK)
- [x] Code review cleanup + Google-style public API docs (2026-07-19)

## Plan: close senior-review gaps (what holds the score back)

Source: 2026-07-19 code review overall **~7.6/10**. Gaps below are the backlog that
moves quality toward 8.5+ without rebuilding v1.

### P0 — ops safety
- [x] **Market-hours gate** — execute RTH only; block pre/after-hours/closed (`broker/hours.py`)
- [x] Surface session on `account`, `session`, `paper-plan`, dashboard Overview/Account/Plan
- [x] Refuse `paper-execute` outside RTH (exit 3); no extended-hours opt-in
- [ ] Longer-term: agent **realtime monitor** (poll/WS quotes within free Alpaca MD limits) — not execute

### P1 — signal / ML rigor (edge quality)
- [ ] LightGBM **walk-forward** (or purged CV) eval; stop relying on single time split
- [ ] Calibration / reliability check (proba vs hit-rate by bucket)
- [ ] Leakage audit (features vs label horizon); document assumptions
- [ ] Baseline comparison (e.g. always-long / momentum-only) so “0.55 acc” is contextualized

### P2 — observability & errors
- [ ] Structured logging (module + level); replace silent `except: pass` where it hides failures
- [ ] Narrow broad `except Exception` in fetch/score/advise paths (typed errors + user message)
- [ ] Integration smoke script (optional, non-CI): quotes + account + signals once

### P3 — product completeness
- [ ] **Advise learning policy** (design first): dashboard rating, what to store, **never** auto-feed prose into LightGBM
- [ ] Wire dashboard Advise to same learning log as CLI (parity)
- [ ] User-guide for non-dev operators (`docs/user-guide.md`)
- [ ] Optional: split `main.py` into `cli/` submodules if CLI keeps growing

### P4 — realtime monitoring (not AH trading)
- [x] Agent-friendly quote poller (`monitor/poller.py`, `neotrade monitor`)
- [x] Move alerts vs prior tick; JSONL log; min interval 5s
- [x] Dashboard Quotes auto-refresh option
- [x] Still **no** execute from monitor; RTH gate unchanged
- [ ] Optional WebSocket stream when free tier allows
- [ ] Handle partial fills / order lifecycle in plan (v1 ignores working orders by design)

## Explicitly deferred
- Cloud LLMs for runtime agents  
- Live (non-paper) trading  
- Feeding advise text into signal model training  
- Institutional multi-account / OMS features  

## Status
**v1 + P0 RTH + P4 monitor poller.** Score floor **7.6** (see `QUALITY_SCORE.md`).  
**Next code default:** P1 ML rigor **or** P2 logging.  
**Ops:** `DAILY_TODO.md` · `neotrade monitor` for live watch.

Last updated: 2026-07-20
