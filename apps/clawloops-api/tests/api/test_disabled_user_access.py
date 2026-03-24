from fastapi import status

from app.core.dependencies import get_sqlalchemy_user_repository
from app.domain.users import User, UserRole, UserStatus
from app.repositories.user_repository import InMemoryUserRepository


def _repo_with_disabled_user():
    repo = InMemoryUserRepository()
    repo.save(
        User(
            user_id="u_disabled",
            subject_id="authentik:disabled",
            tenant_id="t_default",
            role=UserRole.USER,
            status=UserStatus.DISABLED,
        )
    )
    return repo


def test_disabled_user_cannot_start_runtime(client):
    repo = _repo_with_disabled_user()
    client.app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: repo
    try:
        headers = {"X-Authentik-Subject": "authentik:disabled"}
        resp = client.post("/api/v1/users/me/runtime/start", headers=headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        data = resp.json()
        assert data["code"] == "USER_DISABLED"
    finally:
        client.app.dependency_overrides.pop(get_sqlalchemy_user_repository, None)


def test_disabled_user_cannot_access_quota(client):
    repo = _repo_with_disabled_user()
    client.app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: repo
    try:
        headers = {"X-Authentik-Subject": "authentik:disabled"}
        resp = client.get("/api/v1/users/me/quota", headers=headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        data = resp.json()
        assert data["code"] == "USER_DISABLED"
    finally:
        client.app.dependency_overrides.pop(get_sqlalchemy_user_repository, None)


def test_disabled_user_cannot_access_runtime_status(client):
    repo = _repo_with_disabled_user()
    client.app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: repo
    try:
        headers = {"X-Authentik-Subject": "authentik:disabled"}
        resp = client.get("/api/v1/users/me/runtime/status", headers=headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        data = resp.json()
        assert data["code"] == "USER_DISABLED"
    finally:
        client.app.dependency_overrides.pop(get_sqlalchemy_user_repository, None)


def test_disabled_user_business_interfaces_all_return_user_disabled(client):
    repo = _repo_with_disabled_user()
    client.app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: repo
    headers = {"X-Authentik-Subject": "authentik:disabled"}
    endpoints = [
        ("get", "/api/v1/users/me/runtime", None),
        ("post", "/api/v1/users/me/runtime/stop", None),
        ("post", "/api/v1/users/me/runtime/delete", {"retentionPolicy": "preserve_workspace"}),
        ("get", "/api/v1/models", None),
        ("get", "/api/v1/usage/summary", None),
        ("get", "/api/v1/workspace-entry", None),
        ("get", "/api/v1/auth/access", None),
    ]

    try:
        for method, path, payload in endpoints:
            if method == "get":
                resp = client.get(path, headers=headers)
            elif method == "post":
                resp = client.post(path, headers=headers, json=payload)
            else:
                resp = client.request("DELETE", path, headers=headers, json=payload)

            assert resp.status_code == status.HTTP_403_FORBIDDEN
            assert resp.json()["code"] == "USER_DISABLED"
    finally:
        client.app.dependency_overrides.pop(get_sqlalchemy_user_repository, None)

