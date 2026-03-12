from dataclasses import dataclass
from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


@dataclass
class User:
    """
    平台内部用户对象。
    """

    user_id: str
    subject_id: str
    tenant_id: str
    role: UserRole
    status: UserStatus = UserStatus.ACTIVE

    def is_disabled(self) -> bool:
        return self.status == UserStatus.DISABLED


@dataclass
class Tenant:
    """
    简化版租户对象，MVP 默认仅使用 t_default。
    """

    tenant_id: str
    name: str


@dataclass
class Quota:
    """
    用户配额信息。

    TODO:
    - 后续可扩展为更细粒度配额（按模型、按周期等）。
    """

    user_id: str
    total_tokens: int
    used_tokens: int


class DesiredState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    DELETED = "deleted"


class ObservedState(str, Enum):
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    DELETED = "deleted"


class RetentionPolicy(str, Enum):
    PRESERVE_WORKSPACE = "preserve_workspace"
    WIPE_WORKSPACE = "wipe_workspace"


@dataclass
class UserRuntimeBinding:
    """
    与文档冻结结构对齐的 UserRuntimeBinding。

    同步要求：如结构有调整，需同步更新文档与 API 层 schema。
    """

    user_id: str
    runtime_id: str
    volume_id: str
    image_ref: str
    desired_state: DesiredState
    observed_state: ObservedState
    retention_policy: RetentionPolicy
    browser_url: str | None = None
    internal_endpoint: str | None = None
    last_error: str | None = None

