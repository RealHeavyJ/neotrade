# Progress Log

## Session end checkpoint (2026-07-19 ~14:30 PT) — RESTART HERE

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

### Next engineering (pick one)
1. **Market-hours gate** on plan/execute (highest practical value)
2. Advise → learning policy (ratings / when to retrain) — design first
3. WebSocket quotes (optional; REST enough)
4. LightGBM walk-forward (edge quality)

### Next session bootstrap (minimal tokens)
1. `DAILY_TODO.md` if operating the book  
2. Else: this file (top) → `TASKS.md` → open **only** code for chosen track  
3. `source .venv/bin/activate && pytest -q`  
4. Do **not** re-read full history or rebuild scaffold/signals/agents unless broken

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
