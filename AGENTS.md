# Agent instructions — neotrade

For every coding/planning agent (Grok Build CLI, subagents, future tools).

## Before any code change

1. Read **`QUALITY_SCORE.md`** (score floor + non-regression policy).  
2. Read **`TASKS.md`** top + “close senior-review gaps” if doing quality work.  
3. Prefer one track that **improves** the score (P0–P4). Do not rebuild finished v1 layers.

## Quality rule (non-negotiable)

- **Current overall: 7.6 / 10. Floor: 7.6.**  
- Changes must **hold or raise** the overall score.  
- **Never** ship a change that would drop overall below the floor.  
- Do not regress safety (paper-only, `--confirm`), tests, or locked decisions in `CONTEXT.md`.

## After code changes

1. `source .venv/bin/activate && pytest -q`  
2. `ruff check src/neotrade tests` when practical  
3. If architecture/quality shifted: update `QUALITY_SCORE.md` score log (honest)  
4. Touch `PROGRESS.md` / `TASKS.md` only as needed — keep memory tight (`TOKEN_MANAGEMENT.md`)

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

Last updated: 2026-07-19
