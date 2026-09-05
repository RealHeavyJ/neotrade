# neotrade — operator checklist (human loop)

Until agents can run unattended 24/7, **you** run these loops.  
Paper only. Advise ≠ train. Execute only with `--confirm` when plan is intentional.

**Last ops review:** 2026-09-04 (Fri) EOD — equity **$102,241.52**  
**Model gate:** bare BT full PASS · stable/promote **FAIL** (2026-08-22; W1 lost to eq/mom) · top_n=7 rebal=14  
**Next RTH:** 2026-09-07 09:30 ET  
**Day loop:** status → desk → intentional execute OK if RTH + plan (~14d rebalance; desk≠auto-trade)  
**Do not:** multi-open exps · stack more feature drops without one exp

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
| 4 | Desk / narrative | `neotrade desk` (preferred) or `advise` |
| 5 | Execute only if intentional + RTH + promote | `neotrade paper-execute --confirm` (logs fill slip) |
| 6 | Promote snapshot | `neotrade status` |
| 7 | Optional fill calib | `neotrade fills` · `--apply` when n≥20 |

**Rules:** advise-only most days · execute **RTH only** (`neotrade session`) · advise ≠ train.

### D. End of day (~2 min)

- [ ] `neotrade account`
- [ ] Status log line below
- [ ] No need to retrain daily

---

## WEEKLY (human — until automation)

**When:** once/week · **~20–40 min**

### Data + model

- [ ] **`neotrade weekly`** (preferred) — fetch→train→eval→backtest→desk; exit 0 = promote PASS  
  - or manual: `fetch --force` → `train` → `eval` → `backtest` → `desk`
- [ ] `neotrade signals` — sanity if not already via weekly
- [ ] `neotrade bench` — Ollama still OK
- [ ] Optional schedule: `scripts/com.neotrade.weekly.plist` / `./scripts/weekly_promote.sh`

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
| Operator skill track | `docs/OPERATOR_SKILL.md` (stage/score; agents update) |

---

## Status log

