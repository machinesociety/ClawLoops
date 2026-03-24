from pydantic import BaseModel, ConfigDict, Field

from contracts.enums import ObservedState, RetentionPolicy


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class ContractModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel, extra="forbid")


class ConfigMount(ContractModel):
    config_file_path: str = Field(..., min_length=1)
    secret_file_path: str = Field(..., min_length=1)


class CompatConfig(ContractModel):
    openclaw_config_dir: str = Field(..., min_length=1)
    openclaw_workspace_dir: str = Field(..., min_length=1)


class EnsureRunningRequest(ContractModel):
    user_id: str = Field(..., min_length=1)
    runtime_id: str = Field(..., min_length=1)
    volume_id: str = Field(..., min_length=1)
    route_host: str = Field(..., min_length=1)
    config_mount: ConfigMount | None = None
    retention_policy: RetentionPolicy
    compat: CompatConfig
    env: dict[str, str] | None = None
    env_overrides: dict[str, str] | None = None


class EnsureRunningResponse(ContractModel):
    runtime_id: str = Field(..., min_length=1)
    observed_state: ObservedState
    browser_url: str | None = None
    internal_endpoint: str | None = None
    message: str = Field(..., min_length=1)


class StopRequest(ContractModel):
    user_id: str = Field(..., min_length=1)
    runtime_id: str = Field(..., min_length=1)


class StopResponse(ContractModel):
    runtime_id: str = Field(..., min_length=1)
    observed_state: ObservedState = Field(default=ObservedState.STOPPED)
    message: str = Field(..., min_length=1)


class DeleteRequest(ContractModel):
    user_id: str = Field(..., min_length=1)
    runtime_id: str = Field(..., min_length=1)
    retention_policy: RetentionPolicy


class DeleteResponse(ContractModel):
    runtime_id: str = Field(..., min_length=1)
    observed_state: ObservedState = Field(default=ObservedState.DELETED)
    message: str = Field(..., min_length=1)


class RuntimeStatusResponse(ContractModel):
    runtime_id: str = Field(..., min_length=1)
    observed_state: ObservedState
    browser_url: str | None = None
    internal_endpoint: str | None = None
    message: str = Field(..., min_length=1)


class ErrorResponse(ContractModel):
    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
