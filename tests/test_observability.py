"""Test real metric increments, fixed incidents and bounded label cardinality."""

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.main import app

client = TestClient(app)


def count(route, status):
    return REGISTRY.get_sample_value(
        "obs_http_requests_total", {"route": route, "status": status}
    ) or 0


def test_metrics_and_unknown_paths():
    before = count("/api/status", "2xx")
    assert client.get("/api/status?private=not-a-label").status_code == 200
    assert count("/api/status", "2xx") == before + 1
    assert client.get("/user-supplied-not-a-label").status_code == 404
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "obs_http_request_duration_seconds_bucket" in response.text
    assert "not-a-label" not in response.text
    assert count("/api/status", "2xx") == before + 1


def test_incidents_require_explicit_lab_flag(monkeypatch):
    monkeypatch.delenv("LAB_INCIDENTS", raising=False)
    assert client.get("/lab/fail").status_code == 404
    assert client.get("/lab/slow").status_code == 404
    assert "/lab/fail" not in client.get("/openapi.json").json()["paths"]
    monkeypatch.setenv("LAB_INCIDENTS", "1")
    before = count("/lab/fail", "5xx")
    assert client.get("/lab/fail").status_code == 503
    assert count("/lab/fail", "5xx") == before + 1
    assert client.get("/lab/slow").status_code == 200
    assert client.get("/health").status_code == 200
