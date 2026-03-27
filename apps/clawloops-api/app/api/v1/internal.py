from fastapi import APIRouter, Depends, Request, Response

from app.core.auth import AuthContext
from app.core.dependencies import get_app_settings, get_auth_context, get_user_service
from app.core.errors import PasswordChangeRequiredError, UserDisabledError
from app.core.settings import AppSettings
from app.domain.users import DesiredState, ObservedState, RetentionPolicy
from app.schemas.internal import (
    ContainerStateResponse,
    DeleteContainerRequest,
    EnsureContainerRequest,
    ModelConfigResponse,
    RuntimeBindingStateUpdateRequest,
    RuntimeBindingUpsertRequest,
    StopContainerRequest,
    SyncUserRequest,
    UsageRecordItem,
)
from app.schemas.runtime import (
    DesiredState as SchemaDesiredState,
    ObservedState as SchemaObservedState,
    RetentionPolicy as SchemaRetentionPolicy,
    RuntimeBindingSnapshot,
)
from app.services.user_service import UserService


router = APIRouter(prefix="/internal", tags=["internal"])


def _to_binding_snapshot(binding) -> RuntimeBindingSnapshot:
    return RuntimeBindingSnapshot(
        runtimeId=binding.runtime_id,
        volumeId=binding.volume_id,
        imageRef=binding.image_ref,
        desiredState=SchemaDesiredState(binding.desired_state.value),
        observedState=SchemaObservedState(binding.observed_state.value),
        browserUrl=binding.browser_url,
        internalEndpoint=binding.internal_endpoint,
        retentionPolicy=SchemaRetentionPolicy(binding.retention_policy.value),
        lastError=binding.last_error,
    )


@router.post("/users/sync")
async def sync_user(
    body: SyncUserRequest,
    user_service: UserService = Depends(get_user_service),
) -> dict:
    """
    首次登录同步 / 创建用户。

    """
    user = user_service.get_or_create_user(body.subjectId)
    return {"userId": user.user_id, "subjectId": user.subject_id, "tenantId": user.tenant_id}


@router.get("/auth/workspace-access")
async def workspace_access_gate(
    request: Request,
    response: Response,
    ctx: AuthContext = Depends(get_auth_context),
) -> dict:
    """
    workspace 子域统一网关鉴权入口（ForwardAuth 等价）。

    约束：
    - 依赖浏览器携带平台 session cookie
    - 按 v0.12 语义：disabled / mustChangePassword 必须拒绝
    """

    if ctx.isDisabled:
        raise UserDisabledError()
    if ctx.mustChangePassword:
        raise PasswordChangeRequiredError()

    host = request.headers.get("host") or ""
    response.headers["X-Clawloops-User-Id"] = ctx.userId
    response.headers["X-Clawloops-Subject-Id"] = ctx.subjectId
    response.headers["X-Clawloops-Workspace-Id"] = host
    return {"ok": True}


@router.post("/users/{user_id}/runtime-binding/ensure", response_model=RuntimeBindingSnapshot)
async def ensure_runtime_binding(
    user_id: str,
    user_service: UserService = Depends(get_user_service),
) -> RuntimeBindingSnapshot:
    """
    确保 runtime binding 存在；首次创建时由模块 2 分配 runtimeId / volumeId / 默认 imageRef / 默认 retentionPolicy。
    """

    return _to_binding_snapshot(user_service.ensure_runtime_binding(user_id))


@router.put("/users/{user_id}/runtime-binding", response_model=RuntimeBindingSnapshot)
async def upsert_runtime_binding(
    user_id: str,
    body: RuntimeBindingUpsertRequest,
    user_service: UserService = Depends(get_user_service),
) -> RuntimeBindingSnapshot:
    """
    创建或更新 runtime binding。
    """
    desired = DesiredState(body.desiredState)
    observed = ObservedState(body.observedState)
    retention = RetentionPolicy(body.retentionPolicy)
    binding = user_service.upsert_runtime_binding(
        user_id=user_id,
        runtime_id=body.runtimeId,
        volume_id=body.volumeId,
        image_ref=body.imageRef,
        desired_state=desired,
        observed_state=observed,
        retention_policy=retention,
        browser_url=body.browserUrl,
        internal_endpoint=body.internalEndpoint,
        last_error=body.lastError,
    )
    return _to_binding_snapshot(binding)


@router.patch("/users/{user_id}/runtime-binding/state", response_model=RuntimeBindingSnapshot)
async def update_runtime_binding_state(
    user_id: str,
    body: RuntimeBindingStateUpdateRequest,
    user_service: UserService = Depends(get_user_service),
) -> RuntimeBindingSnapshot:
    """
    更新 runtime binding 状态。
    """
    binding = user_service.update_runtime_binding_state(
        user_id=user_id,
        desired_state=DesiredState(body.desiredState),
        observed_state=ObservedState(body.observedState),
        browser_url=body.browserUrl,
        internal_endpoint=body.internalEndpoint,
        last_error=body.lastError,
    )
    if binding is None:
        from app.core.errors import RuntimeNotFoundError

        raise RuntimeNotFoundError()
    return _to_binding_snapshot(binding)


@router.get("/model-config/users/{user_id}", response_model=ModelConfigResponse)
async def get_user_model_config(
    user_id: str,
    settings: AppSettings = Depends(get_app_settings),
) -> ModelConfigResponse:
    """
    获取运行时模型配置。
    """
    _ = user_id
    model_base_url = settings.model_gateway_base_url or "http://litellm:4000"
    model_ids = settings.get_model_gateway_default_models()
    return ModelConfigResponse(
        baseUrl=model_base_url,
        models=model_ids,
        gatewayAccessTokenRef="token_ref_001",
        configRenderVersion="v1",
    )


@router.post("/usage/records")
async def ingest_usage_records(records: list[UsageRecordItem]) -> dict:
    """
    接收 OpenClaw usage 上报。
    """
    _ = records
    return {"status": "accepted"}


@router.post("/runtime-manager/containers/ensure-running")
async def ensure_container_running(body: EnsureContainerRequest) -> ContainerStateResponse:
    """
    确保容器运行。

    TODO:
    - 调用 runtime-manager 客户端执行真实操作。
    """
    _ = body
    return ContainerStateResponse(
        runtimeId="rt_001",
        observedState="creating",
        internalEndpoint="http://clawloops-u001:3000",
        message="creating",
    )


@router.post("/runtime-manager/containers/stop")
async def stop_container(body: StopContainerRequest) -> dict:
    """
    停止容器占位。
    """
    return {"runtimeId": body.runtimeId, "observedState": "stopped", "message": "stopped"}


@router.post("/runtime-manager/containers/delete")
async def delete_container(body: DeleteContainerRequest) -> dict:
    """
    删除容器占位。
    """
    _ = body.retentionPolicy
    return {"runtimeId": body.runtimeId, "observedState": "deleted", "message": "deleted"}


@router.get("/runtime-manager/containers/{runtime_id}", response_model=ContainerStateResponse)
async def get_container_state(runtime_id: str) -> ContainerStateResponse:
    """
    查询容器状态。
    """
    _ = runtime_id
    return ContainerStateResponse(
        runtimeId=runtime_id,
        observedState="running",
        internalEndpoint="http://clawloops-u001:3000",
        message="running",
    )

