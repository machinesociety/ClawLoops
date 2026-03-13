from fastapi import status

from app.core.dependencies import (
    get_runtime_service,
    get_sqlalchemy_user_repository,
    get_user_service,
)
from app.domain.users import User, UserRole, UserStatus
from app.repositories.user_repository import InMemoryUserRepository
from app.services.user_service import UserService


def _setup_admin_user_repo():
    repo = InMemoryUserRepository()
    # admin 用户
    repo.save(
        User(
            user_id="u_admin",
            subject_id="authentik:admin",
            tenant_id="t_default",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
    )
    # 普通用户
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


def test_admin_permission_required_for_admin_routes(client):
    """
    admin 权限判断：非 admin 访问 /admin 路由返回 403 ACCESS_DENIED。
    """

    repo = _setup_admin_user_repo()
    client.app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: repo
    # 使用普通用户 subject
    headers = {"X-Authentik-Subject": "authentik:user"}

    try:
        resp = client.get("/api/v1/admin/users", headers=headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        data = resp.json()
        assert data["code"] == "ACCESS_DENIED"
    finally:
        client.app.dependency_overrides.pop(get_sqlalchemy_user_repository, None)


def test_admin_can_list_and_get_user_detail(client):
    """
    管理员可以查看用户列表和详情。
    """

    repo = _setup_admin_user_repo()
    service = UserService(
        user_repo=repo,
        binding_repo=None,  # type: ignore[arg-type]
        default_image_ref="crewclaw-runtime-wrapper:openclaw-1.0.0",
        default_retention_policy="preserve_workspace",
    )
    client.app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: repo
    client.app.dependency_overrides[get_user_service] = lambda: service

    headers = {"X-Authentik-Subject": "authentik:admin"}
    try:
        # 列表
        resp = client.get("/api/v1/admin/users", headers=headers)
        assert resp.status_code == status.HTTP_200_OK
        users = resp.json()
        assert any(u["userId"] == "u_user" for u in users)

        # 详情
        detail = client.get("/api/v1/admin/users/u_user", headers=headers)
        assert detail.status_code == status.HTTP_200_OK
        data = detail.json()
        assert data["userId"] == "u_user"
        assert data["status"] == "active"
    finally:
        client.app.dependency_overrides.clear()


def test_admin_update_user_status_and_disabled_affects_frontend(client):
    """
    用户状态修改：admin 禁用用户后，前台业务接口返回 403 USER_DISABLED。
    """

    repo = InMemoryUserRepository()
    # 管理员
    repo.save(
        User(
            user_id="u_admin",
            subject_id="authentik:admin",
            tenant_id="t_default",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
    )
    # 目标用户
    repo.save(
        User(
            user_id="u_target",
            subject_id="authentik:target",
            tenant_id="t_default",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
    )

    service = UserService(
        user_repo=repo,
        binding_repo=None,  # type: ignore[arg-type]
        default_image_ref="crewclaw-runtime-wrapper:openclaw-1.0.0",
        default_retention_policy="preserve_workspace",
    )

    class _DummyRuntimeService:
        def stop_runtime(self, user_id: str):
            # 在本测试中不关心 runtime 收敛细节，仅验证用户禁用后前台 403
            _ = user_id
            return None

    client.app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: repo
    client.app.dependency_overrides[get_user_service] = lambda: service
    client.app.dependency_overrides[get_runtime_service] = lambda: _DummyRuntimeService()

    try:
        admin_headers = {"X-Authentik-Subject": "authentik:admin"}
        target_headers = {"X-Authentik-Subject": "authentik:target"}

        # admin 禁用用户
        resp = client.patch(
            "/api/v1/admin/users/u_target/status",
            headers=admin_headers,
            json={"status": "disabled"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] == "disabled"

        # 前台访问业务接口应返回 403 USER_DISABLED
        quota_resp = client.get("/api/v1/users/me/quota", headers=target_headers)
        assert quota_resp.status_code == status.HTTP_403_FORBIDDEN
        qdata = quota_resp.json()
        assert qdata["code"] == "USER_DISABLED"
    finally:
        client.app.dependency_overrides.clear()


