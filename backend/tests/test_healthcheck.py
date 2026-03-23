from fastapi import status


def test_root_ok(client):
    resp = client.get("/")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["service"] == "clawloops-control-plane"


def test_healthz_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "healthy"

