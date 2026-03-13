import pytest
from fastapi import status


def test_internal_users_sync_and_binding_ensure(client_with_inmemory):
    client = client_with_inmemory

    resp = client.post("/internal/users/sync", json={"subject_id": "authentik:sync-user"})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "userId" in data
    user_id = data["userId"]
    assert data["subjectId"] == "authentik:sync-user"

    resp2 = client.post(f"/internal/users/{user_id}/runtime-binding/ensure")
    assert resp2.status_code == status.HTTP_200_OK
    binding = resp2.json()
    assert binding["runtimeId"].startswith("rt_")
    assert binding["volumeId"].startswith("vol_")
    assert binding["desiredState"] == "stopped"
    assert binding["observedState"] == "stopped"

    resp3 = client.post(f"/internal/users/{user_id}/runtime-binding/ensure")
    assert resp3.status_code == status.HTTP_200_OK
    binding2 = resp3.json()
    assert binding2["runtimeId"] == binding["runtimeId"]
    assert binding2["volumeId"] == binding["volumeId"]


def test_user_runtime_and_status_and_workspace_entry(client_with_inmemory):
    client = client_with_inmemory

    resp_sync = client.post("/internal/users/sync", json={"subject_id": "authentik:user1"})
    assert resp_sync.status_code == status.HTTP_200_OK
    user_id = resp_sync.json()["userId"]

    client.post(f"/internal/users/{user_id}/runtime-binding/ensure")
    headers = {"X-Authentik-Subject": "authentik:user1"}

    resp_binding = client.get("/api/v1/users/me/runtime", headers=headers)
    assert resp_binding.status_code == status.HTTP_200_OK
    data_binding = resp_binding.json()
    assert data_binding["userId"] == user_id
    assert data_binding["runtime"]["runtimeId"].startswith("rt_")

    resp_status = client.get("/api/v1/users/me/runtime/status", headers=headers)
    assert resp_status.status_code == status.HTTP_200_OK
    data_status = resp_status.json()
    assert data_status["runtimeId"] is not None
    assert data_status["ready"] is False
    assert data_status.get("reason") in (None, "runtime_stopped", "runtime_not_found", "runtime_starting", "runtime_error")

    resp_workspace = client.get("/api/v1/workspace-entry", headers=headers)
    assert resp_workspace.status_code == status.HTTP_200_OK
    data_workspace = resp_workspace.json()
    assert data_workspace["runtimeId"] == data_status["runtimeId"]
    assert data_workspace["ready"] is False
