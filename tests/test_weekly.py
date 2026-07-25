"""Weekly promote pipeline (mocked runner — no network)."""

from __future__ import annotations

from neotrade.ops.weekly import run_weekly_promote


def test_weekly_promote_pass_exit_0(tmp_path, monkeypatch):
    monkeypatch.setattr("neotrade.ops.weekly.learning_dir", lambda: tmp_path)
    monkeypatch.setattr("neotrade.ops.weekly.append_entry", lambda *a, **k: tmp_path / "e.jsonl")
    monkeypatch.setattr("neotrade.ops.weekly._ollama_up", lambda: False)

    calls: list[list[str]] = []

    def runner(argv):
        calls.append(list(argv))
        cmd = argv[0]
        if cmd == "backtest":
            return 0
        if cmd == "experiment":
            return 0
        return 0

    res = run_weekly_promote(runner=runner, mock_llm=True, save=True)
    assert res.promote is True
    assert res.exit_code == 0
    names = [s.name for s in res.steps]
    assert names[:5] == ["session", "fetch", "train", "eval", "backtest"]
    assert "desk" in names
    assert any(c[0] == "fetch" and "--force" in c for c in calls)
    assert any(c[0] == "backtest" and len(c) == 1 for c in calls)  # bare BT
    assert not any("paper-execute" in c for c in calls)
    assert (tmp_path / "weekly_latest.json").is_file()


def test_weekly_promote_fail_exit_2(tmp_path, monkeypatch):
    monkeypatch.setattr("neotrade.ops.weekly.learning_dir", lambda: tmp_path)
    monkeypatch.setattr("neotrade.ops.weekly.append_entry", lambda *a, **k: tmp_path / "e.jsonl")

    def runner(argv):
        if argv[0] == "backtest":
            return 2
        return 0

    res = run_weekly_promote(runner=runner, skip_desk=True, skip_signals=True, save=False)
    assert res.promote is False
    assert res.exit_code == 2


def test_weekly_hard_fail_stops_before_backtest(tmp_path, monkeypatch):
    monkeypatch.setattr("neotrade.ops.weekly.learning_dir", lambda: tmp_path)
    monkeypatch.setattr("neotrade.ops.weekly.append_entry", lambda *a, **k: tmp_path / "e.jsonl")

    def runner(argv):
        if argv[0] == "train":
            return 1
        return 0

    res = run_weekly_promote(runner=runner, save=False)
    assert res.exit_code == 1
    assert res.promote is False
    names = [s.name for s in res.steps]
    assert "train" in names
    assert "backtest" not in names


def test_weekly_pipeline_argv_has_no_execute(tmp_path, monkeypatch):
    monkeypatch.setattr("neotrade.ops.weekly.learning_dir", lambda: tmp_path)
    monkeypatch.setattr("neotrade.ops.weekly.append_entry", lambda *a, **k: tmp_path / "e.jsonl")
    calls: list[list[str]] = []

    def runner(argv):
        calls.append(list(argv))
        return 0 if argv[0] != "backtest" else 0

    run_weekly_promote(runner=runner, mock_llm=True, save=False)
    flat = [" ".join(c) for c in calls]
    assert not any("execute" in s for s in flat)
    assert not any(c[0] == "paper-execute" for c in calls)
