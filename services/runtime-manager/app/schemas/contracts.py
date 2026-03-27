from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


ObservedState = Literal["creating", "running", "stopped", "error", "deleted"]
RetentionPolicy = Literal["preserve_workspace", "wipe_workspace"]


class CompatConfig(BaseModel):
    openclawConfigDir: str
    openclawWorkspaceDir: str


class RenderedConfig(BaseModel):
    configVersion: str
    openclawJson: dict


class EnsureContainerRequest(BaseModel):
    userId: str
    runtimeId: str
    volumeId: str
    routeHost: str
    retentionPolicy: RetentionPolicy
    compat: CompatConfig
    renderedConfig: RenderedConfig

    @model_validator(mode="after")
    def _validate_required_rendered_values(self) -> "EnsureContainerRequest":
        gateway = self.renderedConfig.openclawJson.get("gateway", {})
        if gateway.get("bind") != "lan" or gateway.get("port") != 18789:
            raise ValueError("renderedConfig.gateway must be bind=lan and port=18789")
        return self


class StopContainerRequest(BaseModel):
    userId: str
    runtimeId: str


class DeleteContainerRequest(BaseModel):
    userId: str
    runtimeId: str
    retentionPolicy: RetentionPolicy
    compat: CompatConfig | None = None


class ContainerStateResponse(BaseModel):
    runtimeId: str
    observedState: ObservedState
    internalEndpoint: str | None = None
    message: str | None = None


class ErrorResponse(BaseModel):
    code: str = Field(..., description="Platform error code")
    message: str
