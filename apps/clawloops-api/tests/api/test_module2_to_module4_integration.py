from fastapi import status

from app.core.dependencies import (
    get_sqlalchemy_user_repository,
)
from app.repositories.model_repository import reset_inmemory_model_repositories
from app.domain.users import User, UserRole, UserStatus
from app.repositories.user_repository import InMemoryUserRepository


def _auth_headers(subject: str) -> dict[str, str]:
    return {"X-Authentik-Subject": subject}


def test_module2_to_module4_integration(client):
    """
    集成测试：模块 2 提供用户与 runtime 资源基础，模块 4 提供用户只读模型与用量视图。
    """
    repo = InMemoryUserRepository()
    reset_inmemory_model_repositories()
    client.app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: repo
    try:
        resp_sync = client.post(
            "/internal/users/sync",
            json={"subjectId": "authentik:integration-user"},
        )
        assert resp_sync.status_code == status.HTTP_200_OK
        user_id = resp_sync.json()["userId"]

        resp_binding = client.post(f"/internal/users/{user_id}/runtime-binding/ensure")
        assert resp_binding.status_code == status.HTTP_200_OK
        binding = resp_binding.json()
        assert binding["runtimeId"]
        assert binding["volumeId"]
        assert binding["imageRef"]
        assert binding["retentionPolicy"] == "preserve_workspace"

        headers = _auth_headers("authentik:integration-user")

        resp_models = client.get("/api/v1/models", headers=headers)
        assert resp_models.status_code == status.HTTP_200_OK
        models = resp_models.json()["models"]
        assert models
        assert all("modelId" in model for model in models)

        resp_usage = client.get("/api/v1/usage/summary", headers=headers)
        assert resp_usage.status_code == status.HTTP_200_OK
        usage = resp_usage.json()
        assert usage["userId"] == user_id
    finally:
        client.app.dependency_overrides.pop(get_sqlalchemy_user_repository, None)
