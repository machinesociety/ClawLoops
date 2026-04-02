from fastapi import status

from app.core.dependencies import (
    get_runtime_service,
    get_sqlalchemy_user_repository,
    get_runtime_binding_repository,
    get_user_service,
)
from app.domain.models import UsageSummary
from app.domain.users import (
    DesiredState,
    ObservedState,
    RetentionPolicy,
    User,
    UserRole,
    UserRuntimeBinding,
    UserStatus,
)
from app.repositories.model_repository import (
    get_inmemory_model_repository,
    get_inmemory_provider_credential_repository,
    get_inmemory_usage_repository,
    reset_inmemory_model_repositories,
)
from app.repositories.user_repository import InMemoryUserRepository
from app.services.user_service import UserService


class _InMemoryBindingRepo:
    def __init__(self) -> None:
        self._bindings: dict[str, UserRuntimeBinding] = {}

    def get_by_user_id(self, user_id: str):
        return self._bindings.get(user_id)

    def save(self, binding):
        self._bindings[binding.user_id] = binding


def _setup_admin_user_repo():
    repo = InMemoryUserRepository()
    repo.save(
        User(
            user_id="u_admin",
            subject_id="authentik:admin",
            tenant_id="t_default",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
    )
    repo.save(
        User(
            user_id="u_user",
            subject_id="authentik:user",
            tenant_id="t_default",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
    )
    return repo


def _setup_admin_services():
    repo = _setup_admin_user_repo()
    binding_repo = _InMemoryBindingRepo()
    binding_repo.save(
        UserRuntimeBinding(
            user_id="u_user",
            runtime_id="rt_u_user",
            volume_id="vol_u_user",
            image_ref="clawloops-runtime-wrapper:openclaw-1.0.0",
            desired_state=DesiredState.RUNNING,
            observed_state=ObservedState.RUNNING,
            retention_policy=RetentionPolicy.PRESERVE_WORKSPACE,
            browser_url="https://u-user.clawloops.example.com",
            internal_endpoint="http://clawloops-u-user:3000",
            last_error=None,
        )
    )
    service = UserService(
        user_repo=repo,
        binding_repo=binding_repo,
        default_image_ref="clawloops-runtime-wrapper:openclaw-1.0.0",
        default_retention_policy="preserve_workspace",
    )
    return repo, binding_repo, service


def test_admin_permission_required_for_admin_routes(client, issue_session_cookie):
    repo = _setup_admin_user_repo()
    client.app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: repo

    try:
        issue_session_cookie(client, user_id="u_user")
        resp = client.get("/api/v1/admin/users")
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        data = resp.json()
        assert data["code"] == "ACCESS_DENIED"
    finally:
        client.app.dependency_overrides.pop(get_sqlalchemy_user_repository, None)


def test_admin_can_list_and_get_user_detail(client, issue_session_cookie):
    repo, binding_repo, service = _setup_admin_services()
    client.app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: repo
    client.app.dependency_overrides[get_runtime_binding_repository] = lambda: binding_repo
    client.app.dependency_overrides[get_user_service] = lambda: service

    try:
        issue_session_cookie(client, user_id="u_admin")
        resp = client.get("/api/v1/admin/users")
        assert resp.status_code == status.HTTP_200_OK
        users = resp.json()["users"]
        assert any(u["userId"] == "u_user" for u in users)
        assert any(u["runtimeObservedState"] == "running" for u in users if u["userId"] == "u_user")

        detail = client.get("/api/v1/admin/users/u_user")
        assert detail.status_code == status.HTTP_200_OK
        data = detail.json()
        assert data["userId"] == "u_user"
        assert data["status"] == "active"

        runtime_resp = client.get("/api/v1/admin/users/u_user/runtime")
        assert runtime_resp.status_code == status.HTTP_200_OK
        runtime = runtime_resp.json()
        assert runtime["runtimeId"] == "rt_u_user"
        assert runtime["volumeId"] == "vol_u_user"
        assert runtime["imageRef"]
        assert runtime["internalEndpoint"] == "http://clawloops-u-user:3000"
        assert runtime["retentionPolicy"] == "preserve_workspace"
    finally:
        client.app.dependency_overrides.clear()


def test_admin_update_user_status_and_disabled_affects_frontend(client, issue_session_cookie):
    repo = InMemoryUserRepository()
    repo.save(
        User(
            user_id="u_admin",
            subject_id="authentik:admin",
            tenant_id="t_default",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
    )
    repo.save(
        User(
            user_id="u_target",
            subject_id="authentik:target",
            tenant_id="t_default",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
    )

    binding_repo = _InMemoryBindingRepo()
    service = UserService(
        user_repo=repo,
        binding_repo=binding_repo,
        default_image_ref="clawloops-runtime-wrapper:openclaw-1.0.0",
        default_retention_policy="preserve_workspace",
    )

    class _DummyRuntimeService:
        def stop_runtime(self, user_id: str):
            # 在本测试中不关心 runtime 收敛细节，仅验证用户禁用后前台 403
            _ = user_id
            return None

    client.app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: repo
    client.app.dependency_overrides[get_runtime_binding_repository] = lambda: binding_repo
    client.app.dependency_overrides[get_user_service] = lambda: service
    client.app.dependency_overrides[get_runtime_service] = lambda: _DummyRuntimeService()

    try:
        issue_session_cookie(client, user_id="u_admin")
        resp = client.patch(
            "/api/v1/admin/users/u_target/status",
            json={"status": "disabled"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] == "disabled"

        issue_session_cookie(client, user_id="u_target")
        quota_resp = client.get("/api/v1/users/me/quota")
        assert quota_resp.status_code == status.HTTP_403_FORBIDDEN
        qdata = quota_resp.json()
        assert qdata["code"] == "USER_DISABLED"
    finally:
        client.app.dependency_overrides.clear()


def test_admin_can_manage_models_provider_credentials_and_usage(client, issue_session_cookie):
    reset_inmemory_model_repositories()
    repo, binding_repo, service = _setup_admin_services()
    usage_repo = get_inmemory_usage_repository()
    usage_repo.set_user_usage(UsageSummary(user_id="u_user", total_tokens=123, used_tokens=120))

    client.app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: repo
    client.app.dependency_overrides[get_runtime_binding_repository] = lambda: binding_repo
    client.app.dependency_overrides[get_user_service] = lambda: service

    try:
        issue_session_cookie(client, user_id="u_admin")
        models_resp = client.get("/api/v1/admin/models")
        assert models_resp.status_code == status.HTTP_200_OK
        models = models_resp.json()["models"]
        assert any(model["modelId"] == "gpt-4-mini" for model in models)

        update_resp = client.put(
            "/api/v1/admin/models/gpt-4-mini",
            json={
                "enabled": True,
                "userVisible": False,
                "defaultRoute": "openai/gpt-4-mini-alt",
                "defaultProviderCredentialId": "pc_manual",
            },
        )
        assert update_resp.status_code == status.HTTP_200_OK
        updated = update_resp.json()
        assert updated["userVisible"] is False
        assert updated["defaultRoute"] == "openai/gpt-4-mini-alt"

        create_cred_resp = client.post(
            "/api/v1/admin/provider-credentials",
            json={"provider": "openai", "name": "prod-openai", "secret": "sk-admin"},
        )
        assert create_cred_resp.status_code == status.HTTP_201_CREATED
        credential = create_cred_resp.json()
        assert credential["credentialId"]
        assert credential["provider"] == "openai"
        assert "secret" not in credential

        list_cred_resp = client.get("/api/v1/admin/provider-credentials")
        assert list_cred_resp.status_code == status.HTTP_200_OK
        credentials = list_cred_resp.json()["credentials"]
        assert any(item["credentialId"] == credential["credentialId"] for item in credentials)

        verify_resp = client.post(
            f"/api/v1/admin/provider-credentials/{credential['credentialId']}/verify",
        )
        assert verify_resp.status_code == status.HTTP_200_OK
        verify = verify_resp.json()
        assert verify["verified"] is True
        assert verify["status"] == "active"

        usage_resp = client.get("/api/v1/admin/usage/summary")
        assert usage_resp.status_code == status.HTTP_200_OK
        usage = usage_resp.json()
        assert usage["totalTokens"] == 123
        assert usage["usedTokens"] == 120

        delete_resp = client.delete(
            f"/api/v1/admin/provider-credentials/{credential['credentialId']}",
        )
        assert delete_resp.status_code == status.HTTP_204_NO_CONTENT
    finally:
        client.app.dependency_overrides.clear()

