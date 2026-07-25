# Tasks - neotrade

## Restart here (next session)
1. Operator day? → `DAILY_TODO.md` only  
2. Coding day? → **`QUALITY_SCORE.md`** + `AGENTS.md` + `PROGRESS.md` (top) + this file  
3. `source .venv/bin/activate && pytest -q`  
4. One track only — must hold/raise score ≥ floor (**7.6**); prefer improve overall  
5. **End of session:** `AGENTS.md` → Session close checklist (mandatory if files changed)

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
- [x] LightGBM **walk-forward** eval (`signals/eval.py`, `neotrade eval`)
- [x] Calibration bins + Brier score
- [x] Leakage audit notes + structural checks
- [x] Baselines: always-long + momentum (`ret_5>0`); edge reported
- [ ] Optional: purged CV / embargo beyond expanding WF
- [x] Feature upgrade + relative labels + CS ranks (2026-07-20)
- [x] Portfolio walk-forward **backtest** + promotion gate (`neotrade backtest`)
- [x] Improve strategy: ranked top-N + model/mom blend → BT **PASS** (2026-07-25)
- [x] Smarter model track: regime filter + multi-window stable gate + cost stress (2026-07-25)
- [ ] Re-check: keep stable_gate PASS after data refreshes / longer history

### P2 — observability & errors
- [x] Structured logging (`logging_config.py`; level/JSON/file env)
- [x] Replace silent learning-log `pass` with `log.warning`
- [x] Narrow broad `except Exception` on fetch/score/advise/agents/dashboard/bench
- [x] Integration smoke script: `scripts/smoke_integration.py`

### P3 — product completeness
- [x] **Advise learning policy** (`learning/policy.py`) — journal only; never LightGBM
- [x] CLI `--rating` / `--notes` + dashboard rating UI; shared `record_advice_run`
- [x] User-guide for operators (`docs/user-guide.md`)
- [ ] Optional: split `main.py` into `cli/` submodules if CLI keeps growing

### P4 — realtime monitoring (not AH trading)
- [x] Agent-friendly quote poller (`monitor/poller.py`, `neotrade monitor`)
- [x] Move alerts vs prior tick; JSONL log; min interval 5s
- [x] Dashboard Quotes auto-refresh option
- [x] Still **no** execute from monitor; RTH gate unchanged
- [x] Optional WebSocket stream (`monitor/stream.py`, `neotrade stream`, IEX)
- [ ] Handle partial fills / order lifecycle in plan (v1 ignores working orders by design)

## Explicitly deferred
- Cloud LLMs for runtime agents  
- Live (non-paper) trading  
- Feeding advise text into signal model training  
- Institutional multi-account / OMS features  

## Status
**v1 complete.** Score **9.1** / floor **7.6**.  
**2026-07-25 model track:** regime + multi-window stable gate → **promote=True** (3/3 windows PASS, cost stress ok).  
**Next:** experiment ledger (desk EXPERIMENT → result); optional scheduled desk; ops Mon.  
**Promote:** `neotrade backtest` exit 0 (full + stable gates).  
**Desk:** `neotrade desk` shipped (ops/quant/PM/critic).

Last updated: 2026-07-25
