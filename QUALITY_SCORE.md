# neotrade — codebase quality score (canonical)

**All coding agents must read this before changing code.**  
Goal: every change **holds or raises** the score; **never regress**.

---

## Current score

| Field | Value |
|-------|--------|
| **Overall** | **7.6 / 10** |
| **Floor (do not go below)** | **7.6** |
| **Target (next milestone)** | **8.5** |
| **Rated** | 2026-07-19 |
| **Rater** | Senior software review (session) |
| **Tests at rating** | 35 passed |

### Dimension scores (baseline)

| Dimension | Score | Notes |
|-----------|------:|-------|
| Architecture / modularity | 8.0 | Clear packages; advise ≠ train |
| Safety / ops | 8.5 | Paper-only, `--confirm`, sleeves |
| Correctness / tests | 7.5 | Unit mocks strong; thin integration |
| Code quality | 7.5 | Post-cleanup; `main.py` still large |
| Docs / self-describing APIs | 7.5 | Google-style on core public APIs |
| ML rigor | 5.5 | Baseline model; weak edge proof |
| Observability | 6.0 | Learning JSONL + bench only |
| Scalability / realtime | 6.0 | REST OK; no WS / hours gate yet |

**Weighted overall ≈ 7.6** — strong local v1 / paper demo; not institutional grade.

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
| P1 | Walk-forward / calibration / baselines | ML rigor, correctness |
| P2 | Structured logging; narrower excepts | Observability, code quality |
| P3 | Advise learning policy + dashboard parity | Product completeness / docs |
| P4 | WS quotes; order lifecycle | Scalability / realtime |

Cosmetic refactors that do not close a gap should still **not** lower any dimension.

---

## Score log

| Date | Overall | Δ | Notes |
|------|--------:|---|-------|
| 2026-07-19 | 7.6 | — | Baseline after v1 + review cleanup |
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
