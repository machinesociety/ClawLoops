from enum import Enum

from pydantic import BaseModel


class DesiredState(str, Enum):
    running = "running"
    stopped = "stopped"
    deleted = "deleted"


class ObservedState(str, Enum):
    creating = "creating"
    running = "running"
    stopped = "stopped"
    error = "error"
    deleted = "deleted"


class RetentionPolicy(str, Enum):
    preserve_workspace = "preserve_workspace"
    wipe_workspace = "wipe_workspace"


class TaskAction(str, Enum):
    ensure_running = "ensure_running"
    stop = "stop"
    delete = "delete"


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"


class UserRuntimeBinding(BaseModel):
    """
    与 baseline-v0.2 UserRuntimeBinding JSON Schema 一致的内部模型。
    """

    runtimeId: str
    volumeId: str
    imageRef: str
    desiredState: DesiredState
    observedState: ObservedState
    browserUrl: str | None
    internalEndpoint: str | None
    retentionPolicy: RetentionPolicy
    lastError: str | None


class RuntimeStatusReason(str, Enum):
    runtime_not_found = "runtime_not_found"
    runtime_stopped = "runtime_stopped"
    runtime_starting = "runtime_starting"
    runtime_error = "runtime_error"


class WorkspaceEntryReason(str, Enum):
    runtime_not_found = "runtime_not_found"
    runtime_not_running = "runtime_not_running"
    runtime_starting = "runtime_starting"
    runtime_error = "runtime_error"


class UserRuntimeBindingResponse(BaseModel):
    """
    对应 GET /api/v1/users/me/runtime 的用户侧视图。
    """

    userId: str
    runtime: UserRuntimeBinding


class RuntimeStatusResponse(BaseModel):
    """
    对应 GET /api/v1/users/me/runtime/status 的轻量状态投影。
    """

    runtimeId: str | None
    desiredState: DesiredState | None
    observedState: ObservedState | None
    ready: bool
    browserUrl: str | None
    reason: RuntimeStatusReason | None = None
    lastError: str | None = None


class RuntimeTaskResponse(BaseModel):
    """
    对应 GET /api/v1/runtime/tasks/{taskId} 响应。
    """

    taskId: str
    userId: str
    runtimeId: str
    action: TaskAction
    status: TaskStatus
    message: str | None = None


class RuntimeActionAcceptedResponse(BaseModel):
    """
    启动/停止/删除 runtime 的异步任务受理响应。
    """

    taskId: str
    action: TaskAction
    status: str


class UserQuotaResponse(BaseModel):
    """
    当前用户 quota 响应，占位模型。
    """

    userId: str
    totalTokens: int
    usedTokens: int

