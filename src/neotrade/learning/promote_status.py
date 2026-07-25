"""Shared promote / learning artifact status for desk, dashboard, CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from neotrade import defaults as D
from neotrade.broker.fills import calibrate_fills, effective_slip_bps
from neotrade.config.load import project_root


def learning_dir() -> Path:
    return project_root() / "data" / "learning"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def artifact_age_hours(path: Path) -> float | None:
    """Hours since file mtime, or None if missing."""
    if not path.is_file():
        return None
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    now = datetime.now(UTC).timestamp()
    return max(0.0, (now - mtime) / 3600.0)


def promote_from_backtest_dict(data: dict[str, Any]) -> bool | None:
    """Derive promote from backtest_latest.json (gate + stable_gate)."""
    gate = data.get("gate") or {}
    stable = data.get("stable_gate") or {}
    full_pass = bool(gate.get("pass"))
    if not stable:
        return full_pass
    return full_pass and bool(stable.get("pass"))


@dataclass
class PromoteStatus:
    """Snapshot for UI / desk packet."""

    promote: bool | None
    full_gate: bool | None
    stable_gate: bool | None
    signal_ret: float | None
    signal_sharpe: float | None
    signal_maxdd: float | None
    windows_pass: str | None
    top_n: int | None
    rebalance_every: int | None
    bt_age_hours: float | None
    eval_age_hours: float | None
    model_age_hours: float | None
    defaults_top_n: int
    defaults_rebalance_every: int
    slip_bps_effective: float
    fill_n: int
    fill_min_n: int
    notes: list[str] = field(default_factory=list)
    bt_ts: str | None = None

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        if self.promote is None:
            lines.append("promote=unknown (no backtest_latest.json)")
        else:
            lines.append(f"promote={'PASS' if self.promote else 'FAIL'}")
        if self.full_gate is not None:
            lines.append(f"full_gate={self.full_gate} stable_gate={self.stable_gate}")
        if self.signal_ret is not None:
            lines.append(
                f"signal_ret={self.signal_ret:+.2%} sharpe={self.signal_sharpe} "
                f"maxDD={self.signal_maxdd}"
            )
        if self.windows_pass:
            lines.append(f"windows={self.windows_pass}")
        lines.append(
            f"defaults top_n={self.defaults_top_n} rebalance_every={self.defaults_rebalance_every} "
            f"bt_slip_bps={self.slip_bps_effective:.1f}"
        )
        if self.top_n is not None:
            lines.append(
                f"last_bt top_n={self.top_n} rebalance_every={self.rebalance_every}"
            )
        lines.append(
            f"fills n={self.fill_n}/{self.fill_min_n} "
            f"(apply calib when n≥{self.fill_min_n})"
        )
        for label, age in (
            ("backtest", self.bt_age_hours),
            ("eval", self.eval_age_hours),
            ("model", self.model_age_hours),
        ):
            if age is None:
                lines.append(f"{label}_age=missing")
            else:
                stale = " STALE" if age > 168 else ""  # >7d
                lines.append(f"{label}_age_h={age:.1f}{stale}")
        lines.extend(f"note: {n}" for n in self.notes)
        return lines


def load_promote_status(*, model_path: Path | None = None) -> PromoteStatus:
    """Load promote + freshness + defaults for agents/UI."""
    root = project_root()
    learning = learning_dir()
    bt_path = learning / "backtest_latest.json"
    eval_path = learning / "eval_latest.json"
    model = model_path or (root / "models" / "signal.txt")

    bt = _load_json(bt_path)
    notes: list[str] = []
    promote = None
    full_gate = None
    stable_gate = None
    sig_ret = sig_sh = sig_dd = None
    windows_pass = None
    top_n = rebal = None
    bt_ts = None

    if bt:
        promote = promote_from_backtest_dict(bt)
        gate = bt.get("gate") or {}
        stable = bt.get("stable_gate") or {}
        full_gate = bool(gate.get("pass"))
        stable_gate = bool(stable.get("pass")) if stable else None
        sig = bt.get("signal") or {}
        sig_ret = sig.get("total_return")
        sig_sh = sig.get("sharpe")
        sig_dd = sig.get("max_drawdown")
        wins = bt.get("windows") or []
        if wins:
            n_ok = sum(1 for w in wins if w.get("gate_pass"))
            windows_pass = f"{n_ok}/{len(wins)}"
        cfg = bt.get("config") or {}
        top_n = cfg.get("top_n")
        rebal = cfg.get("rebalance_every")
        bt_ts = bt.get("ts")
    else:
        notes.append("run neotrade backtest (or weekly) for promote status")

    cal = calibrate_fills()
    slip = effective_slip_bps(fallback=D.BT_SLIP_BPS)

    return PromoteStatus(
        promote=promote,
        full_gate=full_gate,
        stable_gate=stable_gate,
        signal_ret=float(sig_ret) if sig_ret is not None else None,
        signal_sharpe=float(sig_sh) if sig_sh is not None else None,
        signal_maxdd=float(sig_dd) if sig_dd is not None else None,
        windows_pass=windows_pass,
        top_n=int(top_n) if top_n is not None else None,
        rebalance_every=int(rebal) if rebal is not None else None,
        bt_age_hours=artifact_age_hours(bt_path),
        eval_age_hours=artifact_age_hours(eval_path),
        model_age_hours=artifact_age_hours(model),
        defaults_top_n=D.RISK_TOP_N,
        defaults_rebalance_every=D.BT_REBALANCE_EVERY,
        slip_bps_effective=float(slip),
        fill_n=cal.n,
        fill_min_n=cal.min_n,
        notes=notes,
        bt_ts=str(bt_ts) if bt_ts else None,
    )
