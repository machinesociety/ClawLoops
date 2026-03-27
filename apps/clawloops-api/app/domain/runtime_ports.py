from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.runtime import RuntimeTask
from app.schemas.internal import ModelConfigResponse
from app.schemas.runtime import RuntimeBindingSnapshot


@dataclass
class ModelConfig:
    """
    运行时模型配置的领域视图。
    """

    base_url: str
    models: list[str]
    gateway_access_token_ref: str
    config_render_version: str

    @classmethod
    def from_response(cls, resp: ModelConfigResponse) -> "ModelConfig":
        return cls(
            base_url=resp.baseUrl,
            models=resp.models,
            gateway_access_token_ref=resp.gatewayAccessTokenRef,
            config_render_version=resp.configRenderVersion,
        )


class UserRuntimeBindingServicePort(Protocol):
    """
    模块 3 访问 UserRuntimeBinding 的抽象端口。
    """

    def ensure_binding(self, user_id: str) -> RuntimeBindingSnapshot:
        ...

    def patch_binding_state(
        self,
        user_id: str,
        desired_state: str,
        observed_state: str,
        browser_url: str | None,
        internal_endpoint: str | None,
        last_error: str | None,
    ) -> RuntimeBindingSnapshot | None:
        ...


class ModelConfigServicePort(Protocol):
    """
    模块 3 访问模型配置的抽象端口。
    """

    def get_user_model_config(self, user_id: str) -> ModelConfig:
        ...


class RuntimeManagerPort(Protocol):
    """
    对 runtime manager 的抽象端口。
    """

    def ensure_running(self, payload: dict) -> dict:
        ...

    def stop(self, user_id: str, runtime_id: str) -> dict:
        ...

    def delete(
        self,
        user_id: str,
        runtime_id: str,
        retention_policy: str,
        compat: dict[str, str] | None = None,
    ) -> dict:
        ...


class RuntimeTaskRepository(Protocol):
    """
    任务仓储抽象，后续可替换为持久化实现。
    """

    def save(self, task: RuntimeTask) -> None:
        ...

    def get(self, task_id: str) -> RuntimeTask | None:
        ...

