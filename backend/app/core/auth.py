from fastapi import Request
from pydantic import BaseModel

from app.core.errors import UnauthenticatedError
from app.core.settings import AppSettings
from app.domain.users import User, UserRole, UserStatus
from app.repositories.user_repository import UserRepository


class AuthContext(BaseModel):
    """当前请求的认证上下文，与基线契约字段对齐。"""

    userId: str
    subjectId: str
    tenantId: str
    role: str
    isAdmin: bool = False
    isDisabled: bool = False


def build_auth_context_from_request(
    request: Request,
    settings: AppSettings,
    user_repo: UserRepository,
) -> AuthContext:
    """
    根据请求头与用户仓储构造 AuthContext。

    - 若缺少 subject 头部则视为未认证。
    - 若用户不存在，则以默认值创建（tenantId=t_default, role=user, status=active）。
    """

    subject_header = settings.auth_header_subject
    subject_id = request.headers.get(subject_header)
    if not subject_id:
        raise UnauthenticatedError()

    user = user_repo.get_by_subject_id(subject_id)
    if user is None:
        # 按 MVP 约定创建默认用户，后续可委托模块 2 的 /internal/users/sync。
        user = User(
            user_id=f"auto_{abs(hash(subject_id))}",
            subject_id=subject_id,
            tenant_id="t_default",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
        user_repo.save(user)

    return AuthContext(
        userId=user.user_id,
        subjectId=user.subject_id,
        tenantId=user.tenant_id,
        role=user.role.value,
        isAdmin=user.role == UserRole.ADMIN,
        isDisabled=user.is_disabled(),
    )

