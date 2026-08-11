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
- [ ] Optional: purged CV / embargo beyond expanding WF — see **Future: ML honesty leftovers**
- [x] Feature upgrade + relative labels + CS ranks (2026-07-20)
- [x] Portfolio walk-forward **backtest** + promotion gate (`neotrade backtest`)
- [x] Improve strategy: ranked top-N + model/mom blend → BT **PASS** (2026-07-25)
- [x] Smarter model track: regime filter + multi-window stable gate + cost stress (2026-07-25)
- [x] Production-strict defaults (`neotrade.defaults`); bare backtest = promote path (2026-07-25)
- [x] Promote knobs: top_n=7 + rebalance_every=14; fair baseline slip (2026-07-25) → **PASS**
- [ ] Re-check: keep stable_gate PASS after weekly data refresh

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
- [x] Handle partial fills / order lifecycle in plan (`OpenOrder`, reserved cash, no double-buy/sell)

## Explicitly deferred
- Cloud LLMs for runtime agents  
- Live (non-paper) trading  
- Feeding advise text into signal model training  
- Institutional multi-account / OMS features  

## Next dev tracks (post-promote) — pick one

v1 + P0–P4 + T1–T6 eng **done**. Next week = **ops + model/agent research** only.

### T1–T6 (shipped)
- [x] T1 weekly · T2 fills · T3 commit · T4 cli split + except narrow  
- [x] T5 `neotrade eval --ablate` + FEATURE_GROUPS  
- [x] T6 promote panel + quote age/stale · `neotrade status` · desk promote packet  
- [ ] Optional: Codecov token · purged CV (later if needed)

### Next week (human + agents — not plumbing)
1. Mon RTH: desk · paper-plan · execute intentional (logs fills)  
2. Research loop: `status` → experiment open → train/eval/ablate/backtest → complete  
3. `neotrade weekly` keeps promote honest  
4. `fills --apply` when n≥20  

### T9 — Social / X research module (Phase A+B shipped 2026-07-25)
- [x] `src/neotrade/social/` fetch → lexicon grade → JSONL cache  
- [x] CLI: `neotrade social {fetch,status,summary}`  
- [x] Desk SOCIAL block when `NEOTRADE_SOCIAL_ENABLED=1` (journal only)  
- [x] `config/social_accounts.yaml` + `docs/social_module.md`  
- [ ] **Ops:** daily `social fetch` if `X_BEARER_TOKEN` set (build history)  
- [ ] Phase C later: IC study → opt-in `FEATURE_GROUPS["social"]` + ablate (never bare promote default)

---

## Future eng tracks (NOT this week — schedule after research week)

Hardware target: **MacBook Neo · Apple A18 Pro · 8 GB RAM · 6 cores**.  
Design brief: `docs/FUTURE_EPOCHS_AND_LOGS.md`.

### T7 — Scalable learning log store (adopted: wait for pain)
**Trigger to start:** learning/ ≫ ~50–100MB, or monitor JSONL hurts Neo, or `logs stats` would be useful weekly.  
**Not Mon priority** — ~0.7MB today.

**Direction (Neo 8GB):** JSONL hot → rotate/compress → archive stamped JSON → optional DuckDB query. Cap **monitor** first.  
See `docs/FUTURE_EPOCHS_AND_LOGS.md`.

### T8 — Paper eras (adopted reshape)
**Name:** paper **eras** (not vanity “maturity engine”).  
**Boss metric remains:** bare `backtest` promote PASS — era diffs are secondary.

**Build order when scheduled:**
1. `epoch snapshot` (book + gates + model hash)  
2. `epoch diff` on **numbers** (eval edges, BT, promote, equity/DD, fills)  
3. `epoch reset-paper --confirm` (liquidate/verify flat; snapshot required)  
4. Desk may read last diff → **one** experiment only  

**Never:** train LightGBM on era prose · auto-tune from narrative · multi-open exps  

### Agent advisor (adopted — live now)
- [x] `AGENTS.md` expert review before building features  
- [x] `docs/FEATURE_REQUEST_REVIEW.md`  
- [x] Desk QUANT/CRITIC **BLIND_SPOT**  

### Future: ML honesty leftovers (not this week — anti-overfit already strong)

Core covered: time-ordered WF eval, portfolio WF BT, costs/slip + stress, multi-window stable_gate, baselines, leakage notes, ablate, paper forward test, one-open exps. **Do not rebuild.**

| ID | Idea | Trigger to start | Priority |
|----|------|------------------|----------|
| H1 | **Embargo-lite** on eval folds (gap bars after train end) | After 2+ weeklies where promote flips on noise | P2 |
| H2 | Full **purged/embargo CV** (López de Prado style) | Only if H1 insufficient / academic need | P3 |
| H3 | BT **OOS window stats** (min/med/mean/max Sharpe, worst edge) | **Shipped 2026-08-10** — `summarize_oos_windows` on BT summary + status | done |
| H4 | Default **`--require-both`** baselines | Exp only if promote too easy / overconfident | P3 |
| H5 | **T8** era snapshot/diff (numbers) | Before paper reset or multi-era compare | P1 eng later |
| H6 | Fill slip calib live | When fills **n≥20** | Ops |
| H7 | **Model card** on status + retrain event params/features | **Shipped 2026-08-10** — read-only learning | done |

**Never as “fix overfitting”:** more tickers, deeper trees, auto-tune, train on desk/Ollama prose, multi-open experiments.

### Do not (always)
- Rebuild v1 · live trading · train on advise · multi-open experiments  

## Status
**2026-08-10 — H3 OOS window stats shipped.** Score **10.0** · promote currently **FAIL** 2/3 (ops).  
**Default:** weekly refresh + read `oos_windows` block · Mon daily loop.  
```
neotrade backtest   # see oos_windows min/med/mean/max + worst=
neotrade status     # note: oos sh min/med/...
neotrade weekly     # when ages stale
```
**Later eng:** T8 (H5) · H1 embargo-lite · T7 when log pain.

Last updated: 2026-08-10
