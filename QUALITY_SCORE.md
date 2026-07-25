# neotrade — codebase quality score (canonical)

**All coding agents must read this before changing code.**  
Goal: every change **holds or raises** the score; **never regress**.

---

## Current score

| Field | Value |
|-------|--------|
| **Overall** | **9.3 / 10** |
| **Floor (do not go below)** | **7.6** |
| **Target (next milestone)** | **9.4** (longer history / fill realism) |
| **Rated** | 2026-07-25 (experiment ledger) |
| **Rater** | Closed improve loop |
| **Tests at rating** | 102+; experiment tests |

### Dimension scores

| Dimension | Score | Notes |
|-----------|------:|-------|
| Architecture / modularity | 8.3 | desk packet + experiment ledger |
| Safety / ops | **8.9** | desk blocks execute off RTH / promote no |
| Correctness / tests | **8.5** | + experiment ledger tests |
| Code quality | **7.7** | Narrower excepts; less silent swallow |
| Docs / self-describing APIs | **8.5** | experiment loop documented |
| ML rigor | **8.5** | multi-window + cost stress + regime |
| Observability | **8.3** | experiments.jsonl before/after gates |
| Scalability / realtime | **7.3** | REST poller + IEX WebSocket stream |

**Weighted overall ≈ 9.3** — LLM improvement loop is measurable; still no auto-execute.

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
| P4 | ~~WS quotes~~ done; order lifecycle still open | Scalability / realtime |

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
