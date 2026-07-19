from neotrade.agents.llm import MockLLM
from neotrade.perf.bench import BenchReport, bench_ollama


def test_bench_report_summary():
    r = BenchReport(ts="t", ollama_ok=True, ollama_model="m", ollama_latency_s=1.5, signal_score_s=0.2, signal_n=22)
    lines = r.summary_lines()
    assert any("ollama" in x for x in lines)


def test_bench_ollama_down(monkeypatch):
    class Down:
        config = type("C", (), {"model": "x"})()

        def ping(self):
            return False

    ok, model, lat, notes = bench_ollama(Down())  # type: ignore[arg-type]
    assert ok is False
    assert lat is None
