# neotrade — daily operator checklist

Personal to-do. Review each market day (or when you sit down with the project).
Last updated: 2026-07-19 (deps verified; libomp OK — not a daily install)

---

## Every session (2 min)

```bash
cd ~/dev/neotrade
source .venv/bin/activate    # must source, not execute
pytest -q                    # optional smoke
```

- [ ] Ollama up: `brew services list | grep ollama` (or `curl -s localhost:11434/api/tags`)
- [ ] `.env` present (never commit); paper keys only

---

## After US regular open (Mon–Fri ~9:30–16:00 ET) — **priority this week**

Weekend paper orders were **accepted**, not filled. Confirm the book is real:

- [ ] `neotrade account` — positions > 0 and/or open_orders cleared/filled
- [ ] Note cash vs equity (fills reduce cash)
- [ ] `neotrade quotes` — prices look sane (IEX feed OK)
- [ ] `neotrade paper-plan` — intents make sense **with** current holdings
- [ ] Only if plan is good: `neotrade paper-execute --confirm` (optional; not daily)

If still `accepted` / 0 positions deep into the session: check Alpaca dashboard + order status; cancel stale day orders if needed.

---

## Daily decision loop (when you want a full pass)

| Step | Command / UI | Done? |
|------|----------------|-------|
| 1. Refresh bars (if cache stale) | `neotrade fetch` | [ ] |
| 2. Latest prices | `neotrade quotes` or Dashboard → Quotes | [ ] |
| 3. Signals | `neotrade signals` or Dashboard → Signals | [ ] |
| 4. Account | `neotrade account` or Dashboard → Account | [ ] |
| 5. Dry-run plan | `neotrade paper-plan` or Dashboard → Plan | [ ] |
| 6. Narrative (optional) | `neotrade advise` or Dashboard → Advise | [ ] |
| 7. Execute (rare) | `neotrade paper-execute --confirm` | [ ] |

**Advise** = human-readable opinion only. It does **not** retrain LightGBM.

---

## Weekly (signals / local models)

- [ ] `neotrade fetch --force` then `neotrade train` (if you want fresher ML)
- [ ] `neotrade bench` — Ollama latency still OK (~few seconds on 3b)
- [ ] Skim `data/learning/events.jsonl` / `bench_latest.json` if curious
- [ ] Optional: rate advise quality in your own notes (formal feedback loop TBD)

---

## Do not forget

- Paper only — never point `ALPACA_BASE_URL` at live trading API
- `ALPACA_DATA_URL=https://data.alpaca.markets` · feed `iex` is fine for free/paper
- Dashboard: `neotrade dashboard` → http://localhost:8501

### Dependencies (verified 2026-07-19 — skip unless something breaks)

| Dep | Status |
|-----|--------|
| `libomp` (Homebrew) | OK — already installed; LightGBM imports |
| Python pkgs (venv) | OK — lightgbm, streamlit, langgraph, pandas, … |
| Ollama service + `llama3.2:3b` | OK — HTTP 200 |
| `.env` paper + data keys | OK |
| `models/signal.txt` | OK |
| `pytest` | 35 passed |
| Alpaca quotes + bench | OK |

If LightGBM ever fails with `libomp.dylib`: `brew reinstall libomp` then re-open the terminal.

---

## Backlog (when ready — not daily)

1. ~~Agent open-order prompt fix~~ (engineering)
2. Market-hours gate on plan/execute
3. Advise → learning policy (log ratings, when to retrain)
4. WebSocket live quotes
5. LightGBM walk-forward / better labels

---

## One-line status (edit when you check)

| Date | Account | Notes |
|------|---------|--------|
| 2026-07-19 | 8 open buys accepted, 0 positions (weekend) | Wait for Mon open |
| | | |
