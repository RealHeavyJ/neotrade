"""Operator automation (scheduled jobs, no execute)."""

from neotrade.ops.weekly import WeeklyResult, run_weekly_promote

__all__ = ["WeeklyResult", "run_weekly_promote"]
