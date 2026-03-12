from fastapi import APIRouter, Depends

from app.core.dependencies import require_active_user
from app.schemas.runtime import RuntimeActionAcceptedResponse, RuntimeTaskResponse


router = APIRouter(tags=["runtime"])


@router.post("/users/me/runtime/start", response_model=RuntimeActionAcceptedResponse, status_code=202)
async def start_runtime(
    _ = Depends(require_active_user),
) -> RuntimeActionAcceptedResponse:
    """
    启动或创建 runtime。

    TODO:
    - 调用 RuntimeService.ensure_running 并返回真实 taskId。
    """
    return RuntimeActionAcceptedResponse(
        task_id="rtask_001",
        action="ensure_running",
        status="accepted",
    )


@router.post("/users/me/runtime/stop", response_model=RuntimeActionAcceptedResponse, status_code=202)
async def stop_runtime(
    _ = Depends(require_active_user),
) -> RuntimeActionAcceptedResponse:
    """
    停止 runtime。

    TODO:
    - 调用 RuntimeService.stop_runtime。
    """
    return RuntimeActionAcceptedResponse(
        task_id="rtask_002",
        action="stop",
        status="accepted",
    )


@router.delete("/users/me/runtime", response_model=RuntimeActionAcceptedResponse, status_code=202)
async def delete_runtime(
    _ = Depends(require_active_user),
) -> RuntimeActionAcceptedResponse:
    """
    删除 runtime。

    TODO:
    - 调用 RuntimeService.delete_runtime，并根据 retentionPolicy 处理 workspace。
    """
    return RuntimeActionAcceptedResponse(
        task_id="rtask_003",
        action="delete",
        status="accepted",
    )


@router.get("/runtime/tasks/{task_id}", response_model=RuntimeTaskResponse)
async def get_runtime_task(
    task_id: str,
    _ = Depends(require_active_user),
) -> RuntimeTaskResponse:
    """
    查询 runtime 任务状态。

    TODO:
    - 从任务仓储中查询任务状态。
    """
    return RuntimeTaskResponse(
        task_id=task_id,
        user_id="u_001",
        runtime_id="rt_001",
        action="ensure_running",
        status="running",
        message="creating",
    )

