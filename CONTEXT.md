# Context - neotrade

## What This Project Is
Local-first paper-trading decision-support system for the Apple MacBook Neo, using LightGBM signals, multi-agent collaboration (Ollama + LangGraph), and a Streamlit dashboard.

## Hardware Target
- Apple MacBook Neo (A18 Pro, 8GB unified memory)
- Local inference via Ollama / MLX and small models

## Key Decisions
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Project name | **neotrade** | Locked; no trailing "r" |
| Repo | `~/dev/neotrade` + `github.com/RealHeavyJ/neotrade` | Isolated project root |
| Runtime locality | Fully local for trading system | Privacy + Neo demo |
| Primary agents framework | LangGraph (preferred) over CrewAI | Controllable multi-agent graphs |
| Signal model | LightGBM | Lightweight, fits 8GB unified memory |
| UI | Streamlit | Fast interactive dashboard + chat |
| Dev agent | Grok Build CLI | Primary coding/planning agent |
| Memory | Markdown files | Goals, tasks, progress, testing, context, tokens |

## Open Questions
- Paper broker: Alpaca paper vs local simulator?
- Exact small models for Ollama on Neo?
- Final list of ~20 tickers and config format?

## Related Files
- `PROJECT_GOALS.md` — vision and success criteria
- `TASKS.md` — backlog and session priority
- `PROGRESS.md` — session log and milestones
- `TESTING.md` — test approach and status
- `TOKEN_MANAGEMENT.md` — context/token budget notes

Last updated: 2026-07-15