| Date | Equity | Cash | Pos | Open | Notes |
|------|--------|------|-----|------|--------|
| 2026-07-19 | 100,000 | 100,000 | 0 | 8 accepted | Pre-open weekend orders |
| 2026-07-20 AM | ~99,954 | ~20,208 | 10 | 0 | Fills OK |
| 2026-07-20 EOD | 100,297 | 20,208 | 10 | 0 | Day 1 live book |
| 2026-07-21 EOD | **101,744** | 20,208 | 10 | 0 | +1.4% vs 7/20 EOD; leaders MU/MRVL/AMD/ARM; lag CRWD |
| 2026-07-25 | **98,909** | 20,208 | 10 | 0 | Weekly: eval OK; BT was FAIL then **strategy fix → BT PASS** (+72% vs eq+39%/mom+44%). Ranked top-5 + mom blend. |
| 2026-07-27 EOD | **98,284** | 2,126 | 7 | 0 | Deployed; top_n book |
| 2026-07-28 EOD | **97,810** | 2,126 | — | — | equity=$97,809.78 · cash=$2,126.28 · bp=$276,418.92 |
| 2026-07-29 EOD | **97,190** | 805 | — | — | equity=$97,190.00 · cash=$805.42 · bp=$273,098.50 |
| 2026-07-30 EOD | **96,416** | 805 | 7 | 0 | equity=$96,416.02 · cash=$805.38 · bp=$270,931.31 · NOW lead / PLTR lag |
| 2026-07-31 AH | **96,903** | 853 | 7 | 0 | equity=$96,902.96 · cash=$853.18 · bp=$272,352.11 · NOW lead / KO lag |
| 2026-08-04 EOD | **101,762** | 853 | 7 | 0 | equity=$101,761.60 · cash=$853.12 · bp=$285,956.22 · NOW/AVGO/ETN/NVDA lead · KO lag |
| 2026-08-05 EOD | **101,469** | 1,280 | 7 | 0 | equity=$101,468.86 · cash=$1,279.83 · bp=$285,648.60 · NVDA/AVGO/ETN lead · PLTR/CRWD lag |
| 2026-08-06 EOD | **101,061** | 1,279 | 7 | 0 | equity=$101,061.46 · cash=$1,279.15 · bp=$284,507.07 · NVDA/AVGO/ETN lead · PLTR lag |
| 2026-08-10 EOD | **104,227** | 1,197 | 7 | 0 | equity=$104,227.37 · cash=$1,196.69 · bp=$293,272.66 · AVGO/NVDA/ETN/PLTR/CRWD lead · JPM flat |
| 2026-08-11 EOD | **104,132** | 1,196 | 7 | 0 | equity=$104,131.74 · cash=$1,196.36 · bp=$293,004.50 · ETN/NVDA/AVGO/PLTR lead · JPM flat |
| 2026-08-12 EOD | **104,398** | 1,196 | 7 | 0 | equity=$104,398.32 · cash=$1,196.36 · bp=$293,750.93 · NVDA/ETN/AVGO lead · NOW flat |
| 2026-08-13 EOD | **105,350** | 1,196 | 7 | 0 | equity=$105,350.31 · cash=$1,196.36 · bp=$296,416.50 · NVDA/ETN/PLTR lead |
| 2026-08-19 EOD | **103,305** | 1,097 | 7 | 0 | equity=$103,304.82 · cash=$1,097.31 · bp=$290,570.27 · NVDA/MRVL/PLTR lead · CEG lag |
| 2026-08-24 EOD | **101,308** | 1,097 | 7 | 0 | equity=$101,308.09 · cash=$1,097.31 · bp=$284,979.42 · PLTR/NVDA/MRVL lead · MU/CEG lag |
| 2026-08-27 EOD | **102,894** | 1,364 | 7 | 0 | equity=$102,894.47 · cash=$1,364.18 · bp=$289,741.53 · PLTR/NVDA lead · MU/AMD lag |
| 2026-08-28 EOD | **101,229** | 1,364 | 7 | 0 | equity=$101,229.01 · cash=$1,364.18 · bp=$285,078.23 · PLTR/NVDA lead · AMD/MU/MRVL lag |
| 2026-09-01 EOD | **99,103** | 1,364 | 7 | 0 | equity=$99,102.52 · cash=$1,364.18 · bp=$279,124.07 · PLTR/NVDA lead · MRVL/AMD lag |
| 2026-09-03 EOD | **101,948** | 985 | 7 | 0 | equity=$101,948.24 · cash=$985.39 · bp=$286,637.54 · NVDA/PLTR/NOW lead · MU flat |
| 2026-09-04 EOD | **102,242** | 1,018 | 7 | 0 | equity=$102,241.52 · cash=$1,018.36 · bp=$287,498.29 · NVDA/PLTR/MU/CEG lead · JNJ flat |

### Weekly model check — 2026-07-25

| Check | Result |
|-------|--------|
| `eval` | mean_acc ~0.52 · edge_al **+0.022** · OK |
| `backtest` (after fix) | signal **+71.9%** · eq **+39%** · mom **+44%** · maxDD 21.9% · sharpe 2.29 |
| Gate | **PASS** — ranked top-N + 40/60 model·mom blend |
| Action | Promote OK on this window; re-run BT after each weekly train |

### Weekly model check — 2026-07-31

| Check | Result |
|-------|--------|
| `fetch` → `train` → `eval` → `backtest` | ran (~0.5h artifact age) |
| `eval` | mean_acc **0.498** · vs always-long **−0.002** · vs mom **+0.012** · Brier 0.264 · leakage OK |
| `backtest` full sample | signal **+215%** · eq **+116%** · mom **+138%** · maxDD **21.9%** · sharpe **2.43** · full_gate **PASS** |
| stable multi-window | **1/3** pass (need ≥2/3) → **stable_gate FAIL** → **promote=FAIL** |
| W0 2024-07→2025-08 | sig +15% · eq +19% · mom +19% · FAIL (lost to baselines) |
| W1 2025-01→2026-02 | sig +46% · eq +40% · mom +42% · **PASS** |
| W2 2025-06→2026-07 | sig +7% · eq +22% · mom +37% · FAIL (recent window weak) |
| Experiments | rebal=7 runs closed (mix fail/abandon; one historical pass) · **0 open** |
| Fills | n=1/20 (no slip calib yet) |
| Action | **Do not promote** new confidence; paper book OK to hold; research = why W0/W2 lose |

