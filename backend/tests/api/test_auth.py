from fastapi import status

from app.core import dependencies
from app.domain.users import User, UserRole, UserStatus
from app.repositories.user_repository import InMemoryUserRepository


def test_auth_me_unauthenticated(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    data = resp.json()
    assert data["code"] == "UNAUTHENTICATED"


def test_auth_me_ok_with_subject_header(client):
    # 使用干净的仓储，避免其他测试污染
    dependencies._user_repo_singleton = InMemoryUserRepository()
    headers = {"X-Authentik-Subject": "authentik:12345"}
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["authenticated"] is True
    assert data["userId"]
    assert data["subjectId"] == "authentik:12345"
    assert data["tenantId"] == "t_default"


def test_auth_access_allowed_for_active_user(client):
    dependencies._user_repo_singleton = InMemoryUserRepository()
    headers = {"X-Authentik-Subject": "authentik:active"}
    resp = client.get("/api/v1/auth/access", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["allowed"] is True
    assert data["reason"] is None


def test_auth_access_disabled_user_blocked(client, monkeypatch):
    # 通过覆盖仓储，让该 subject 对应用户为 disabled。
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

    headers = {"X-Authentik-Subject": "authentik:disabled"}
    resp = client.get("/api/v1/auth/access", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["allowed"] is False
    assert data["reason"] == "USER_DISABLED"

