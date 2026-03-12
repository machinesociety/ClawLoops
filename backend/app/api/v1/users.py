from fastapi import APIRouter, Depends

from app.core.dependencies import require_active_user
from app.schemas.runtime import RuntimeStatusResponse, UserQuotaResponse, UserRuntimeBindingResponse


router = APIRouter(tags=["users"])


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
        user_id="u_001",
        total_tokens=1_000_000,
        used_tokens=12_345,
    )


@router.get("/users/me/runtime", response_model=UserRuntimeBindingResponse | None)
async def get_my_runtime_binding(
    _ = Depends(require_active_user),
) -> UserRuntimeBindingResponse | None:
    """
    获取当前用户 runtime binding。

    TODO:
    - 从 UserRuntimeBinding 仓储中读取实际数据。
    """
    return None


@router.get("/users/me/runtime/status", response_model=RuntimeStatusResponse)
async def get_my_runtime_status(
    _ = Depends(require_active_user),
) -> RuntimeStatusResponse:
    """
    查询当前用户 runtime 状态。

    TODO:
    - 从 RuntimeTask 和 UserRuntimeBinding 综合得出状态。
    """
    return RuntimeStatusResponse(
        runtimeId=None,
        desiredState=None,
        observedState=None,
        ready=False,
        browserUrl=None,
        reason=None,
        lastError=None,
    )