### Research B — 2026-08-01 (stable_gate diagnose)

| Check | Result |
|-------|--------|
| Exp | `4173bf84` complete · outcome auto **fail** (defaults unchanged; promote still false) |
| `eval --ablate` | baseline acc **0.501** edge_mom **+0.014** |
| most useful groups | **returns** (Δacc −0.007) · **cs** (−0.007) · volume/trend ~flat |
| slightly harmful | **vol** (dropping it Δacc **+0.0045**) — do not drop yet without BT confirm |
| bare BT (regime ON, no-save) | full PASS · stable **2/3** · W2 FAIL sig +15% vs mom +41% · promote **FAIL** |
| A/B `--no-regime` (no-save) | full PASS · stable **3/3** · W2 PASS sig +35% · promote **True** |
| Prior | rebal=7 mostly fail — leave **rebal=14** |
| Learning | Regime filter helps risk-off narrative but **hurts recent window vs mom** on this tape |
| Next exp (one) | `BT_USE_REGIME=False` → bare `backtest` **with save** → keep only if stable PASS holds · else revert |

### Research — 2026-08-01 exp `BT_USE_REGIME=False` **KEPT**

| Check | Result |
|-------|--------|
| Code | `defaults.BT_USE_REGIME=False` · `BacktestConfig` field aligned · CLI uses `D.BT_USE_REGIME` (was ignoring default) |
| bare `backtest` (save) | regime=False · full PASS · stable **3/3** · promote **PASS** |
| signal | ret **+191%** · maxDD **23.9%** · sharpe **2.26** · vs eq +60% · vs mom +63% |
| W0/W1/W2 | all PASS (W2 sig +35% vs prior FAIL under regime ON) |
| CI | `./scripts/ci_local.sh` OK · **149** passed |
| Note | Live score blend still regime-aware; only **portfolio BT** filter off |

### Research — 2026-08-01 exp drop `vol` group **KEPT**

| Check | Result |
|-------|--------|
| Code | `FEATURE_EXCLUDE_GROUPS=("vol",)` + `model_feature_names` honors it |
| Features | 31 → **26** (dropped vol_10/20, vol_ratio, atr_14_pct, high_low_range) |
| bare BT | promote **PASS** · stable **3/3** · sig **+194.5%** (was +191.2%) |
| W2 | **+42.8%** (was +34.7%) · still beats eq; under mom slightly OK for gate |
| Tradeoff | maxDD **25.7%** vs 23.9% · sharpe **2.22** vs 2.26 |
| eval/model | refreshed age **0h** · mean_acc 0.497 · edge_mom +0.011 |
| #3 hygiene | **done** as part of this train/eval/BT |

### Latest book snapshot — 2026-07-25

equity≈$98,909 · cash≈$20,208 · 10 pos · 0 open · ACTIVE · weekend (execute blocked until Mon RTH)

### EOD — 2026-07-27 (Mon)

| Field | Value |
|-------|--------|
| equity | **$98,284.46** |
| cash | **$2,126.32** |
| positions | **7** (top_n book) · 0 open orders |
| blocked / PDT | False / False |
| names | AVGO CEG JNJ JPM NOW NVDA PLTR |
| note | vs 7/25: equity −$625 · cash −$18k (deployed into 7 names) · uPL leaders JNJ/NOW; NVDA lag |

### EOD — 2026-07-28 (Tue)

| Field | Value |
|-------|--------|
| equity | **$97,809.78** |
| cash | **$2,126.28** |
| buying_power | **$276,418.92** |
| note | vs 7/27 EOD: equity −$474.68 · cash flat |

### EOD — 2026-07-29 (Wed)

| Field | Value |
|-------|--------|
| equity | **$97,190.00** |
| cash | **$805.42** |
| buying_power | **$273,098.50** |
| note | vs 7/28 EOD: equity −$619.78 · cash −$1,320.86 (further deployed) |

