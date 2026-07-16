# Token Management - neotrade

## Purpose
Keep development sessions efficient under 1–2 hour focus blocks and limited agent context windows.

## Practices
- Prefer small, targeted prompts and file edits over full-repo dumps.
- Use these markdown files as persistent memory instead of re-explaining history every session.
- Load only the files needed for the current task (`TASKS.md` + relevant code).
- Summarize session outcomes into `PROGRESS.md` and `CONTEXT.md` before ending.
- Avoid pasting large logs or data; store paths and short excerpts.

## Session Checklist
1. Read `PROJECT_GOALS.md` and `TASKS.md` (current priority).
2. Skim latest `PROGRESS.md` / `CONTEXT.md` if resuming.
3. Do the focused work.
4. Update `TASKS.md`, `PROGRESS.md`, and any decisions in `CONTEXT.md`.
5. Note test status in `TESTING.md` when applicable.

## Budget Notes
| Item | Guidance |
|------|----------|
| Session length | 1–2 hours |
| Context sources | Markdown memory first, then code |
| Runtime system | Local-only (Ollama/MLX); no cloud model required for trading loop |
| Dev coding agent | Grok Build CLI |

## Large Artifacts (Do Not Inline)
- Model weights, full market history, raw agent traces — keep on disk; reference by path.

Last updated: 2026-07-15
