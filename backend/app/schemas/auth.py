from pydantic import BaseModel


class AuthMeResponse(BaseModel):
    """对应 GET /api/v1/auth/me 的响应体。"""

    authenticated: bool
    userId: str
    subjectId: str
    tenantId: str
    role: str
    isAdmin: bool
    isDisabled: bool


class AccessCheckResponse(BaseModel):
    """对应 GET /api/v1/auth/access 的响应体。"""

    allowed: bool
    reason: str | None = None

