# neotrade — operator checklist (human loop)

Until agents can run unattended 24/7, **you** run these loops.  
Paper only. Advise ≠ train. Execute only with `--confirm` when plan is intentional.

**Last ops review:** 2026-07-20 (Mon) — full daily checklist **done**  
**Book snapshot (that check):** equity ≈ $99,954 · cash ≈ $20,208 · **10 positions** · **0 open orders** · fills OK post-open

---

## How to use this file

1. **Daily** — every US market day you care about the book (or any day you touch neotrade).  
2. **Weekly** — once per calendar week (pick a fixed day, e.g. Sunday evening or Friday after close).  
3. Tick boxes in a copy/notes app if you prefer; update the **status log** at the bottom here.  
4. Engineering work (P0–P4) lives in `TASKS.md` — not required for ops health.

```bash
cd ~/dev/neotrade
source .venv/bin/activate    # must source, not execute
```

---

## DAILY (human — until automation)

**When:** Mon–Fri, ideally once after **09:45 ET** (book settled) and optionally once near **15:45 ET** (optional EOD glance).  
**Time:** ~10–15 min full pass; ~3 min light pass.

### A. Session start (every day you operate)

- [ ] Venv active: `source .venv/bin/activate`
- [ ] Ollama up if you will run advise: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:11434/api/tags` → `200`  
      (if down: `brew services start ollama`)
- [ ] Optional smoke: `pytest -q` (after code pulls / env changes only)

### B. Market data + book

- [ ] `neotrade quotes` — prices sane, feed=`iex` (or Dashboard → Quotes)
- [ ] `neotrade account` — note equity, cash, **positions count**, **open_orders**
- [ ] If `open_orders > 0`: note symbols/status; do **not** treat as filled inventory
- [ ] If unexpected flat book or blocked account: check Alpaca paper dashboard

### C. Decision loop (full pass)

| # | Action | Command / UI |
|---|--------|----------------|
| 1 | Refresh bars if cache stale (>~24h or after big moves) | `neotrade fetch` |
| 2 | Signals | `neotrade signals` or Dashboard → Signals |
| 3 | Dry-run plan vs **current** holdings | `neotrade paper-plan` or Dashboard → Plan |
| 4 | Narrative (optional) | `neotrade advise` or Dashboard → Advise |
| 5 | Execute **only if** plan is intentional | `neotrade paper-execute --confirm` |

**Rules**

- Prefer **advise-only** most days; execute is the exception.  
- **Execute is gated:** `neotrade paper-execute` only works **09:30–16:00 ET** on trading days (no pre/after-hours). Check `neotrade session`.  
- Quotes / signals / advise still OK anytime (monitor ≠ trade).  
- Advise is opinion only — does **not** retrain LightGBM.

### D. End of day (optional, ~2 min)

- [ ] `neotrade account` — equity/cash vs morning  
- [ ] One line in **status log** below  
- [ ] No need to execute or retrain daily

### E. Today only — 2026-07-20 follow-ups (new)

Market is open and book is deployed. After morning checklist is done:

- [ ] **Midday / EOD glance:** `neotrade account` once more (P&L sanity; no open_orders stuck)  
- [ ] **Paper-plan with holdings:** confirm intents are mostly holds/trims, not a full re-buy  
- [ ] **Do not** re-run `paper-execute` unless plan shows a deliberate change you want  
- [ ] Optional: Dashboard → Advise once (verify no errors after ScoreResult fixes)  
- [ ] Log outcome in status table (EOD equity/cash)

---

## WEEKLY (human — until automation)

**When:** Once per week (suggested: **Sunday evening** prep, or **Friday after close**).  
**Time:** ~20–40 min.

### Data + model

- [ ] `neotrade fetch --force` — full bar refresh  
- [ ] `neotrade train` — refresh `models/signal.txt`  
- [ ] Spot-check: `neotrade signals` — buy list not nonsense vs your thesis  
- [ ] `neotrade bench` — Ollama still interactive (~few seconds on 3b); note RSS if huge

### Book + risk

- [ ] `neotrade account` — sleeve mix still roughly growth-heavy vs defensive (eyeball)  
- [ ] `neotrade paper-plan` — any large unintended turnover?  
- [ ] Review open risk: max single name still ~≤8% of equity (rough check)  
- [ ] Cancel any **stale** working orders in Alpaca UI if left over from weekends

### Learning / quality (light)

- [ ] Skim `data/learning/events.jsonl` and/or `bench_latest.json`  
- [ ] Optional: 1–5 rating on last advise quality in your notes (formal policy = P3 in `TASKS.md`)  
- [ ] If something broke: note in status log; do not “fix” by deleting tests

### Weekly health

- [ ] `pytest -q` still green after any pulls  
- [ ] Confirm still **paper** keys only (no live URL)  
- [ ] Deps: only if imports fail — see verified table below  

---

## NOT daily (agents / eng will own later)

These stay in **`TASKS.md`** until built — then ops shrinks:

| Until this ships… | You still must… |
|-------------------|-----------------|
| ~~P0 market-hours gate~~ | ~~Done — execute blocked off RTH~~ |
| Unattended scheduler | Run daily/weekly yourself |
| ~~REST quote monitor (P4)~~ | Optional: `neotrade monitor -v` instead of manual refresh |
| Unattended 24/7 driver | Still manual daily/weekly |
| Advise learning policy | Manually judge advise; don’t feed it to train |
| 24/7 agent driver | No overnight automation — laptop + you |

**24/7 goal (future):** scheduled fetch → signal → plan → (gated) execute → advise log, with hours/risk guards. **Not available yet.**

---

## Standing rules (always)

- Paper only — never live `ALPACA_BASE_URL`  
- Data: `ALPACA_DATA_URL=https://data.alpaca.markets` · feed `iex` OK  
- `source .venv/bin/activate` (never execute `activate`)  
- Dashboard: `neotrade dashboard` → http://localhost:8501  
- Quality floor for code changes: `QUALITY_SCORE.md` (agents); ops doesn’t change the score  

### Dependencies (skip unless broken)

| Dep | Status |
|-----|--------|
| libomp / LightGBM | OK (verified 2026-07-19) |
| Ollama + llama3.2:3b | OK when service running |
| `.env` paper + data | OK |
| Tests | **38 passed** (last eng check) |

---

## Status log

| Date | Equity | Cash | Pos | Open orders | Notes |
|------|--------|------|-----|-------------|--------|
| 2026-07-19 | 100000 | 100000 | 0 | 8 accepted | Weekend; waits for open |
| 2026-07-20 AM | ~99954 | ~20208 | **10** | **0** | Fills OK; daily checklist completed by user |
| 2026-07-20 EOD | 100,297.42 | 20,207.56 | 10 | 0 | Day 1 filled all advised |
| | | | | | |

---

## Copy-paste: minimum daily commands

```bash
cd ~/dev/neotrade && source .venv/bin/activate
neotrade quotes
neotrade account
neotrade signals
neotrade paper-plan
# neotrade advise          # optional
# neotrade paper-execute --confirm   # rare
```

## Copy-paste: minimum weekly commands

```bash
cd ~/dev/neotrade && source .venv/bin/activate
neotrade fetch --force && neotrade train
neotrade signals && neotrade account && neotrade paper-plan
neotrade bench && pytest -q
```

Last updated: 2026-07-20
