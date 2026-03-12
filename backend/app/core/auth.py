from pydantic import BaseModel


class AuthContext(BaseModel):
    """当前请求的认证上下文，占位与模块 1 对齐。"""

    user_id: str
    subject_id: str
    tenant_id: str
    role: str
    is_admin: bool = False
    is_disabled: bool = False

