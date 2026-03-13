from fastapi import status

from app.domain.users import DesiredState as DomainDesiredState, ObservedState as DomainObservedState


def _auth_headers(subject: str = "authentik:workspace-user") -> dict[str, str]:
    return {"X-Authentik-Subject": subject}


def _sync_user(client, subject: str) -> str:
    resp = client.post("/internal/users/sync", json={"subject_id": subject})
    assert resp.status_code == status.HTTP_200_OK
    return resp.json()["userId"]


def test_workspace_entry_no_binding(client_with_inmemory):
    client = client_with_inmemory
    subject = "authentik:ws-none"
    _ = _sync_user(client, subject)

    resp = client.get("/api/v1/workspace-entry", headers=_auth_headers(subject))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["ready"] is False
    assert data["runtimeId"] is None
    assert data["browserUrl"] is None
    assert data["reason"] == "runtime_not_found"


def test_workspace_entry_not_running_and_ready(client_with_inmemory):
    client = client_with_inmemory
    subject = "authentik:ws-flow"
    user_id = _sync_user(client, subject)

    # 先确保 binding，默认 stopped
    resp_ensure = client.post(f"/internal/users/{user_id}/runtime-binding/ensure")
    assert resp_ensure.status_code == status.HTTP_200_OK
    runtime_id = resp_ensure.json()["runtimeId"]

    # stopped 场景：observed=stopped -> runtime_not_running
    resp_stopped = client.get("/api/v1/workspace-entry", headers=_auth_headers(subject))
    assert resp_stopped.status_code == status.HTTP_200_OK
    data_stopped = resp_stopped.json()
    assert data_stopped["ready"] is False
    assert data_stopped["runtimeId"] == runtime_id
    assert data_stopped["browserUrl"] is None
    assert data_stopped["reason"] == "runtime_not_running"

    # 启动中：desired=running, observed=creating -> runtime_starting
    resp_update_creating = client.patch(
        f"/internal/users/{user_id}/runtime-binding/state",
        json={
            "desired_state": DomainDesiredState.RUNNING.value,
            "observed_state": DomainObservedState.CREATING.value,
            "browser_url": None,
            "internal_endpoint": None,
            "last_error": None,
        },
    )
    assert resp_update_creating.status_code == status.HTTP_200_OK

    resp_starting = client.get("/api/v1/workspace-entry", headers=_auth_headers(subject))
    assert resp_starting.status_code == status.HTTP_200_OK
    data_starting = resp_starting.json()
    assert data_starting["ready"] is False
    assert data_starting["runtimeId"] == runtime_id
    assert data_starting["reason"] == "runtime_starting"

    # ready：observed=running 且 browser_url 非空
    resp_update_running = client.patch(
        f"/internal/users/{user_id}/runtime-binding/state",
        json={
            "desired_state": DomainDesiredState.RUNNING.value,
            "observed_state": DomainObservedState.RUNNING.value,
            "browser_url": "https://u-001.crewclaw.example.com",
            "internal_endpoint": "http://crewclaw-u001:3000",
            "last_error": None,
        },
    )
    assert resp_update_running.status_code == status.HTTP_200_OK

    resp_ready = client.get("/api/v1/workspace-entry", headers=_auth_headers(subject))
    assert resp_ready.status_code == status.HTTP_200_OK
    data_ready = resp_ready.json()
    assert data_ready["ready"] is True
    assert data_ready["runtimeId"] == runtime_id
    assert data_ready["browserUrl"] == "https://u-001.crewclaw.example.com"
    assert data_ready["reason"] is None


def test_workspace_entry_error_reason(client_with_inmemory):
    client = client_with_inmemory
    subject = "authentik:ws-error"
    user_id = _sync_user(client, subject)

    resp_ensure = client.post(f"/internal/users/{user_id}/runtime-binding/ensure")
    assert resp_ensure.status_code == status.HTTP_200_OK
    runtime_id = resp_ensure.json()["runtimeId"]

    resp_update_error = client.patch(
        f"/internal/users/{user_id}/runtime-binding/state",
        json={
            "desired_state": DomainDesiredState.RUNNING.value,
            "observed_state": DomainObservedState.ERROR.value,
            "browser_url": None,
            "internal_endpoint": None,
            "last_error": "boom",
        },
    )
    assert resp_update_error.status_code == status.HTTP_200_OK

    resp = client.get("/api/v1/workspace-entry", headers=_auth_headers(subject))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["ready"] is False
    assert data["runtimeId"] == runtime_id
    assert data["browserUrl"] is None
    assert data["reason"] == "runtime_error"

