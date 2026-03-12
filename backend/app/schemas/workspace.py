from pydantic import BaseModel

from app.schemas.runtime import WorkspaceEntryReason


class WorkspaceEntryResponse(BaseModel):
    ready: bool
    runtimeId: str | None = None
    browserUrl: str | None = None
    reason: WorkspaceEntryReason | None = None

