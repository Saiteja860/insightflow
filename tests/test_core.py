"""Unit tests for analysis, insights, db and the FastAPI app."""
from __future__ import annotations

import pytest

from app.analysis import Analysis, analyze_feedback, sentiment_score, tokenize
from app.db import Database
from app.insights import generate_decisions, summarize
from app.seed import SAMPLE_FEEDBACK


# ---------- analysis ----------

def test_tokenize_lowercases():
    assert tokenize("Great PRODUCT!") == ["great", "product"]


def test_positive_sentiment():
    a = analyze_feedback("Great product, I love it!")
    assert a.sentiment == "positive"
    assert a.score > 0.15


def test_negative_sentiment():
    a = analyze_feedback("Terrible app, it crashes and the bugs are unacceptable.")
    assert a.sentiment == "negative"
    assert a.score < -0.15


def test_neutral_sentiment():
    a = analyze_feedback("It is a table.")
    assert a.sentiment == "neutral"
    assert a.score == 0.0


def test_negation_flips_polarity():
    tokens = tokenize("this is not good")
    assert sentiment_score(tokens) < 0


def test_theme_detection():
    a = analyze_feedback("The pricing is too expensive and billing is unclear.")
    assert "pricing" in a.themes


def test_urgency_refund_is_high():
    a = analyze_feedback("I want a refund immediately, this is unacceptable!!")
    assert a.urgency >= 4


def test_analysis_to_dict():
    d = analyze_feedback("nice and easy").to_dict()
    assert set(d) == {"sentiment", "score", "themes", "urgency", "keywords"}


# ---------- insights ----------

def test_summarize_empty():
    s = summarize([])
    assert s["total"] == 0
    assert s["theme_stats"] == []


def test_summarize_sample_data():
    feedback = [{**item, **analyze_feedback(item["text"]).to_dict()} for item in SAMPLE_FEEDBACK]
    s = summarize(feedback)
    assert s["total"] == len(SAMPLE_FEEDBACK)
    assert sum(s["sentiment_counts"].values()) == len(SAMPLE_FEEDBACK)
    assert isinstance(s["nps_like"], int)


def test_generate_decisions_produces_actions():
    feedback = [{**item, **analyze_feedback(item["text"]).to_dict()} for item in SAMPLE_FEEDBACK]
    decisions = generate_decisions(feedback)
    assert decisions, "expected at least one decision from sample data"
    for d in decisions:
        assert d["priority"] in {"critical", "high", "medium", "low"}
        assert d["title"]
        assert d["rationale"]


# ---------- db ----------

def _make_db():
    return Database(":memory:")


def test_db_insert_and_list_feedback():
    db = _make_db()
    a = analyze_feedback("love it, fast and easy")
    fid = db.insert_feedback({"source": "chat", "text": "love it, fast and easy", **a.to_dict()})
    rows = db.all_feedback()
    assert len(rows) == 1
    assert rows[0]["id"] == fid
    assert rows[0]["themes"] == a.themes  # JSON round-trip


def test_db_decision_status_update():
    db = _make_db()
    did = db.insert_decision({"title": "Fix billing", "theme": "pricing",
                              "priority": "high", "rationale": "many complaints"})
    assert db.update_decision_status(did, "done") is True
    assert db.list_decisions()[0]["status"] == "done"
    assert db.update_decision_status(9999, "done") is False


# ---------- API ----------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("INSIGHTFLOW_DB", str(tmp_path / "test.db"))
    # re-import so the app picks up the temp DB path
    from importlib import reload
    import app.main as main_mod
    reload(main_mod)
    from fastapi.testclient import TestClient
    return TestClient(main_mod.app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_submit_feedback_and_insights(client):
    r = client.post("/api/feedback", json={"text": "Amazing app, very fast!", "source": "web"})
    assert r.status_code == 201
    body = r.json()
    assert body["analysis"]["sentiment"] == "positive"

    r = client.post("/api/seed")
    assert r.status_code == 200

    r = client.get("/api/insights")
    assert r.status_code == 200
    assert r.json()["total"] == len(SAMPLE_FEEDBACK) + 1


def test_decision_lifecycle(client):
    client.post("/api/seed")
    r = client.post("/api/decisions/generate")
    assert r.status_code == 200
    created = r.json()["created"]
    assert created, "expected generated decisions"

    did = created[0]["id"]
    r = client.patch(f"/api/decisions/{did}", json={"status": "in_progress"})
    assert r.status_code == 200

    r = client.patch("/api/decisions/999999", json={"status": "done"})
    assert r.status_code == 404


def test_invalid_feedback_rejected(client):
    r = client.post("/api/feedback", json={"text": "ok", "source": "nope"})
    assert r.status_code == 422
