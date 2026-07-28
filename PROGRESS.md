# Progress Log

## Session close checklist (agents + humans)

Before ending a **coding** session (see also `AGENTS.md`):

1. [ ] `pytest -q` green (if code changed)  
2. [ ] Update **this file’s top checkpoint** (shipped + next default)  
3. [ ] Update `TASKS.md` status / next  
4. [ ] Update `QUALITY_SCORE.md` only if score dimensions moved  
5. [ ] One-line hand-off: shipped · tests/score · next track  

Ops-only day → `DAILY_TODO.md` status log only (skip eng files).

---

## Session end checkpoint (2026-07-25 T9 social) — RESTART HERE

### Shipped
- **T9 Phase A+B:** `neotrade social` module — X fetch/cache/lexicon grade, desk context  
  - Package `src/neotrade/social/`, CLI fetch/status/summary, `config/social_accounts.yaml`  
  - Desk SOCIAL block only if `NEOTRADE_SOCIAL_ENABLED=1`; **not** LightGBM train; promote untouched  
  - Docs: `docs/social_module.md`  
- Prior: promote PASS path, T1–T6 eng pack  

### Live
```
promote path unchanged · score 10.0 · 148 tests · social default OFF
```

### Next session default (Mon research — not eng)
```
neotrade status
neotrade desk
# one experiment only →
neotrade train && neotrade eval && neotrade backtest
neotrade experiment complete --latest
# optional archive: X_BEARER_TOKEN + neotrade social fetch (daily)
```
Execute only RTH + `--confirm` + promote yes. `fills --apply` when n≥20.

### Later eng (not next)
T8a snapshot/diff → T8c reset · T7 when learning/ grows — `docs/FUTURE_EPOCHS_AND_LOGS.md`

### Uncommitted
Working tree may still have local changes — **commit/push when you want** (not done this close).

### 2026-07-25 research-ready eng pack
- `learning/promote_status.py` + `neotrade status`  
- Dashboard promote panel; quote age/stale on monitor + Quotes  
- `eval --ablate` feature groups; excepts narrowed  
- Desk packet: promote/freshness/defaults/fills  

### 2026-07-25 T4 split CLI
- `main.py` ~50 lines; handlers in `neotrade/cli/*`  
- parser + data/ml/broker/agent/ops modules  

### 2026-07-25 T3 commit
- Shipped T1 weekly + T2 fills on main (local commit)

### 2026-07-25 T2 fill calibration
- `broker/fills.py` + `neotrade fills` / `--apply` (n≥20)  
- paper-execute logs slip vs mid; account shows calib  
- bare BT slip = `defaults.effective_slip_bps()`  

### 2026-07-25 T1 weekly automation
- `neotrade weekly` / `scripts/weekly_promote.sh` / launchd plist  
- exit 0=promote PASS · 2=FAIL · never execute  
- `data/learning/weekly_latest.json`

### Promote only if
bare `backtest` → PASS (no `--fast`).

---

## Older checkpoint (2026-07-19) — archive

### v1 loop status: COMPLETE (ops + polish remain)

| Layer | Status |
|-------|--------|
| Config + 22-ticker universe | Done |
| OHLCV cache + Alpaca MD quotes/bars | Done |
| LightGBM train/signals | Done |
| Alpaca paper account/plan/execute | Done |
| LangGraph + Ollama advise | Done |
| Streamlit dashboard | Done |
| Bench + learning log files | Done |
| Agent open-order prompt fix | Done |
| Operator daily checklist | `DAILY_TODO.md` |
| Deps verified | libomp, Ollama 3b, 35 tests, quotes live |

### CLI map (do not rebuild)
```
neotrade tickers | fetch | quotes | train | signals
neotrade account | paper-plan | paper-execute --confirm
neotrade advise | bench | dashboard
```

### Operator note (open book)
- Paper buys submitted weekend: often **accepted / unfilled** until US regular session
- After Mon open: follow `DAILY_TODO.md` → confirm fills via `neotrade account`

### Advise ≠ ML training
- Dashboard/CLI advise = narrative only
- CLI `advise` appends thin snapshot to `data/learning/events.jsonl`
- LightGBM only updates via `neotrade train` on price history

### Deps (verified 2026-07-19)
- libomp installed; LightGBM imports
- Ollama service + llama3.2:3b; bench ~5s latency OK
- `.env` paper + `ALPACA_DATA_*`; feed iex
- `pytest` **35 passed**

