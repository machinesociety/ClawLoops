from fastapi import APIRouter, Depends

from app.core.dependencies import get_user_service
from app.domain.users import DesiredState, ObservedState, RetentionPolicy
from app.schemas.internal import (
    ContainerStateResponse,
    EnsureContainerRequest,
    ModelConfigResponse,
    RuntimeBindingStateUpdateRequest,
    RuntimeBindingUpsertRequest,
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
async def get_user_model_config(user_id: str) -> ModelConfigResponse:
    """
    获取运行时模型配置。
    """
    _ = user_id
    return ModelConfigResponse(
        baseUrl="http://litellm:4000",
        models=["gpt-4-mini"],
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
async def stop_container() -> dict:
    """
    停止容器占位。
    """
    return {"status": "accepted"}


@router.post("/runtime-manager/containers/delete")
async def delete_container() -> dict:
    """
    删除容器占位。
    """
    return {"status": "accepted"}


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

