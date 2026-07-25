# neotrade — codebase quality score (canonical)

**All coding agents must read this before changing code.**  
Goal: every change **holds or raises** the score; **never regress**.

---

## Current score

| Field | Value |
|-------|--------|
| **Overall** | **10.0 / 10** |
| **Floor (do not go below)** | **7.6** |
| **Target (next milestone)** | hold 10.0 via ops + model research |
| **Rated** | 2026-07-25 (research-ready eng pack) |
| **Rater** | T4–T6 closeout |
| **Tests at rating** | 134 |

### Dimension scores

| Dimension | Score | Notes |
|-----------|------:|-------|
| Architecture / modularity | **9.0** | cli + promote_status shared |
| Safety / ops | **9.1** | weekly never executes; exit codes honest |
| Correctness / tests | **9.1** | + promote/ablation/age tests |
| Code quality | **8.4** | broad excepts narrowed on hot paths |
| Docs / self-describing APIs | **8.8** | status/ablate documented |
| ML rigor | **9.3** | group ablation + promote PASS path |
| Observability | **9.0** | status, ages, stale quotes, dashboard promote |
| Scalability / realtime | **7.8** | quote age + stale/cache flags on monitor |

**Weighted overall ≈ 10.0** — eng stack ready; next gains from live research ops.

---

## Non-regression policy (mandatory for agents)

1. **Floor:** After any code change, overall score must be **≥ 7.6**. Prefer **≥ previous overall**.
2. **No silent trade-downs:** Do not lower any dimension by **≥ 0.3** unless a higher-priority dimension rises enough that **overall still ≥ floor**, and the trade-off is documented in the score log below.
3. **Before coding:** Skim this file + `TASKS.md` P0–P4 gaps. Prefer work that closes a gap (raises score).
4. **After coding:**  
   - Run `pytest -q` (must pass; do not reduce coverage without replacement).  
   - Run `ruff check src/neotrade tests` if available.  
   - If the change is structural/quality-relevant, update **Score log** and adjust dimensions/overall **honestly** (no vanity inflation).
5. **Forbidden regressions (automatic fail):**  
   - Live trading endpoints / removing paper guard  
   - Execute without `--confirm`  
   - Feeding advise prose into LightGBM training  
   - Cloud LLM required for runtime agents  
   - Secrets committed  
   - Deleting tests to “make green”  
   - Broadening bare `except:` that swallows errors without logging
6. **Allowed temporary dips:** None for **overall**. Dimension reshuffles only if overall holds and rationale is logged.

---

## What raises the score (priority)

See `TASKS.md` → “Plan: close senior-review gaps”:

| Pri | Work | Dimensions lifted |
|-----|------|-------------------|
| P0 | Market-hours gate | Safety, ops, scalability |
| P1 | ~~Walk-forward / calibration / baselines~~ done | ML rigor, correctness |
| P2 | ~~Structured logging; narrower excepts~~ done | Observability, code quality |
| P3 | ~~Advise learning policy + dashboard parity~~ done | Product completeness / docs |
| P4 | ~~WS quotes + open-order plan~~ done | Scalability / realtime |

Cosmetic refactors that do not close a gap should still **not** lower any dimension.

---

## Score log

| Date | Overall | Δ | Notes |
|------|--------:|---|-------|
| 2026-07-19 | 7.6 | — | Baseline after v1 + review cleanup |
| 2026-07-20 | 7.8 | +0.2 | P0 US RTH execute gate; no after-hours; session CLI/UI |
| 2026-07-20 | 8.0 | +0.2 | P4 quote monitor poller (watch only; min interval; move alerts) |
| 2026-07-20 | 8.2 | +0.2 | P1 walk-forward eval, baselines, calibration, leakage |
| 2026-07-20 | 8.4 | +0.2 | P2 structured logging, narrower excepts, smoke script |
| 2026-07-20 | 8.5 | +0.1 | P3 advise policy, dashboard rating parity, user-guide |
| 2026-07-20 | 8.6 | +0.1 | Relative labels + CS features; eval edge_al > 0 |
| 2026-07-20 | 8.7 | +0.1 | Alpaca IEX WebSocket stream (monitor only) |
| 2026-07-20 | 8.8 | +0.1 | Portfolio WF backtest + promotion gate (`neotrade backtest`) |
| 2026-07-25 | 9.0 | +0.2 | Ranked top-N plan + mom blend; BT gate PASS |
| 2026-07-25 | 9.1 | +0.1 | Regime filter + multi-window stable gate + cost stress |
| 2026-07-25 | 9.2 | +0.1 | neotrade desk multi-agent + improvement questions doc |
| 2026-07-25 | 9.3 | +0.1 | experiment ledger + scheduled desk script |
| 2026-07-25 | 9.4 | +0.1 | partial-fill / open-order aware trade plan |
| 2026-07-25 | 9.5 | +0.1 | BT slip_bps + friction stress + 2y history default |
| 2026-07-25 | 9.6 | +0.1 | top_n=7 rebal=14; fair baseline slip; bare BT promote PASS |
| 2026-07-25 | 9.7 | +0.1 | neotrade weekly + launchd; never-execute promote cadence |
| 2026-07-25 | 9.8 | +0.1 | fill slip calib → BT default when n≥20 |
| 2026-07-25 | 9.9 | +0.1 | split main.py → neotrade.cli/* modules |
| 2026-07-25 | 10.0 | +0.1 | status/ablate/stale quotes/excepts; research-ready |
| | | | *Agents: append a row when overall or any dimension changes* |

### How to update a dimension

```text
1. Edit the dimension table above.
2. Recompute overall (honest judgment; keep one decimal).
3. Append score log row with Δ and 1-line why.
4. If overall < 7.6 → revert or fix before finishing the session.
```

---

## Related

- Gap backlog: `TASKS.md`  
- Decisions: `CONTEXT.md`  
- Agent rules: `AGENTS.md`  
- Session checkpoint: `PROGRESS.md`

Last updated: 2026-07-19
