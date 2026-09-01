"""/health is a readiness probe, not a liveness lie.

A host that gates rollout on this endpoint must not promote a kernel that cannot reach its store.
"""
from fastapi.testclient import TestClient

from jidoka_api import state
from jidoka_api.main import app

client = TestClient(app)


def test_a_reachable_store_reports_ready():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["checks"]["store"] == "ok"


def test_an_unreachable_store_fails_the_probe(monkeypatch):
    """The failure this exists for: uvicorn is up, the store is not, and a health-gated deploy
    would otherwise promote it into production."""
    def boom():
        raise RuntimeError("postgres://user:hunter2@db/jidoka is unreachable")

    monkeypatch.setattr(state.STORE, "list", boom)
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"


def test_the_probe_never_quotes_the_failure_message(monkeypatch):
    """A DSN in an exception string is a leaked credential, and /health is unauthenticated."""
    def boom():
        raise RuntimeError("postgres://user:hunter2@db/jidoka is unreachable")

    monkeypatch.setattr(state.STORE, "list", boom)
    said = client.get("/health").text
    assert "hunter2" not in said and "jidoka.db" not in said
    assert "RuntimeError" in said
