"""Paper fill observations → slip calibration for backtest defaults.

Adverse slip_bps (same convention as BT):
  buy:  (fill - mid) / mid * 1e4
  sell: (mid - fill) / mid * 1e4

Positive = worse than mid (costs you). Used to set ``BT_SLIP_BPS`` only when
``n >= MIN_FILLS_FOR_CALIBRATION``.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from neotrade.config.load import project_root
from neotrade.learning.log import append_entry, learning_dir
from neotrade.logging_config import get_logger

log = get_logger("broker.fills")

MIN_FILLS_FOR_CALIBRATION = 20
SLIP_BPS_FLOOR = 1.0
SLIP_BPS_CAP = 50.0
DEFAULT_SLIP_BPS = 5.0


@dataclass(frozen=True)
class FillObservation:
    """One filled (or partially filled) paper order vs reference mid."""

    ts: str
    order_id: str
    symbol: str
    side: str  # buy | sell
    fill_px: float
    mid_px: float
    qty: float
    slip_bps: float
    source: str  # execute | closed_order | manual
    status: str = "filled"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FillObservation:
        return cls(
            ts=str(d.get("ts") or ""),
            order_id=str(d.get("order_id") or ""),
            symbol=str(d.get("symbol") or "").upper(),
            side=str(d.get("side") or "").lower(),
            fill_px=float(d["fill_px"]),
            mid_px=float(d["mid_px"]),
            qty=float(d.get("qty") or 0),
            slip_bps=float(d["slip_bps"]),
            source=str(d.get("source") or "manual"),
            status=str(d.get("status") or "filled"),
        )


@dataclass
class FillCalibration:
    """Aggregate slip stats and optional recommended BT slip."""

    n: int
    median_slip_bps: float | None
    mean_slip_bps: float | None
    p75_slip_bps: float | None
    recommended_slip_bps: float | None
    min_n: int = MIN_FILLS_FOR_CALIBRATION
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "median_slip_bps": self.median_slip_bps,
            "mean_slip_bps": self.mean_slip_bps,
            "p75_slip_bps": self.p75_slip_bps,
            "recommended_slip_bps": self.recommended_slip_bps,
            "min_n": self.min_n,
            "notes": list(self.notes),
            "ready": self.recommended_slip_bps is not None,
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"fills n={self.n} (need ≥{self.min_n} for auto BT slip)",
        ]
        if self.median_slip_bps is not None:
            lines.append(
                f"slip_bps median={self.median_slip_bps:.2f} "
                f"mean={self.mean_slip_bps:.2f} p75={self.p75_slip_bps:.2f}"
            )
        if self.recommended_slip_bps is not None:
            lines.append(
                f"recommended BT slip_bps={self.recommended_slip_bps:.1f} "
                f"(clamped [{SLIP_BPS_FLOOR:.0f},{SLIP_BPS_CAP:.0f}])"
            )
        else:
            lines.append(
                f"recommended BT slip_bps=default ({DEFAULT_SLIP_BPS:.1f}) — "
                f"insufficient fills or no apply"
            )
        for n in self.notes:
            lines.append(f"note: {n}")
        return lines


def fills_path() -> Path:
    return learning_dir() / "fills.jsonl"


def calibration_path() -> Path:
    return learning_dir() / "slip_calibration.json"


def slip_bps_adverse(*, side: str, mid_px: float, fill_px: float) -> float:
    """Adverse slippage in bps vs mid (positive = worse fill)."""
    side_l = side.lower()
    if mid_px <= 0 or fill_px <= 0 or math.isnan(mid_px) or math.isnan(fill_px):
        raise ValueError("mid_px and fill_px must be positive")
    if side_l == "buy":
        return (fill_px - mid_px) / mid_px * 10_000.0
    if side_l == "sell":
        return (mid_px - fill_px) / mid_px * 10_000.0
    raise ValueError("side must be buy or sell")


def make_observation(
    *,
    order_id: str,
    symbol: str,
    side: str,
    fill_px: float,
    mid_px: float,
    qty: float = 0.0,
    source: str = "execute",
    status: str = "filled",
    ts: str | None = None,
) -> FillObservation:
    """Build a fill observation with computed slip_bps."""
    slip = slip_bps_adverse(side=side, mid_px=mid_px, fill_px=fill_px)
    return FillObservation(
        ts=ts or datetime.now(UTC).isoformat(),
        order_id=order_id,
        symbol=symbol.upper(),
        side=side.lower(),
        fill_px=float(fill_px),
        mid_px=float(mid_px),
        qty=float(qty),
        slip_bps=float(slip),
        source=source,
        status=status,
    )


def append_fill(obs: FillObservation) -> Path:
    """Append one observation to fills.jsonl + learning events."""
    path = fills_path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obs.to_dict()) + "\n")
    append_entry("fill_observation", obs.to_dict())
    log.info(
        "fill logged %s %s slip=%.2fbps fill=%.4f mid=%.4f",
        obs.side,
        obs.symbol,
        obs.slip_bps,
        obs.fill_px,
        obs.mid_px,
    )
    return path


def load_fills(*, path: Path | None = None) -> list[FillObservation]:
    """Load fill observations (skips bad lines)."""
    p = path or fills_path()
    if not p.is_file():
        return []
    out: list[FillObservation] = []
    seen: set[str] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            obs = FillObservation.from_dict(d)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        # de-dupe by order_id keeping last
        key = obs.order_id or f"{obs.ts}:{obs.symbol}:{obs.fill_px}"
        if key in seen:
            # replace previous
            out = [o for o in out if (o.order_id or f"{o.ts}:{o.symbol}:{o.fill_px}") != key]
        seen.add(key)
        out.append(obs)
    return out


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        raise ValueError("empty")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = q * (len(sorted_vals) - 1)
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return sorted_vals[lo]
    w = idx - lo
    return sorted_vals[lo] * (1 - w) + sorted_vals[hi] * w


def calibrate_fills(
    observations: list[FillObservation] | None = None,
    *,
    min_n: int = MIN_FILLS_FOR_CALIBRATION,
) -> FillCalibration:
    """Compute slip stats; recommend BT slip when n ≥ min_n."""
    obs = observations if observations is not None else load_fills()
    notes: list[str] = []
    if not obs:
        notes.append("no fill observations — run paper-execute in RTH to log fills")
        return FillCalibration(
            n=0,
            median_slip_bps=None,
            mean_slip_bps=None,
            p75_slip_bps=None,
            recommended_slip_bps=None,
            min_n=min_n,
            notes=notes,
        )
    slips = [o.slip_bps for o in obs]
    # floor negative (price improvement) at 0 for conservative BT cost
    adverse = [max(0.0, s) for s in slips]
    sorted_a = sorted(adverse)
    med = float(statistics.median(sorted_a))
    mean = float(statistics.fmean(sorted_a))
    p75 = float(_percentile(sorted_a, 0.75))
    rec: float | None = None
    if len(obs) >= min_n:
        # use median adverse; clamp
        rec = max(SLIP_BPS_FLOOR, min(SLIP_BPS_CAP, round(med, 1)))
        notes.append(f"n≥{min_n}: auto-recommend enabled")
    else:
        notes.append(f"n={len(obs)} < {min_n}: keep default slip until more fills")
    n_improve = sum(1 for s in slips if s < 0)
    if n_improve:
        notes.append(f"{n_improve}/{len(obs)} fills beat mid (counted as 0 adverse for median)")
    return FillCalibration(
        n=len(obs),
        median_slip_bps=med,
        mean_slip_bps=mean,
        p75_slip_bps=p75,
        recommended_slip_bps=rec,
        min_n=min_n,
        notes=notes,
    )


def save_calibration(cal: FillCalibration, *, path: Path | None = None) -> Path:
    """Persist calibration snapshot for defaults.effective_slip_bps()."""
    p = path or calibration_path()
    src = "fills.jsonl"
    fp = fills_path()
    if fp.is_file():
        try:
            src = str(fp.relative_to(project_root()))
        except ValueError:
            src = str(fp)
    payload = {
        "ts": datetime.now(UTC).isoformat(),
        **cal.to_dict(),
        "source": src,
    }
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    append_entry("slip_calibration", payload)
    return p


def load_saved_calibration(*, path: Path | None = None) -> dict[str, Any] | None:
    p = path or calibration_path()
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def effective_slip_bps(*, fallback: float = DEFAULT_SLIP_BPS) -> float:
    """BT slip default: calibrated median if ready, else package fallback."""
    data = load_saved_calibration()
    if not data:
        return float(fallback)
    rec = data.get("recommended_slip_bps")
    n = int(data.get("n") or 0)
    min_n = int(data.get("min_n") or MIN_FILLS_FOR_CALIBRATION)
    if rec is None or n < min_n:
        return float(fallback)
    try:
        v = float(rec)
    except (TypeError, ValueError):
        return float(fallback)
    return max(SLIP_BPS_FLOOR, min(SLIP_BPS_CAP, v))


def parse_filled_order(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Extract fill fields from Alpaca closed order JSON."""
    status = str(raw.get("status") or "").lower()
    if status not in {"filled", "partially_filled"}:
        return None
    avg = raw.get("filled_avg_price")
    if avg in (None, ""):
        return None
    try:
        fill_px = float(avg)
        qty = float(raw.get("filled_qty") or raw.get("qty") or 0)
    except (TypeError, ValueError):
        return None
    if fill_px <= 0:
        return None
    side = str(raw.get("side") or "").lower()
    if side not in {"buy", "sell"}:
        return None
    return {
        "order_id": str(raw.get("id") or ""),
        "symbol": str(raw.get("symbol") or "").upper(),
        "side": side,
        "fill_px": fill_px,
        "qty": qty,
        "status": status,
        "filled_at": str(raw.get("filled_at") or raw.get("updated_at") or ""),
    }


def mid_from_quote(bid: float | None, ask: float | None, last: float | None = None) -> float | None:
    """Best mid from bid/ask; fall back to last trade."""
    if bid and ask and bid > 0 and ask > 0:
        return (float(bid) + float(ask)) / 2.0
    if last and last > 0:
        return float(last)
    if bid and bid > 0:
        return float(bid)
    if ask and ask > 0:
        return float(ask)
    return None
