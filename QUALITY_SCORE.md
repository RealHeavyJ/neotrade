# neotrade — codebase quality score (canonical)

**All coding agents must read this before changing code.**  
Goal: every change **holds or raises** the score; **never regress**.

---

## Current score

| Field | Value |
|-------|--------|
| **Overall** | **8.5 / 10** |
| **Floor (do not go below)** | **7.6** |
| **Target (next milestone)** | **9.0** (ML edge + optional WS) |
| **Rated** | 2026-07-20 (P3 learning policy) |
| **Rater** | Senior review + P0–P4 track complete |
| **Tests at rating** | 71+; policy tests added |

### Dimension scores

| Dimension | Score | Notes |
|-----------|------:|-------|
| Architecture / modularity | 8.0 | Clear packages; advise ≠ train enforced in policy |
| Safety / ops | **8.8** | Paper-only, `--confirm`, sleeves, RTH execute gate |
| Correctness / tests | **8.1** | + learning policy unit tests |
| Code quality | **7.7** | Narrower excepts; less silent swallow |
| Docs / self-describing APIs | **8.0** | user-guide + advise policy documented |
| ML rigor | **6.8** | WF eval present; edge still weak vs always-long |
| Observability | **7.6** | Logging + rated advice journal + smoke |
| Scalability / realtime | **6.8** | REST poller; WS still open |

**Weighted overall ≈ 8.5** — product track complete; **ML edge** is the main path above 8.5.

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
| P4 | WS quotes; order lifecycle | Scalability / realtime |

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