### EOD — 2026-07-30 (Thu)

| Field | Value |
|-------|--------|
| equity | **$96,416.02** |
| cash | **$805.38** |
| buying_power | **$270,931.31** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| names | AVGO JNJ JPM KO NOW PEP PLTR |
| uPL leaders | NOW +$1,112 · AVGO +$418 · JPM +$94 |
| uPL laggards | PLTR −$834 · PEP −$398 · KO −$303 · JNJ −$184 |
| note | vs 7/29 EOD: equity −$773.98 · cash flat · book rotated (CEG/NVDA out; KO/PEP in) |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AVGO | 36 | $14,004.00 | 389.00 | +$418.32 |
| JNJ | 51 | $13,035.09 | 255.59 | −$184.36 |
| JPM | 38 | $13,338.76 | 351.02 | +$93.87 |
| KO | 156 | $13,771.68 | 88.28 | −$302.64 |
| NOW | 135 | $14,786.55 | 109.53 | +$1,112.40 |
| PEP | 96 | $13,394.88 | 139.53 | −$398.40 |
| PLTR | 108 | $13,279.68 | 122.96 | −$833.77 |

### EOD/AH — 2026-07-31 (Fri)

| Field | Value |
|-------|--------|
| equity | **$96,902.96** |
| cash | **$853.18** |
| buying_power | **$272,352.11** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| names | AVGO CEG ETN JPM KO NOW NVDA |
| uPL leaders | NOW +$1,229 · ETN +$389 · AVGO +$378 · NVDA +$241 · JPM +$121 |
| uPL laggards | KO −$393 · CEG +$8 flat |
| note | vs 7/30 EOD: equity +$486.94 · cash +$47.80 · book rotated (JNJ/PEP/PLTR out; CEG/ETN/NVDA in) |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AVGO | 36 | $13,964.04 | 387.89 | +$378.36 |
| CEG | 52 | $13,593.88 | 261.42 | +$7.84 |
| ETN | 31 | $12,789.67 | 412.57 | +$388.74 |
| JPM | 38 | $13,366.12 | 351.74 | +$121.23 |
| KO | 156 | $13,681.20 | 87.70 | −$393.12 |
| NOW | 135 | $14,903.18 | 110.39 | +$1,229.03 |
| NVDA | 69 | $13,751.70 | 199.30 | +$241.48 |

### EOD — 2026-08-04 (Mon)

| Field | Value |
|-------|--------|
| equity | **$101,761.60** |
| cash | **$853.12** |
| buying_power | **$285,956.22** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| names | AVGO CEG ETN JPM KO NOW NVDA |
| uPL leaders | NOW +$2,240 · AVGO +$1,484 · ETN +$1,415 · NVDA +$1,408 · CEG +$466 · JPM +$363 |
| uPL laggards | KO −$543 |
| fill_calib | n=1/20 · bt_slip_bps=5.0 · median=1.7 |
| note | vs 7/31 AH: equity **+$4,858.64** · cash flat · same 7 names · book recovered above $100k start |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AVGO | 36 | $15,069.60 | 418.60 | +$1,483.92 |
| CEG | 52 | $14,051.96 | 270.23 | +$465.92 |
| ETN | 31 | $13,816.08 | 445.68 | +$1,415.15 |
| JPM | 38 | $13,607.80 | 358.10 | +$362.91 |
| KO | 156 | $13,531.44 | 86.74 | −$542.88 |
| NOW | 135 | $15,913.80 | 117.88 | +$2,239.65 |
| NVDA | 69 | $14,917.80 | 216.20 | +$1,407.58 |

### EOD — 2026-08-05 (Tue)

