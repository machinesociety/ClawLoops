from fastapi import APIRouter, Depends

from app.core.dependencies import get_app_settings, get_user_service, require_active_user
from app.domain.users import DesiredState as DomainDesiredState, ObservedState as DomainObservedState
from app.infra.runtime_manager_client import RuntimeManagerClient
from app.schemas.runtime import (
    DesiredState as SchemaDesiredState,
    ObservedState as SchemaObservedState,
    RetentionPolicy as SchemaRetentionPolicy,
    RuntimeStatusReason,
    RuntimeStatusResponse,
    UserQuotaResponse,
    UserRuntimeBinding,
    UserRuntimeBindingResponse,
)
from app.schemas.users import UserResponse
from app.services.openclaw_url import merge_with_existing_token
from app.services.user_service import UserService


router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserResponse)
async def get_current_user(
    ctx = Depends(require_active_user),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    """
    获取当前用户信息。
    """
    user = user_service.get_user_by_id(ctx.userId)
    if user is None:
        from app.core.errors import UserNotFoundError
        raise UserNotFoundError()
    return UserResponse(
        userId=user.user_id,
        subjectId=user.subject_id,
        username=user.username,
        tenantId=user.tenant_id,
        role=user.role.value,
        status=user.status.value,
    )


@router.get("/users/me/quota", response_model=UserQuotaResponse)
async def get_my_quota(
    _ = Depends(require_active_user),
) -> UserQuotaResponse:
    """
    获取当前用户 quota。

    TODO:
    - 从实际配额服务或配置中读取。
    """
    return UserQuotaResponse(
        userId="u_001",
        totalTokens=1_000_000,
        usedTokens=12_345,
    )


@router.get("/users/me/runtime", response_model=UserRuntimeBindingResponse | None)
async def get_my_runtime_binding(
    ctx=Depends(require_active_user),
    user_service: UserService = Depends(get_user_service),
) -> UserRuntimeBindingResponse | None:
    """
    获取当前用户 runtime binding。

    """
    binding = user_service.get_runtime_binding(ctx.userId)
    if binding is None:
        return None

    runtime = UserRuntimeBinding(
        runtimeId=binding.runtime_id,
        volumeId=binding.volume_id,
        imageRef=binding.image_ref,
        desiredState=SchemaDesiredState(binding.desired_state.value),
        observedState=SchemaObservedState(binding.observed_state.value),
        browserUrl=binding.browser_url,
        retentionPolicy=SchemaRetentionPolicy(binding.retention_policy.value),
        lastError=binding.last_error,
    )
    return UserRuntimeBindingResponse(userId=ctx.userId, runtime=runtime)


@router.get("/users/me/runtime/status", response_model=RuntimeStatusResponse)
async def get_my_runtime_status(
    ctx=Depends(require_active_user),
    user_service: UserService = Depends(get_user_service),
    settings=Depends(get_app_settings),
) -> RuntimeStatusResponse:
    """
    查询当前用户 runtime 状态。

    MVP 阶段直接基于 UserRuntimeBinding 进行投影。
    """
    binding = user_service.get_runtime_binding(ctx.userId)
    if binding is None:
        return RuntimeStatusResponse(
            runtimeId=None,
            desiredState=None,
            observedState=None,
            ready=False,
            browserUrl=None,
            reason=RuntimeStatusReason.runtime_not_found,
            lastError=None,
        )

    if binding is not None:
        try:
            rm_client = RuntimeManagerClient(settings.runtime_manager_base_url or "http://runtime-manager:18080")
            container_fact = rm_client.get_container(binding.runtime_id)
            fact_observed = container_fact.get("observedState")
            fact_browser_url = merge_with_existing_token(
                new_browser_url=container_fact.get("browserUrl"),
                existing_browser_url=binding.browser_url,
            )
            if fact_observed and (
                fact_observed != binding.observed_state.value.lower() or fact_browser_url != binding.browser_url
            ):
                mapped = {
                    "creating": DomainObservedState.CREATING,
                    "running": DomainObservedState.RUNNING,
                    "stopped": DomainObservedState.STOPPED,
                    "error": DomainObservedState.ERROR,
                    "deleted": DomainObservedState.DELETED,
                }
                user_service.update_runtime_binding_state(
                    user_id=ctx.userId,
                    desired_state=binding.desired_state,
                    observed_state=mapped.get(fact_observed, binding.observed_state),
                    browser_url=fact_browser_url,
                    internal_endpoint=binding.internal_endpoint,
                    last_error=binding.last_error,
                )
                binding = user_service.get_runtime_binding(ctx.userId) or binding
        except Exception:
            pass

    ready = binding.observed_state == DomainObservedState.RUNNING and bool(binding.browser_url)

    if binding.observed_state == DomainObservedState.ERROR:
        reason = RuntimeStatusReason.runtime_error
    elif binding.observed_state == DomainObservedState.CREATING:
        reason = RuntimeStatusReason.runtime_starting
    elif binding.desired_state == DomainDesiredState.STOPPED:
        reason = RuntimeStatusReason.runtime_stopped
    else:
        reason = None

    return RuntimeStatusResponse(
        runtimeId=binding.runtime_id,
        desiredState=SchemaDesiredState(binding.desired_state.value),
        observedState=SchemaObservedState(binding.observed_state.value),
        ready=ready,
        browserUrl=binding.browser_url,
        reason=reason,
        lastError=binding.last_error,
    )

