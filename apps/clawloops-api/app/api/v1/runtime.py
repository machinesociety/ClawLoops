from fastapi import APIRouter, Depends

from app.core.dependencies import get_runtime_service, require_active_user
from app.core.auth import AuthContext
from app.domain.runtime import RuntimeAction
from app.schemas.runtime import (
    DeleteRuntimeRequest,
    RuntimeActionAcceptedResponse,
    RuntimeTaskResponse,
    TaskAction,
    TaskStatus,
)
from app.services.runtime_service import RuntimeService


router = APIRouter(tags=["runtime"])


def _to_task_response(task) -> RuntimeTaskResponse:
    return RuntimeTaskResponse(
        taskId=task.task_id,
        userId=task.user_id,
        runtimeId=task.runtime_id,
        action=TaskAction(task.action.value),
        status=TaskStatus(task.status.value),
        message=task.message,
    )


@router.post("/users/me/runtime/start", response_model=RuntimeActionAcceptedResponse, status_code=202)
async def start_runtime(
    ctx: AuthContext = Depends(require_active_user),
    svc: RuntimeService = Depends(get_runtime_service),
) -> RuntimeActionAcceptedResponse:
    """
    启动或创建 runtime。
    """
    task = svc.ensure_running(ctx.userId)
    return RuntimeActionAcceptedResponse(
        taskId=task.task_id,
        action=TaskAction.ensure_running,
        status="accepted",
    )


@router.post("/users/me/runtime/stop", response_model=RuntimeActionAcceptedResponse, status_code=202)
async def stop_runtime(
    ctx: AuthContext = Depends(require_active_user),
    svc: RuntimeService = Depends(get_runtime_service),
) -> RuntimeActionAcceptedResponse:
    """
    停止 runtime。
    """
    task = svc.stop_runtime(ctx.userId)
    return RuntimeActionAcceptedResponse(
        taskId=task.task_id,
        action=TaskAction.stop,
        status="accepted",
    )


@router.post("/users/me/runtime/delete", response_model=RuntimeActionAcceptedResponse, status_code=202)
async def delete_runtime(
    body: DeleteRuntimeRequest | None = None,
    ctx: AuthContext = Depends(require_active_user),
    svc: RuntimeService = Depends(get_runtime_service),
) -> RuntimeActionAcceptedResponse:
    """
    删除 runtime。
    """
    retention_policy = body.retentionPolicy.value if body and body.retentionPolicy else None
    task = svc.delete_runtime(ctx.userId, retention_policy=retention_policy)
    return RuntimeActionAcceptedResponse(
        taskId=task.task_id,
        action=TaskAction.delete,
        status="accepted",
    )


@router.get("/runtime/tasks/{task_id}", response_model=RuntimeTaskResponse)
async def get_runtime_task(
    task_id: str,
    ctx: AuthContext = Depends(require_active_user),
    svc: RuntimeService = Depends(get_runtime_service),
) -> RuntimeTaskResponse:
    """
    查询 runtime 任务状态。
    """
    task = svc.get_task(task_id)
    if task is None or task.user_id != ctx.userId:
        # 为简化起见，返回一个 failed 任务视图；后续可改为 404。
        return RuntimeTaskResponse(
            taskId=task_id,
            userId=ctx.userId,
            runtimeId="",
            action=TaskAction.ensure_running,
            status=TaskStatus.failed,
            message="TASK_NOT_FOUND",
        )
    return _to_task_response(task)