### Code review / docs cleanup (DONE 2026-07-19)
- `ScoreResult` replaces function-attr error side-channel
- Removed dead `latest_trade_price` stub; ruff-clean
- Google-style docstrings on core public APIs
- Tests still **35 passed**

### P0 market-hours gate (DONE 2026-07-20)
- `broker/hours.py` — US RTH 09:30–16:00 ET; block pre/AH/closed/holiday
- CLI: `neotrade session`; banners on account/plan; execute hard-block
- Dashboard Overview/Account/Plan show session
- Policy: **no after-hours trading**; quotes/monitor anytime

### Score-back plan (7.8 → aim 8.5+)
| Gap | Track |
|-----|--------|
| ~~No session gate~~ | ~~P0 done~~ |
| ML edge unproven | P1 walk-forward / calibration / baselines |
| Weak observability | P2 structured logging |
| Advise log policy | P3 |
| Realtime **monitor** (user long-term) | P4 poll/WS — not AH execute |

### P4 quote monitor (DONE 2026-07-20)
- `monitor/poller.py` + `neotrade monitor` (interval, moves, JSONL)
- Dashboard Quotes auto-refresh; never executes
- Score **8.0**

### P1 ML eval (DONE 2026-07-20)
- `signals/eval.py` + `neotrade eval` — walk-forward, always-long + momentum baselines
- Calibration bins, Brier, leakage report; `data/learning/eval_latest.json`
- Exit 2 if model fails both baselines
- Score **8.2**

### P2 logging (DONE 2026-07-20)
- `logging_config.py` — level/JSON/file via env
- Narrowed bare Exception handlers; learning log failures warn
- `scripts/smoke_integration.py`
- Score **8.4**

### P3 advise learning (DONE 2026-07-20)
- `learning/policy.py` — journal only; never LightGBM
- CLI `--rating` / dashboard rate UI; shared `record_advice_run`
- `docs/user-guide.md`
- Score **8.5** (target hit); next lift = ML edge

### Signal upgrade (DONE 2026-07-20)
- Richer lagging features + CS ranks; default **relative** labels
- `score_universe` builds latest-bar CS panel
- Live eval: edge_al **+0.0077**, edge_mom **+0.0288** (exit 0)
- Retrain required for production model (done this session)
- Score **8.6**

### WebSocket stream (DONE 2026-07-20)
- `monitor/stream.py` + `neotrade stream` (IEX v2, websockets lib)
- Auth/subscribe/trade+quote parse; mocked unit tests
- Never executes; score **8.7**

### Portfolio backtest (DONE 2026-07-20)
- `signals/backtest.py` + `neotrade backtest`
- WF retrain, next-open fills, costs, eq-weight + momentum baselines
- Promotion gate (exit 0/2); live run **gate=FAIL** (signal +35% vs eq +38% vs mom +63%)
- Score **8.8**

### Next engineering (default)
1. Improve signals/plan until backtest gate PASSes  
2. Optional partial-fill lifecycle  
3. Keep execute RTH-only

### Quality score (stored)
- **`QUALITY_SCORE.md`**: overall **7.6**, floor **7.6**, target **8.5**
- **`AGENTS.md`**: all agents must hold/raise score; never regress
- Closing gaps (P0–P4) is how the score improves — see `TASKS.md`

### Next session bootstrap (minimal tokens)
1. Coding: **`QUALITY_SCORE.md`** → `AGENTS.md` → this file (top) → `TASKS.md`  
2. Ops only: `DAILY_TODO.md`  
3. `source .venv/bin/activate && pytest -q`  
4. One track that improves score; do not rebuild v1 unless broken  
5. After quality-relevant work: update score log if dimensions moved

### Gotchas
- `source .venv/bin/activate` (not execute)
- Never commit `.env`
- Paper trading URL only; data host `data.alpaca.markets`

---

## Earlier 2026-07-19 (compressed)
- Session 1a/1b: config, cache, LightGBM
- Paper broker + SSL/certifi + `/v2` strip
- Ollama brew install + live advise
- Dashboard, bench, Alpaca MD REST, prompt fix, DAILY_TODO

## Session 0 (2026-07-15)
- Scaffold neotrade + CI + markdown memory

Last updated: 2026-07-19
