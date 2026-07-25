# Agent instructions — neotrade

For every coding/planning agent (Grok Build CLI, subagents, future tools).

## Before any code change

1. Read **`QUALITY_SCORE.md`** (score floor + non-regression policy).  
2. Read **`TASKS.md`** top + “close senior-review gaps” if doing quality work.  
3. Prefer one track that **improves** the score (P0–P4). Do not rebuild finished v1 layers.

## Quality rule (non-negotiable)

- **Current overall: 9.3 / 10. Floor: 7.6.**  
- Changes must **hold or raise** the overall score.  
- **Never** ship a change that would drop overall below the floor.  
- Do not regress safety (paper-only, `--confirm`), tests, or locked decisions in `CONTEXT.md`.  
- Advise logs are **journal only** — never train LightGBM on advise prose/ratings.  
- Prefer `neotrade eval` + `neotrade backtest` before promoting signal models.

## After code changes

1. **Mandatory CI mirror** (same as GitHub Actions — do not skip):  
   ```bash
   source .venv/bin/activate
   ./scripts/ci_local.sh
   # or: ruff check src/neotrade tests && pytest -q
   ```  
2. If architecture/quality shifted: update `QUALITY_SCORE.md` score log (honest)  
3. Touch `PROGRESS.md` / `TASKS.md` only as needed — keep memory tight (`TOKEN_MANAGEMENT.md`)  
4. **Never push** if ruff or pytest fails locally — CI will fail the same way  

## Session close checklist (mandatory)

Run this **before ending any coding or planning session** that changed code, config, or project memory. Skip only pure Q&A with no file edits.

### 1. Verify (if code changed)

- [ ] `./scripts/ci_local.sh` **or** `ruff check src/neotrade tests && pytest -q` (both must pass)  
- [ ] No secrets / `.env` staged for commit  
- [ ] Optional: `pre-commit install` once per clone (blocks bad commits)  

### 2. Memory (keep tight — do not rewrite history)

- [ ] **`PROGRESS.md`**: refresh **top checkpoint only** (what shipped, CLI notes, next default). Date it.  
- [ ] **`TASKS.md`**: mark done items; set **Status / next** to one clear default.  
- [ ] **`QUALITY_SCORE.md`**: if quality/architecture shifted, update dimensions + overall **honestly** and append score log. Overall must stay **≥ floor (7.6)** and prefer **≥ previous overall**.  
- [ ] **`CONTEXT.md`**: only if a **locked decision** changed (broker, labels, gates, etc.).  
- [ ] **`DAILY_TODO.md`**: only if ops cadence or weekly commands changed.  
- [ ] **`TESTING.md` / docs**: only if new tests or user-facing CLI behavior shipped.  
- [ ] **Experiments:** `neotrade experiment list --status open` must show **0 or 1** open.  
      If orphans: `neotrade experiment complete --all` or `reconcile`. **Never leave multi-open.**

### 3. Hand-off line (end of agent reply)

State in one short block:

1. What shipped (1–3 bullets)  
2. Test/score status (`N passed`, overall score if changed)  
3. **Next session default** (single track)  
4. Ops reminder if relevant (`DAILY_TODO`, `backtest` gate, RTH)  

### 4. Do not on close

- Full rewrite of PROGRESS history  
- Duplicate the same status into every markdown file  
- Rebuild finished v1 layers “for cleanliness”  
- Leave TASKS with no clear next item after coding work  
- Leave **open experiment rows** unfinished (complete, abandon, or reconcile)

## Do not

- Require cloud LLMs for runtime agents  
- Enable live (non-paper) trading  
- Train LightGBM on advise prose  
- Commit `.env` or secrets  
- Delete or skip tests to pass CI  

## Memory map

| File | Use |
|------|-----|
| `QUALITY_SCORE.md` | Score + non-regression |
| `TASKS.md` | What to build next |
| `CONTEXT.md` | Locked decisions |
| `PROGRESS.md` | Restart checkpoint |
| `DAILY_TODO.md` | Human ops only |

Last updated: 2026-07-20
