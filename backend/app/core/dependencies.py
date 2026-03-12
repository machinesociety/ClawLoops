from fastapi import Depends

from app.core.auth import AuthContext
from app.core.settings import AppSettings, get_settings


def get_app_settings() -> AppSettings:
    return get_settings()


def get_auth_context(
    # TODO: 未来接入实际的鉴权中间件，从请求中解析 AuthContext。
    settings: AppSettings = Depends(get_app_settings),
) -> AuthContext:
    # 目前作为占位，返回一个固定用户，便于联调。
    return AuthContext(
        user_id="u_001",
        subject_id="authentik:12345",
        tenant_id="t_default",
        role="user",
        is_admin=False,
        is_disabled=False,
    )

