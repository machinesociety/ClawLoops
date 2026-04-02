from pydantic import BaseModel


class UserResponse(BaseModel):
    """用户信息响应模型"""
    userId: str
    subjectId: str
    username: str | None = None
    tenantId: str
    role: str
    status: str