| Field | Value |
|-------|--------|
| equity | **$101,468.86** |
| cash | **$1,279.83** |
| buying_power | **$285,648.60** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| names | AVGO CEG CRWD ETN JPM NVDA PLTR |
| uPL leaders | NVDA +$1,676 · AVGO +$1,525 · ETN +$1,441 · JPM +$417 · CEG +$318 |
| uPL laggards | PLTR −$273 · CRWD −$242 |
| note | vs 8/04 EOD: equity **−$292.74** · cash **+$426.71** · book rotated (KO/NOW out; CRWD/PLTR in) |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AVGO | 36 | $15,111.00 | 419.75 | +$1,525.32 |
| CEG | 52 | $13,904.28 | 267.39 | +$318.24 |
| CRWD | 68 | $14,263.00 | 209.75 | −$242.08 |
| ETN | 31 | $13,841.50 | 446.50 | +$1,440.57 |
| JPM | 38 | $13,662.14 | 359.53 | +$417.25 |
| NVDA | 69 | $15,186.21 | 220.09 | +$1,675.99 |
| PLTR | 90 | $14,220.90 | 158.01 | −$272.58 |

### EOD — 2026-08-06 (Wed)

| Field | Value |
|-------|--------|
| equity | **$101,061.46** |
| cash | **$1,279.15** |
| buying_power | **$284,507.07** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| names | AVGO CEG CRWD ETN JPM NVDA PLTR |
| uPL leaders | NVDA +$1,604 · AVGO +$1,578 · ETN +$1,516 · JPM +$336 · CEG +$95 |
| uPL laggards | PLTR −$471 · CRWD −$202 |
| note | vs 8/05 EOD: equity **−$407.40** · cash flat · same 7 names |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AVGO | 36 | $15,163.20 | 421.20 | +$1,577.52 |
| CEG | 52 | $13,681.20 | 263.10 | +$95.16 |
| CRWD | 68 | $14,303.12 | 210.34 | −$201.96 |
| ETN | 31 | $13,917.14 | 448.94 | +$1,516.21 |
| JPM | 38 | $13,581.20 | 357.40 | +$336.31 |
| NVDA | 69 | $15,114.45 | 219.05 | +$1,604.23 |
| PLTR | 90 | $14,022.00 | 155.80 | −$471.48 |

### EOD — 2026-08-10 (Sun snapshot)

| Field | Value |
|-------|--------|
| equity | **$104,227.37** |
| cash | **$1,196.69** |
| buying_power | **$293,272.66** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| names | AVGO CRWD ETN JPM NOW NVDA PLTR |
| uPL leaders | AVGO +$1,662 · NVDA +$1,580 · ETN +$1,393 · PLTR +$1,121 · CRWD +$795 · NOW +$206 |
| uPL laggards | JPM −$9 flat |
| note | vs 8/06 EOD: equity **+$3,165.91** · cash **−$82.46** · book rotated (CEG out; NOW in; JPM qty 38→39) |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AVGO | 36 | $15,247.80 | 423.55 | +$1,662.12 |
| CRWD | 68 | $15,300.00 | 225.00 | +$794.92 |
| ETN | 31 | $13,793.76 | 444.96 | +$1,392.83 |
| JPM | 39 | $14,015.82 | 359.38 | −$9.36 |
| NOW | 110 | $13,968.90 | 126.99 | +$205.70 |
| NVDA | 69 | $15,090.30 | 218.70 | +$1,580.08 |
| PLTR | 90 | $15,614.10 | 173.49 | +$1,120.62 |

### EOD — 2026-08-11 (Mon)

| Field | Value |
|-------|--------|
| equity | **$104,131.74** |
| cash | **$1,196.36** |
| buying_power | **$293,004.50** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| status | ACTIVE |
| names | AVGO CRWD ETN JPM NOW NVDA PLTR |
| uPL leaders | ETN +$1,804 · NVDA +$1,544 · AVGO +$1,412 · PLTR +$1,068 · CRWD +$548 · NOW +$179 · JPM +$97 |
| note | vs 8/10 EOD: equity **−$95.63** · cash flat · same 7 names |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AVGO | 36 | $14,997.24 | 416.59 | +$1,411.56 |
| CRWD | 68 | $15,053.16 | 221.37 | +$548.08 |
| ETN | 31 | $14,204.94 | 458.22 | +$1,804.01 |
| JPM | 39 | $14,121.90 | 362.10 | +$96.72 |
| NOW | 110 | $13,942.50 | 126.75 | +$179.30 |
| NVDA | 69 | $15,053.73 | 218.17 | +$1,543.51 |
| PLTR | 90 | $15,561.90 | 172.91 | +$1,068.42 |

