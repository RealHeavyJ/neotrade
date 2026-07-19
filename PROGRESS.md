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

### Code review / docs cleanup (DONE 2026-07-19)
- `ScoreResult` replaces function-attr error side-channel
- Removed dead `latest_trade_price` stub; ruff-clean
- Google-style docstrings on core public APIs
- Tests still **35 passed**

### Score-back plan (review 7.6 → aim 8.5+)
Full checklist in `TASKS.md` § “close senior-review gaps”. Summary:

| Gap | Track |
|-----|--------|
| No session/hours gate | P0 market-hours |
| ML edge unproven | P1 walk-forward / calibration / baselines |
| Weak observability; broad excepts | P2 structured logging |
| Advise log incomplete product story | P3 learning policy + dashboard parity |
| No WS / partial-fill modeling | P4 optional realtime |

### Next engineering (default)
1. **P0 Market-hours gate** on plan/execute  
2. Then P1 signal rigor or P3 advise policy (user choice)

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
