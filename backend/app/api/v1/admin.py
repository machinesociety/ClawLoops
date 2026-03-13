from fastapi import APIRouter, Depends

from app.core.auth import AuthContext
from app.core.dependencies import (
    get_auth_context,
    get_runtime_service,
    get_user_service,
)
from app.domain.users import UserStatus
from app.repositories.model_repository import (
    get_inmemory_credential_repository,
    get_inmemory_usage_repository,
)
from app.schemas.admin import (
    UpdateUserStatusRequest,
    AdminUserRuntimeResponse,
    AdminUserCredentialsResponse,
    AdminUsageSummaryResponse,
)
from app.services.runtime_service import RuntimeService
from app.services.user_service import UserService


router = APIRouter(tags=["admin"])


def _require_admin(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
    """
    admin 权限校验依赖。
    """

    if not ctx.isAdmin:
        from app.core.errors import AccessDeniedError

        raise AccessDeniedError()
    return ctx


@router.get("/admin/users")
async def list_users(
    _: AuthContext = Depends(_require_admin),
    user_service: UserService = Depends(get_user_service),
) -> list[dict]:
    """
    管理员查看用户列表（最小字段集）。
    """

    # 目前 UserService 尚未提供列表能力，MVP 使用仓储私有属性兜底。
    repo = user_service._user_repo  # type: ignore[attr-defined]
    users = []
    if hasattr(repo, "_users"):
        users = list(repo._users.values())  # type: ignore[attr-defined]

    return [
        {
            "userId": u.user_id,
            "subjectId": u.subject_id,
            "role": u.role.value,
            "status": u.status.value,
        }
        for u in users
    ]


@router.get("/admin/users/{user_id}")
async def get_admin_user_detail(
    user_id: str,
    _: AuthContext = Depends(_require_admin),
    user_service: UserService = Depends(get_user_service),
) -> dict:
    """
    管理员查看用户详情。
    """

    user = user_service.get_user_by_id(user_id)
    if user is None:
        from app.core.errors import UserNotFoundError

        raise UserNotFoundError()

    return {
        "userId": user.user_id,
        "subjectId": user.subject_id,
        "tenantId": user.tenant_id,
        "role": user.role.value,
        "status": user.status.value,
    }


@router.patch("/admin/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    body: UpdateUserStatusRequest,
    _: AuthContext = Depends(_require_admin),
    user_service: UserService = Depends(get_user_service),
    runtime_service: RuntimeService = Depends(get_runtime_service),
) -> dict:
    """
    启用 / 禁用用户。

    - 更新 User.status。
    - 当改为 disabled 时，触发 runtime 收敛停止。
    """

    new_status = UserStatus(body.status)
    user = user_service.set_user_status(user_id, new_status)

    if new_status == UserStatus.DISABLED:
        runtime_service.stop_runtime(user_id)

    return {"userId": user.user_id, "status": user.status.value}


@router.get("/admin/users/{user_id}/runtime", response_model=AdminUserRuntimeResponse)
async def get_admin_user_runtime(
    user_id: str,
    _: AuthContext = Depends(_require_admin),
    user_service: UserService = Depends(get_user_service),
) -> AdminUserRuntimeResponse:
    """
    管理员查看指定用户的 runtime 详情。
    """

    binding = user_service.get_runtime_binding(user_id)
    if binding is None:
        from app.core.errors import RuntimeNotFoundError

        raise RuntimeNotFoundError()

    return AdminUserRuntimeResponse(
        runtime_id=binding.runtime_id,
        desired_state=binding.desired_state.value,
        observed_state=binding.observed_state.value,
        browser_url=binding.browser_url,
        internal_endpoint=binding.internal_endpoint,
        last_error=binding.last_error,
    )


@router.get(
    "/admin/users/{user_id}/credentials",
    response_model=AdminUserCredentialsResponse,
)
async def get_admin_user_credentials(
    user_id: str,
    _: AuthContext = Depends(_require_admin),
) -> AdminUserCredentialsResponse:
    """
    管理员查看指定用户的凭据元数据。
    """

    cred_repo = get_inmemory_credential_repository()
    credentials = cred_repo.list_credentials_for_user(user_id)
    return AdminUserCredentialsResponse(
        credentials=[
            {
                "credentialId": c.credential_id,
                "name": c.name,
                "status": c.status.value,
                "lastValidatedAt": c.last_validated_at,
            }
            for c in credentials
        ]
    )


@router.get("/admin/usage/summary", response_model=AdminUsageSummaryResponse)
async def get_admin_usage_summary(
    _: AuthContext = Depends(_require_admin),
) -> AdminUsageSummaryResponse:
    """
    管理员查看平台 usage 汇总。
    """

    usage_repo = get_inmemory_usage_repository()
    total_tokens = 0
    used_tokens = 0
    if hasattr(usage_repo, "_usage"):
        for summary in usage_repo._usage.values():  # type: ignore[attr-defined]
            total_tokens += summary.total_tokens
            used_tokens += getattr(summary, "used_tokens", 0)

    return AdminUsageSummaryResponse(
        total_tokens=total_tokens,
        used_tokens=used_tokens,
    )


