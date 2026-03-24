from fastapi import status

from app.core.dependencies import (
    get_runtime_binding_repository,
    get_runtime_service,
    get_sqlalchemy_user_repository,
    get_user_service,
)
from app.domain.users import (
    DesiredState,
    ObservedState,
    RetentionPolicy,
    User,
    UserRole,
    UserRuntimeBinding,
    UserStatus,
)
from app.repositories.user_repository import InMemoryUserRepository, UserRuntimeBindingRepository
from app.services.runtime_service import RuntimeService
from app.services.user_service import UserService


class _InMemoryBindingRepo(UserRuntimeBindingRepository):
    def __init__(self) -> None:
        self._bindings: dict[str, UserRuntimeBinding] = {}

    def get_by_user_id(self, user_id: str) -> UserRuntimeBinding | None:
        return self._bindings.get(user_id)

    def save(self, binding: UserRuntimeBinding) -> None:
        self._bindings[binding.user_id] = binding


class _DummyRuntimeManager:
    """
    简化版 runtime manager，用于观察 stop 是否被调用。
    """

    def __init__(self) -> None:
        self.stopped = set()

    def ensure_running(self, payload: dict) -> dict:
        return {
            "runtimeId": payload["runtimeId"],
            "observedState": ObservedState.CREATING.value,
            "internalEndpoint": "http://dummy",
            "message": "creating",
        }

    def stop(self, user_id: str, runtime_id: str) -> dict:
        _ = user_id
        self.stopped.add(runtime_id)
        return {"runtimeId": runtime_id, "message": "stopped"}

    def delete(self, user_id: str, runtime_id: str, retention_policy: str) -> dict:
        _ = user_id
        _ = runtime_id
        _ = retention_policy
        return {"runtimeId": runtime_id, "message": "deleted"}


def test_governance_smoke_admin_disable_user_stops_runtime_and_frontend_403(client):
    """
    治理 smoke test：
    admin 禁用用户 -> runtime 收敛停止 -> 用户业务接口返回 403 USER_DISABLED。
    """

    user_repo = InMemoryUserRepository()
    binding_repo = _InMemoryBindingRepo()

    # 管理员
    user_repo.save(
        User(
            user_id="u_admin",
            subject_id="authentik:admin",
            tenant_id="t_default",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
    )
    # 业务用户，已有 running runtime
    user_repo.save(
        User(
            user_id="u_biz",
            subject_id="authentik:biz",
            tenant_id="t_default",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
    )
    binding_repo.save(
        UserRuntimeBinding(
            user_id="u_biz",
            runtime_id="rt_u_biz",
            volume_id="vol_u_biz",
            image_ref="clawloops-runtime-wrapper:openclaw-1.0.0",
            desired_state=DesiredState.RUNNING,
            observed_state=ObservedState.RUNNING,
            retention_policy=RetentionPolicy.PRESERVE_WORKSPACE,
            browser_url="https://u-biz.clawloops.example.com",
            internal_endpoint="http://clawloops-u-biz:3000",
            last_error=None,
        )
    )

    user_service = UserService(
        user_repo=user_repo,
        binding_repo=binding_repo,
        default_image_ref="clawloops-runtime-wrapper:openclaw-1.0.0",
        default_retention_policy="preserve_workspace",
    )

    dummy_runtime_manager = _DummyRuntimeManager()

    # 构造 RuntimeService（使用真实配置渲染逻辑，但替换 runtime manager）
    from app.services.runtime_config_renderer import RuntimeConfigRenderer
    from app.services.runtime_service import (
        InMemoryRuntimeTaskRepository,
        ModelConfigServiceAdapter,
        RuntimeManagerPortAdapter,
        UserRuntimeBindingServiceAdapter,
    )
    from app.schemas.runtime import RuntimeBindingSnapshot as BindingSchema
    from app.schemas.internal import ModelConfigResponse
    from app.api.v1.internal import get_user_model_config as internal_get_model_config

    def ensure_binding_schema(user_id: str) -> BindingSchema:
        b = user_service.ensure_runtime_binding(user_id)
        return BindingSchema(
            runtimeId=b.runtime_id,
            volumeId=b.volume_id,
            imageRef=b.image_ref,
            desiredState=b.desired_state.value,
            observedState=b.observed_state.value,
            browserUrl=b.browser_url,
            internalEndpoint=b.internal_endpoint,
            retentionPolicy=b.retention_policy.value,
            lastError=b.last_error,
        )

    def patch_binding_state_schema(
        user_id: str,
        desired_state: str,
        observed_state: str,
        browser_url: str | None,
        internal_endpoint: str | None,
        last_error: str | None,
    ) -> BindingSchema | None:
        updated = user_service.update_runtime_binding_state(
            user_id=user_id,
            desired_state=DesiredState(desired_state),
            observed_state=ObservedState(observed_state),
            browser_url=browser_url,
            internal_endpoint=internal_endpoint,
            last_error=last_error,
        )
        if updated is None:
            return None
        return BindingSchema(
            runtimeId=updated.runtime_id,
            volumeId=updated.volume_id,
            imageRef=updated.image_ref,
            desiredState=updated.desired_state.value,
            observedState=updated.observed_state.value,
            browserUrl=updated.browser_url,
            internalEndpoint=updated.internal_endpoint,
            retentionPolicy=updated.retention_policy.value,
            lastError=updated.last_error,
        )

    def get_model_config(user_id: str) -> ModelConfigResponse:
        return internal_get_model_config(user_id)  # type: ignore[return-value]

    binding_port = UserRuntimeBindingServiceAdapter(
        ensure_binding_fn=ensure_binding_schema,
        patch_state_fn=patch_binding_state_schema,
    )
    model_config_port = ModelConfigServiceAdapter(get_model_config_fn=get_model_config)
    runtime_manager_port = RuntimeManagerPortAdapter(dummy_runtime_manager)

    runtime_service = RuntimeService(
        binding_service=binding_port,
        model_config_service=model_config_port,
        runtime_manager=runtime_manager_port,
        task_repo=InMemoryRuntimeTaskRepository(),
        config_renderer=RuntimeConfigRenderer(),
    )

    # 覆盖依赖
    client.app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: user_repo
    client.app.dependency_overrides[get_runtime_binding_repository] = lambda: binding_repo
    client.app.dependency_overrides[get_user_service] = lambda: user_service
    client.app.dependency_overrides[get_runtime_service] = lambda: runtime_service

    try:
        admin_headers = {"X-Authentik-Subject": "authentik:admin"}
        biz_headers = {"X-Authentik-Subject": "authentik:biz"}

        # 1) admin 禁用用户
        resp = client.patch(
            "/api/v1/admin/users/u_biz/status",
            headers=admin_headers,
            json={"status": "disabled"},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["status"] == "disabled"

        # runtime binding 应收敛到 stopped
        binding = binding_repo.get_by_user_id("u_biz")
        assert binding is not None
        assert binding.desired_state == DesiredState.STOPPED

        # runtime manager stop 被调用
        assert "rt_u_biz" in dummy_runtime_manager.stopped

        # 2) 前台业务接口返回 403 USER_DISABLED
        quota_resp = client.get("/api/v1/users/me/quota", headers=biz_headers)
        assert quota_resp.status_code == status.HTTP_403_FORBIDDEN
        assert quota_resp.json()["code"] == "USER_DISABLED"
    finally:
        client.app.dependency_overrides.clear()


