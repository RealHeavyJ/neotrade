"""Benchmark Ollama + LightGBM on local hardware."""

from __future__ import annotations

import json
import resource
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from neotrade.agents.llm import OllamaClient
from neotrade.config import load_tickers_config
from neotrade.config.load import project_root
from neotrade.data import load_universe_ohlcv
from neotrade.logging_config import get_logger
from neotrade.signals import SignalModel, score_universe

log = get_logger("perf.bench")


@dataclass
class BenchReport:
    ts: str
    ollama_ok: bool = False
    ollama_model: str = ""
    ollama_latency_s: float | None = None
    ollama_tokens_est: int | None = None
    signal_score_s: float | None = None
    signal_n: int = 0
    rss_mb: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_lines(self) -> list[str]:
        lines = [f"bench @ {self.ts}"]
        if self.ollama_ok:
            lines.append(
                f"ollama model={self.ollama_model} latency={self.ollama_latency_s:.2f}s"
                if self.ollama_latency_s is not None
                else f"ollama model={self.ollama_model}"
            )
        else:
            lines.append("ollama: unavailable")
        if self.signal_score_s is not None:
            lines.append(f"signal score: {self.signal_n} names in {self.signal_score_s:.2f}s")
        if self.rss_mb is not None:
            lines.append(f"process rss≈{self.rss_mb:.0f} MB")
        lines.extend(f"note: {n}" for n in self.notes)
        return lines


def _rss_mb() -> float:
    # ru_maxrss is bytes on macOS, KB on Linux — normalize roughly
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if usage > 10_000_000:  # likely bytes (macOS)
        return usage / (1024 * 1024)
    return usage / 1024


def bench_ollama(client: OllamaClient | None = None) -> tuple[bool, str, float | None, list[str]]:
    notes: list[str] = []
    client = client or OllamaClient()
    if not client.ping():
        return False, client.config.model, None, ["Ollama not reachable"]
    prompt = (
        "Reply with exactly one line: STANCE: neutral\n"
        "Keep under 20 tokens."
    )
    t0 = time.perf_counter()
    try:
        text = client.complete(
            "You are a latency probe. Be extremely brief.",
            prompt,
        )
        elapsed = time.perf_counter() - t0
        if len(text) > 500:
            notes.append("response long — consider lower temperature / smaller model")
        if elapsed > 30:
            notes.append("latency >30s — try llama3.2:1b or reduce context")
        elif elapsed > 10:
            notes.append("latency >10s — acceptable on 8GB but monitor thermal")
        else:
            notes.append("latency OK for interactive advise")
        return True, client.config.model, elapsed, notes
    except (RuntimeError, OSError, TimeoutError, ValueError) as exc:
        log.warning("ollama bench failed: %s", exc)
        return False, client.config.model, None, [str(exc)]


def bench_signals(model_path: Path | None = None) -> tuple[float | None, int, list[str]]:
    notes: list[str] = []
    path = model_path or (project_root() / "models" / "signal.txt")
    if not path.is_file():
        return None, 0, ["signal model missing — run neotrade train"]
    cfg = load_tickers_config()
    model = SignalModel.load(path)
    bars = load_universe_ohlcv(cfg, force_refresh=False, root=project_root())
    t0 = time.perf_counter()
    scored = score_universe(model, bars.frames)
    elapsed = time.perf_counter() - t0
    if elapsed > 5:
        notes.append("signal scoring slow — check disk cache")
    else:
        notes.append("signal scoring OK")
    return elapsed, len(scored.rows), notes


def run_full_bench(*, save: bool = True) -> BenchReport:
    report = BenchReport(ts=datetime.now(timezone.utc).isoformat())
    ok, model, lat, n1 = bench_ollama()
    report.ollama_ok = ok
    report.ollama_model = model
    report.ollama_latency_s = lat
    report.notes.extend(n1)
    sig_t, n, n2 = bench_signals()
    report.signal_score_s = sig_t
    report.signal_n = n
    report.notes.extend(n2)
    report.rss_mb = _rss_mb()
    if report.rss_mb and report.rss_mb > 6000:
        report.notes.append("high RSS — close other apps before advise")
    if save:
        out_dir = project_root() / "data" / "learning"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"bench_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        # also keep latest pointer
        (out_dir / "bench_latest.json").write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )
    return report
