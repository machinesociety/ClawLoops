from fastapi import status

from app.core import dependencies
from app.domain.users import User, UserRole, UserStatus
from app.repositories.user_repository import InMemoryUserRepository


def _setup_disabled_user():
    repo = InMemoryUserRepository()
    user = User(
        user_id="u_disabled",
        subject_id="authentik:disabled",
        tenant_id="t_default",
        role=UserRole.USER,
        status=UserStatus.DISABLED,
    )
    repo.save(user)
    dependencies._user_repo_singleton = repo


def test_disabled_user_cannot_start_runtime(client, monkeypatch):
    _setup_disabled_user()

    headers = {"X-Authentik-Subject": "authentik:disabled"}
    resp = client.post("/api/v1/users/me/runtime/start", headers=headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    data = resp.json()
    assert data["code"] == "USER_DISABLED"


def test_disabled_user_cannot_access_quota(client, monkeypatch):
    _setup_disabled_user()

    headers = {"X-Authentik-Subject": "authentik:disabled"}
    resp = client.get("/api/v1/users/me/quota", headers=headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    data = resp.json()
    assert data["code"] == "USER_DISABLED"


def test_disabled_user_cannot_access_runtime_status(client, monkeypatch):
    _setup_disabled_user()

    headers = {"X-Authentik-Subject": "authentik:disabled"}
    resp = client.get("/api/v1/users/me/runtime/status", headers=headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    data = resp.json()
    assert data["code"] == "USER_DISABLED"

