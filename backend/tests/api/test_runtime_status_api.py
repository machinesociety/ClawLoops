from fastapi import status

from app.domain.users import DesiredState as DomainDesiredState, ObservedState as DomainObservedState


def _auth_headers(subject: str = "authentik:status-user") -> dict[str, str]:
    return {"X-Authentik-Subject": subject}


def _sync_user(client, subject: str) -> str:
    resp = client.post("/internal/users/sync", json={"subject_id": subject})
    assert resp.status_code == status.HTTP_200_OK
    return resp.json()["userId"]


def test_runtime_status_without_binding(client_with_inmemory):
    client = client_with_inmemory
    subject = "authentik:no-binding"
    _ = _sync_user(client, subject)

    resp = client.get("/api/v1/users/me/runtime/status", headers=_auth_headers(subject))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["runtimeId"] is None
    assert data["desiredState"] is None
    assert data["observedState"] is None
    assert data["ready"] is False
    assert data["browserUrl"] is None
    assert data["reason"] == "runtime_not_found"
    assert data["lastError"] is None


def test_runtime_status_stopped_after_binding_ensure(client_with_inmemory):
    client = client_with_inmemory
    subject = "authentik:stopped"
    user_id = _sync_user(client, subject)

    resp_ensure = client.post(f"/internal/users/{user_id}/runtime-binding/ensure")
    assert resp_ensure.status_code == status.HTTP_200_OK

    resp = client.get("/api/v1/users/me/runtime/status", headers=_auth_headers(subject))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["runtimeId"] is not None
    assert data["desiredState"] == DomainDesiredState.STOPPED.value
    assert data["observedState"] == DomainObservedState.STOPPED.value
    assert data["ready"] is False
    # 初始 binding 应被视为 runtime_stopped
    assert data["reason"] == "runtime_stopped"
    assert data["browserUrl"] is None


def test_runtime_status_starting_and_error_reasons(client_with_inmemory):
    client = client_with_inmemory
    subject = "authentik:transitions"
    user_id = _sync_user(client, subject)

    resp_ensure = client.post(f"/internal/users/{user_id}/runtime-binding/ensure")
    assert resp_ensure.status_code == status.HTTP_200_OK
    runtime_id = resp_ensure.json()["runtimeId"]

    # 启动中：desired=running, observed=creating
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

    resp_status_creating = client.get(
        "/api/v1/users/me/runtime/status",
        headers=_auth_headers(subject),
    )
    assert resp_status_creating.status_code == status.HTTP_200_OK
    data_creating = resp_status_creating.json()
    assert data_creating["runtimeId"] == runtime_id
    assert data_creating["ready"] is False
    assert data_creating["reason"] == "runtime_starting"

    # error：observed=error，lastError 透传
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

    resp_status_error = client.get(
        "/api/v1/users/me/runtime/status",
        headers=_auth_headers(subject),
    )
    assert resp_status_error.status_code == status.HTTP_200_OK
    data_error = resp_status_error.json()
    assert data_error["runtimeId"] == runtime_id
    assert data_error["ready"] is False
    assert data_error["reason"] == "runtime_error"
    assert data_error["lastError"] == "boom"

