from fastapi.testclient import TestClient

from app.main import app


def test_healthz():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_status_for_missing_runtime_returns_deleted():
    client = TestClient(app)
    response = client.get("/internal/runtime-manager/containers/rt_missing")
    assert response.status_code == 200
    body = response.json()
    assert body["observedState"] == "deleted"
    assert body["internalEndpoint"] is None
