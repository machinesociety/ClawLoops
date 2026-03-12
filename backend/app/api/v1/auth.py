from fastapi import APIRouter, Depends

from app.core.auth import AuthContext
from app.core.dependencies import get_auth_context
from app.schemas.auth import AccessCheckResponse, AuthMeResponse


router = APIRouter(tags=["auth"])


@router.get("/auth/me", response_model=AuthMeResponse)
async def get_current_user(ctx: AuthContext = Depends(get_auth_context)) -> AuthMeResponse:
    """获取当前登录用户，即使 disabled 也可访问。"""

    return AuthMeResponse(
        authenticated=True,
        userId=ctx.userId,
        subjectId=ctx.subjectId,
        tenantId=ctx.tenantId,
        role=ctx.role,
        isAdmin=ctx.isAdmin,
        isDisabled=ctx.isDisabled,
    )


@router.get("/auth/access", response_model=AccessCheckResponse)
async def check_access(ctx: AuthContext = Depends(get_auth_context)) -> AccessCheckResponse:
    """检查当前用户是否可访问业务。"""

    if ctx.isDisabled:
        return AccessCheckResponse(allowed=False, reason="USER_DISABLED")
    return AccessCheckResponse(allowed=True, reason=None)