### EOD — 2026-08-12 (Tue)

| Field | Value |
|-------|--------|
| equity | **$104,398.32** |
| cash | **$1,196.36** |
| buying_power | **$293,750.93** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| status | ACTIVE |
| names | AVGO CRWD ETN JPM NOW NVDA PLTR |
| uPL leaders | NVDA +$1,977 · ETN +$1,858 · AVGO +$1,435 · PLTR +$857 · CRWD +$584 · JPM +$233 |
| uPL laggards | NOW −$25 flat |
| note | vs 8/11 EOD: equity **+$266.58** · cash flat · same 7 names |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AVGO | 36 | $15,020.64 | 417.24 | +$1,434.96 |
| CRWD | 68 | $15,089.20 | 221.90 | +$584.12 |
| ETN | 31 | $14,258.76 | 459.96 | +$1,857.83 |
| JPM | 39 | $14,258.01 | 365.59 | +$232.83 |
| NOW | 110 | $13,737.90 | 124.89 | −$25.30 |
| NVDA | 69 | $15,487.05 | 224.45 | +$1,976.83 |
| PLTR | 90 | $15,350.40 | 170.56 | +$856.92 |

### EOD — 2026-08-13 (Wed)

| Field | Value |
|-------|--------|
| equity | **$105,350.31** |
| cash | **$1,196.36** |
| buying_power | **$296,416.50** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| status | ACTIVE |
| names | AVGO CRWD ETN JPM NOW NVDA PLTR |
| uPL leaders | NVDA +$2,037 · ETN +$1,644 · PLTR +$1,501 · AVGO +$1,464 · CRWD +$812 · NOW +$262 · JPM +$151 |
| note | vs 8/12 EOD: equity **+$951.99** · cash flat · same 7 names |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AVGO | 36 | $15,049.80 | 418.05 | +$1,464.12 |
| CRWD | 68 | $15,317.00 | 225.25 | +$811.92 |
| ETN | 31 | $14,044.55 | 453.05 | +$1,643.62 |
| JPM | 39 | $14,175.72 | 363.48 | +$150.54 |
| NOW | 110 | $14,025.00 | 127.50 | +$261.80 |
| NVDA | 69 | $15,547.08 | 225.32 | +$2,036.86 |
| PLTR | 90 | $15,994.80 | 177.72 | +$1,501.32 |

### EOD — 2026-08-19 (Tue)

| Field | Value |
|-------|--------|
| equity | **$103,304.82** |
| cash | **$1,097.31** |
| buying_power | **$290,570.27** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| status | ACTIVE · paper endpoint ok |
| names | CEG ETN MRVL MU NOW NVDA PLTR |
| uPL leaders | NVDA +$1,601 · MRVL +$1,343 · PLTR +$1,239 · ETN +$879 · NOW +$205 |
| uPL laggards | CEG −$517 · MU −$141 |
| note | vs 8/13 EOD: equity **−$2,045.49** · cash **−$99.05** · book rotated (AVGO/CRWD/JPM out; CEG/MRVL/MU in) |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| CEG | 51 | $13,999.50 | 274.50 | −$516.92 |
| ETN | 31 | $13,280.09 | 428.39 | +$879.16 |
| MRVL | 66 | $15,847.92 | 240.12 | +$1,343.10 |
| MU | 15 | $14,269.20 | 951.28 | −$140.85 |
| NOW | 110 | $13,967.80 | 126.98 | +$204.60 |
| NVDA | 69 | $15,111.00 | 219.00 | +$1,600.78 |
| PLTR | 90 | $15,732.00 | 174.80 | +$1,238.52 |

### EOD — 2026-08-24 (Mon)

