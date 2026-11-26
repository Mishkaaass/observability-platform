"""Reference service contract; adapt these tests to the new project's behavior."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ready_version(monkeypatch):
    monkeypatch.setenv("APP_GIT_SHA", "example-sha")
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}
    assert client.get("/version").json() == {"git_sha": "example-sha"}


def test_stateless_api_contract():
    message = "<script>alert(1)</script>"
    assert client.get("/api/status").json() == {"status": "ok"}
    response = client.post("/api/validate", json={"message": message})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"accepted": True, "length": len(message)}
    assert client.post("/api/validate", json={"message": ""}).status_code == 422
    assert client.post("/api/validate", json={"message": "x" * 129}).status_code == 422


def test_http_security():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/", headers={"Host": "untrusted.invalid"}).status_code == 400
    for path in ("/.env", "/.git/config", "/docs", "/admin"):
        assert client.get(path).status_code == 404
    assert client.post("/health").status_code == 405
    cross_origin = client.get(
        "/api/status", headers={"Origin": "https://untrusted.invalid"}
    )
    assert "access-control-allow-origin" not in cross_origin.headers
