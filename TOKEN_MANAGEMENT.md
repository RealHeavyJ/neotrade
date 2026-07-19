# Token Management - neotrade

## Purpose
1–2 hour sessions; keep agent context small.

## Bootstrap order (strict)
| Goal | Read only |
|------|-----------|
| Trade / check account | `DAILY_TODO.md` |
| Resume coding | `QUALITY_SCORE.md` → `AGENTS.md` → `PROGRESS.md` (top) → `TASKS.md` → `CONTEXT.md` if needed |
| Then | Open **one** package path for the chosen task |

**Do not** load full PROGRESS history, all tests, or entire `src/` unless debugging.

## Practices
- Markdown memory > re-explaining chat history  
- No secrets / large CSVs / model dumps in prompts  
- End session: update PROGRESS top + TASKS status only  
- Prefer incremental edits over rewrites of working modules  

## Budget
| Item | Guidance |
|------|----------|
| Session | 1–2 h, one track |
| Runtime AI | Local Ollama only |
| Dev agent | Grok Build CLI |
| Artifacts | Paths only (`data/`, `models/`) |

## Anti-patterns
- Re-scaffolding complete features  
- Re-installing verified deps (libomp, ollama) “just in case”  
- Pasting full advise transcripts into train pipelines  
- Shipping changes that drop `QUALITY_SCORE.md` overall below the floor  

## Quality score
Canonical score + non-regression: **`QUALITY_SCORE.md`**. Agent rules: **`AGENTS.md`**.

Last updated: 2026-07-19