| Field | Value |
|-------|--------|
| equity | **$101,308.09** |
| cash | **$1,097.31** |
| buying_power | **$284,979.42** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| status | ACTIVE · paper endpoint ok |
| names | CEG ETN MRVL MU NOW NVDA PLTR |
| uPL leaders | PLTR +$1,362 · NVDA +$971 · MRVL +$886 · ETN +$293 · NOW +$259 |
| uPL laggards | MU −$612 · CEG −$547 |
| note | vs 8/19 EOD: equity **−$1,996.73** · cash flat · same 7 names |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| CEG | 51 | $13,969.92 | 273.92 | −$546.50 |
| ETN | 31 | $12,693.88 | 409.48 | +$292.95 |
| MRVL | 66 | $15,391.20 | 233.20 | +$886.38 |
| MU | 15 | $13,797.75 | 919.85 | −$612.30 |
| NOW | 110 | $14,021.70 | 127.47 | +$258.50 |
| NVDA | 69 | $14,481.03 | 209.87 | +$970.81 |
| PLTR | 90 | $15,855.30 | 176.17 | +$1,361.82 |

### EOD — 2026-08-27 (Thu)

| Field | Value |
|-------|--------|
| equity | **$102,894.47** |
| cash | **$1,364.18** |
| buying_power | **$289,741.53** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| status | ACTIVE · paper endpoint ok |
| names | AMD ETN MRVL MU NVDA PLTR TSM |
| uPL leaders | PLTR +$2,150 · NVDA +$2,111 · ETN +$523 · TSM +$279 · MRVL +$207 |
| uPL laggards | MU −$646 · AMD −$234 |
| note | vs 8/24 EOD: equity **+$1,586.38** · cash **+$266.87** · book rotated (CEG/NOW out; AMD/TSM in) |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AMD | 30 | $14,250.00 | 475.00 | −$234.30 |
| ETN | 31 | $12,923.59 | 416.89 | +$522.66 |
| MRVL | 66 | $14,711.40 | 222.90 | +$206.58 |
| MU | 15 | $13,764.00 | 917.60 | −$646.05 |
| NVDA | 69 | $15,621.60 | 226.40 | +$2,111.38 |
| PLTR | 90 | $16,643.70 | 184.93 | +$2,150.22 |
| TSM | 32 | $13,616.00 | 425.50 | +$278.94 |

### EOD — 2026-08-28 (Fri)

| Field | Value |
|-------|--------|
| equity | **$101,229.01** |
| cash | **$1,364.18** |
| buying_power | **$285,078.23** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| status | ACTIVE · paper endpoint ok |
| names | AMD ETN MRVL MU NVDA PLTR TSM |
| uPL leaders | PLTR +$2,202 · NVDA +$1,524 · ETN +$108 · TSM +$66 |
| uPL laggards | AMD −$503 · MU −$448 · MRVL −$223 |
| note | vs 8/27 EOD: equity **−$1,665.46** · cash flat · same 7 names |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AMD | 30 | $13,981.27 | 466.04 | −$503.03 |
| ETN | 31 | $12,508.50 | 403.50 | +$107.57 |
| MRVL | 66 | $14,281.46 | 216.39 | −$223.36 |
| MU | 15 | $13,962.00 | 930.80 | −$448.05 |
| NVDA | 69 | $15,033.72 | 217.88 | +$1,523.50 |
| PLTR | 90 | $16,695.00 | 185.50 | +$2,201.52 |
| TSM | 32 | $13,402.88 | 418.84 | +$65.82 |

### EOD — 2026-09-01 (Tue)

| Field | Value |
|-------|--------|
| equity | **$99,102.52** |
| cash | **$1,364.18** |
| buying_power | **$279,124.07** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| status | ACTIVE · paper endpoint ok |
| names | AMD ETN MRVL MU NVDA PLTR TSM |
| uPL leaders | PLTR +$1,645 · NVDA +$1,483 |
| uPL laggards | MRVL −$856 · AMD −$763 · MU −$468 · ETN −$311 · TSM −$134 |
| note | vs 8/28 EOD: equity **−$2,126.49** · cash flat · same 7 names · first close under $100k since 8/04 recovery |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| AMD | 30 | $13,721.40 | 457.38 | −$762.90 |
| ETN | 31 | $12,090.31 | 390.01 | −$310.62 |
| MRVL | 66 | $13,648.80 | 206.80 | −$856.02 |
| MU | 15 | $13,942.50 | 929.50 | −$467.55 |
| NVDA | 69 | $14,993.01 | 217.29 | +$1,482.79 |
| PLTR | 90 | $16,138.80 | 179.32 | +$1,645.32 |
| TSM | 32 | $13,203.52 | 412.61 | −$133.54 |

