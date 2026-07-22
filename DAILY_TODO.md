# neotrade — operator checklist (human loop)

Until agents can run unattended 24/7, **you** run these loops.  
Paper only. Advise ≠ train. Execute only with `--confirm` when plan is intentional.

**Last ops review:** 2026-07-21 (Tue) EOD — account logged · daily ops **done**  
**Book snapshot:** equity **$101,744** · cash **$20,208** · **10 positions** · **0 open orders** · ~+1.7% vs $100k start  

---

## How to use this file

1. **Daily** — every US market day you care about the book.  
2. **Weekly** — once per week (Sun eve or Fri after close).  
3. Update the **status log** at the bottom when you finish.  
4. Engineering → `TASKS.md`. Coding session end → `AGENTS.md` close checklist.  

```bash
cd ~/dev/neotrade
source .venv/bin/activate    # must source, not execute
```

---

## DAILY (human — until automation)

**When:** Mon–Fri, after **09:45 ET** and/or near **EOD**.  
**Time:** ~10–15 min full · ~3 min light.

### A. Session start

- [ ] `source .venv/bin/activate`
- [ ] Ollama if advising: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:11434/api/tags` → `200`
- [ ] Optional: `pytest -q` after pulls / env changes only

### B. Market data + book

- [ ] `neotrade quotes` — prices sane, feed=`iex`
- [ ] `neotrade account` — equity, cash, positions, open_orders
- [ ] If `open_orders > 0`: not inventory until filled
- [ ] If blocked / flat unexpectedly: check Alpaca paper UI

### C. Decision loop

| # | Action | Command |
|---|--------|---------|
| 1 | Bars if cache stale | `neotrade fetch` |
| 2 | Signals | `neotrade signals` |
| 3 | Dry-run plan | `neotrade paper-plan` |
| 4 | Narrative (optional) | `neotrade advise` (+ `--rating` optional) |
| 5 | Execute only if intentional | `neotrade paper-execute --confirm` |

**Rules:** advise-only most days · execute **RTH only** (`neotrade session`) · advise ≠ train.

### D. End of day (~2 min)

- [ ] `neotrade account`
- [ ] Status log line below
- [ ] No need to retrain daily

---

## WEEKLY (human — until automation)

**When:** once/week · **~20–40 min**

### Data + model

- [ ] `neotrade fetch --force`
- [ ] `neotrade train`
- [ ] `neotrade eval` — note edges
- [ ] `neotrade backtest` — need **gate=PASS** before trusting new model
- [ ] `neotrade signals` — sanity
- [ ] `neotrade bench` — Ollama still OK

### Book + risk

- [ ] `neotrade account` — growth vs defensive eyeball
- [ ] `neotrade paper-plan` — no surprise turnover
- [ ] Single-name ~≤8% equity
- [ ] Cancel stale weekend working orders in Alpaca UI

### Health

- [ ] `pytest -q` after pulls
- [ ] Still **paper** keys only
- [ ] Optional: rate advise / skim `data/learning/`

---

## NOT daily (eng owns)

| Item | You |
|------|-----|
| Unattended scheduler / 24/7 driver | Still manual daily/weekly |
| Backtest gate PASS strategy work | See `TASKS.md` |
| REST/WS monitor tools | Optional: `monitor` / `stream` |

---

## Standing rules

- Paper only — never live trading URL  
- `source .venv/bin/activate` (never execute)  
- Dashboard: `neotrade dashboard`  
- Quality floor for code: `QUALITY_SCORE.md`  

| Dep | Status |
|-----|--------|
| libomp / LightGBM | OK |
| Ollama + llama3.2:3b | OK when service up |
| `.env` paper + data | OK |
| Tests | **94 passed** |

---

## Status log

| Date | Equity | Cash | Pos | Open | Notes |
|------|--------|------|-----|------|--------|
| 2026-07-19 | 100,000 | 100,000 | 0 | 8 accepted | Pre-open weekend orders |
| 2026-07-20 AM | ~99,954 | ~20,208 | 10 | 0 | Fills OK |
| 2026-07-20 EOD | 100,297 | 20,208 | 10 | 0 | Day 1 live book |
| 2026-07-21 EOD | **101,744** | 20,208 | 10 | 0 | +1.4% vs 7/20 EOD; leaders MU/MRVL/AMD/ARM; lag CRWD; no new orders |
| | | | | | |

### Latest book detail — 2026-07-21 EOD

| Symbol | Qty | MV | Px | uPL |
|--------|-----|-----|-----|-----|
| AMD | 16 | 8,637 | 539.82 | +403 |
| ARM | 29 | 8,347 | 287.83 | +369 |
| CRWD | 39 | 7,460 | 191.29 | −456 |
| JNJ | 31 | 7,784 | 251.10 | −79 |
| JPM | 23 | 7,918 | 344.27 | +21 |
| MRVL | 42 | 8,694 | 207.00 | +560 |
| MU | 9 | 8,676 | 964.00 | +674 |
| NOW | 77 | 7,854 | 102.00 | +125 |
| PLTR | 59 | 7,792 | 132.07 | −77 |
| TSM | 20 | 8,374 | 418.68 | +205 |

ACTIVE · bp≈$309k · blocked=False · pdt=False · open_orders=0

---

## Copy-paste

**Daily**
```bash
cd ~/dev/neotrade && source .venv/bin/activate
neotrade session && neotrade quotes && neotrade account
neotrade signals && neotrade paper-plan
# neotrade advise
# neotrade paper-execute --confirm   # RTH only, rare
```

**Weekly**
```bash
cd ~/dev/neotrade && source .venv/bin/activate
neotrade fetch --force && neotrade train && neotrade eval && neotrade backtest
neotrade signals && neotrade account && neotrade paper-plan
neotrade bench && pytest -q
```

Last updated: 2026-07-21 EOD
