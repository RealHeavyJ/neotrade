# neotrade Project Goals

## Core Vision
Build a compact, efficient, well-documented Python project that demonstrates the local AI capabilities of the Apple MacBook Neo (A18 Pro, 8GB unified memory).

Interactive market-hours paper-trading decision-support system using:
- Lightweight ML model (LightGBM) for signals on a configurable list of ~20 stocks.
- Multi-agent collaboration (Expert Trading Agent + Business/Performance Analyst) via local Ollama + LangGraph (or CrewAI).
- Profit-focused + diversification-aware logic oriented toward longer-term growth.
- Streamlit interactive dashboard + chat during US market hours.
- Fully local/privacy-first on the Neo (Ollama/MLX + small models).

## Key Constraints (Current)
- Local-only for the running trading system.
- Development uses Grok Build CLI as primary coding/planning agent.
- 1-2 hour focused development sessions.
- Markdown files as persistent memory for goals, tasks, progress, testing, context, and token management.
- GitHub-based with Actions.
- Modern, compact, efficient Pythonic code.
- Well documented (dev guide + user/run guide).

## Success Criteria (v1)
- Functional interactive system runnable on Neo during market hours.
- Clear characterization of Neo's AI performance (inference speed, agent latency, memory usage).
- Professional repo structure ready for long-term development.
- All development tracked in markdown files.

## Future Considerations (Not Active Yet)
- Hybrid mode (desktop heavy lifting + Neo orchestration).
- Potential use of larger Grok models for complex planning/coding tasks while keeping runtime local.

Last updated: 2026-07-15