### EOD — 2026-09-03 (Thu)

| Field | Value |
|-------|--------|
| equity | **$101,948.24** |
| cash | **$985.39** |
| buying_power | **$286,637.54** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| status | ACTIVE · paper endpoint ok |
| names | CEG JNJ KO MU NOW NVDA PLTR |
| uPL leaders | NVDA +$2,360 · PLTR +$1,932 · NOW +$571 · JNJ +$167 · CEG +$159 · KO +$109 |
| uPL laggards | MU −$21 flat |
| note | vs 9/01 EOD: equity **+$2,845.72** · cash **−$378.79** · book rotated (AMD/ETN/MRVL/TSM out; CEG/JNJ/KO/NOW in; MU/NVDA/PLTR kept) |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| CEG | 49 | $14,000.28 | 285.72 | +$158.76 |
| JNJ | 52 | $14,478.36 | 278.43 | +$167.44 |
| KO | 130 | $11,555.70 | 88.89 | +$108.56 |
| MU | 15 | $14,389.50 | 959.30 | −$20.55 |
| NOW | 98 | $14,243.32 | 145.34 | +$570.90 |
| NVDA | 69 | $15,870.69 | 230.01 | +$2,360.47 |
| PLTR | 90 | $16,425.00 | 182.50 | +$1,931.52 |

### EOD — 2026-09-04 (Fri)

| Field | Value |
|-------|--------|
| equity | **$102,241.52** |
| cash | **$1,018.36** |
| buying_power | **$287,498.29** |
| positions | **7** · open_orders **0** |
| blocked / PDT | False / False |
| status | ACTIVE · paper endpoint ok |
| names | CEG JNJ MU NOW NVDA PLTR VST |
| uPL leaders | NVDA +$2,385 · PLTR +$1,196 · MU +$839 · CEG +$808 · NOW +$171 · VST +$81 |
| uPL laggards | JNJ +$1 flat |
| note | vs 9/03 EOD: equity **+$293.28** · cash **+$32.97** · book rotated (KO out; VST in; JNJ/CEG/MU/NOW/NVDA/PLTR kept) |

| Symbol | qty | mv | px | uPL |
|--------|-----|-----|-----|-----|
| CEG | 49 | $14,649.04 | 298.96 | +$807.52 |
| JNJ | 52 | $14,311.96 | 275.23 | +$1.04 |
| MU | 15 | $15,248.85 | 1016.59 | +$838.80 |
| NOW | 98 | $13,843.48 | 141.26 | +$171.06 |
| NVDA | 69 | $15,894.84 | 230.36 | +$2,384.62 |
| PLTR | 90 | $15,689.70 | 174.33 | +$1,196.22 |
| VST | 77.5974 | $11,585.29 | 149.30 | +$80.76 |

---

## Copy-paste

**Daily**
```bash
cd ~/dev/neotrade && source .venv/bin/activate
neotrade session && neotrade quotes && neotrade account
neotrade signals && neotrade paper-plan
neotrade desk                 # preferred over advise alone
# neotrade paper-execute --confirm   # RTH only, rare, after desk
```

**Weekly**
```bash
cd ~/dev/neotrade && source .venv/bin/activate
neotrade fetch --force && neotrade train && neotrade eval && neotrade backtest
# bare backtest = production defaults (2y, slip, multi-window); do not use --fast for promote
neotrade signals && neotrade account && neotrade paper-plan
neotrade desk
neotrade bench && pytest -q && ./scripts/ci_local.sh
```

Last updated: 2026-09-04 EOD (equity $102,241.52 · cash $1,018.36 · bp $287,498.29 · 7 pos)
