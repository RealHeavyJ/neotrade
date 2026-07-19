from neotrade.learning.log import append_advice_feedback, append_entry, load_recent


def test_learning_log_roundtrip(monkeypatch, tmp_path):
    from neotrade.learning import log as log_mod

    monkeypatch.setattr(log_mod, "project_root", lambda: tmp_path)
    append_entry("test", {"x": 1})
    append_advice_feedback(
        stance="cautious",
        top_picks=["ARM"],
        action="hold",
        model="mock",
        rating=4,
    )
    rows = load_recent(10)
    assert len(rows) >= 2
    assert rows[-1]["kind"] == "advice_feedback"
