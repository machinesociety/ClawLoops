from __future__ import annotations

import uuid
from typing import Optional

from app.domain.runtime import RuntimeAction, RuntimeTask, TaskStatus
from app.domain.runtime_ports import (
    ModelConfigServicePort,
    RuntimeManagerPort,
    RuntimeTaskRepository,
    UserRuntimeBindingServicePort,
)
from app.schemas.runtime import DesiredState, ObservedState, RuntimeBindingSnapshot
from app.services.runtime_config_renderer import RuntimeConfigRenderer


class RuntimeService:
    """
    runtime 编排服务。
    """

    def __init__(
        self,
        binding_service: UserRuntimeBindingServicePort,
        model_config_service: ModelConfigServicePort,
        runtime_manager: RuntimeManagerPort,
        task_repo: RuntimeTaskRepository,
        config_renderer: RuntimeConfigRenderer,
        route_host_suffix: str = "clawloops.example.com",
    ) -> None:
        self._binding_service = binding_service
        self._model_config_service = model_config_service
        self._runtime_manager = runtime_manager
        self._task_repo = task_repo
        self._config_renderer = config_renderer
        self._route_host_suffix = route_host_suffix

    def _new_task(self, user_id: str, runtime_id: str, action: RuntimeAction) -> RuntimeTask:
        task = RuntimeTask(
            task_id=f"rtask_{uuid.uuid4().hex}",
            user_id=user_id,
            runtime_id=runtime_id,
            action=action,
            status=TaskStatus.PENDING,
            message="accepted",
        )
        self._task_repo.save(task)
        return task

    def _route_host_for_user(self, user_id: str) -> str:
        return f"u-{user_id}.{self._route_host_suffix}"

    def ensure_running(self, user_id: str) -> RuntimeTask:
        """
        创建或启动 runtime，并回写 binding 状态。
        """
        binding = self._binding_service.ensure_binding(user_id)
        task = self._new_task(user_id, binding.runtimeId, RuntimeAction.ENSURE_RUNNING)
        task.start()
        self._task_repo.save(task)

        try:
            model_config = self._model_config_service.get_user_model_config(user_id)
            openclaw_json, config_version = self._config_renderer.render(user_id, binding, model_config)

            route_host = self._route_host_for_user(user_id)
            payload = {
                "userId": user_id,
                "runtimeId": binding.runtimeId,
                "volumeId": binding.volumeId,
                "routeHost": route_host,
                "retentionPolicy": binding.retentionPolicy.value,
                "compat": {
                    "openclawConfigDir": f"/var/lib/clawloops/{user_id}/openclaw-config",
                    "openclawWorkspaceDir": f"/var/lib/clawloops/{user_id}/workspace",
                },
                "renderedConfig": {
                    "configVersion": config_version,
                    "openclawJson": openclaw_json,
                },
            }
            resp = self._runtime_manager.ensure_running(payload)
            observed_state = resp.get("observedState", ObservedState.creating.value)
            internal_endpoint = resp.get("internalEndpoint")
            message = resp.get("message", "creating")

            browser_url = resp.get("browserUrl") or f"https://{route_host}"
            self._binding_service.patch_binding_state(
                user_id=user_id,
                desired_state=DesiredState.running.value,
                observed_state=observed_state,
                browser_url=browser_url,
                internal_endpoint=internal_endpoint,
                last_error=None,
            )

            task.succeed(message)
            self._task_repo.save(task)
            return task
        except Exception as exc:  # pragma: no cover - 防御性兜底
            error_message = str(exc)
            self._binding_service.patch_binding_state(
                user_id=user_id,
                desired_state=DesiredState.running.value,
                observed_state=ObservedState.error.value,
                browser_url=None,
                internal_endpoint=None,
                last_error=error_message,
            )
            task.fail(error_message)
            self._task_repo.save(task)
            return task

    def stop_runtime(self, user_id: str) -> RuntimeTask:
        """
        幂等停止 runtime。
        """
        binding = self._binding_service.ensure_binding(user_id)
        task = self._new_task(user_id, binding.runtimeId, RuntimeAction.STOP)
        task.start()
        self._task_repo.save(task)

        try:
            self._runtime_manager.stop(user_id=user_id, runtime_id=binding.runtimeId)
            # 停止后将 desired/observed 统一置为 stopped
            self._binding_service.patch_binding_state(
                user_id=user_id,
                desired_state=DesiredState.stopped.value,
                observed_state=ObservedState.stopped.value,
                browser_url=binding.browserUrl,
                internal_endpoint=binding.internalEndpoint,
                last_error=None,
            )
            task.succeed("stopped")
            self._task_repo.save(task)
            return task
        except Exception as exc:  # pragma: no cover
            error_message = str(exc)
            self._binding_service.patch_binding_state(
                user_id=user_id,
                desired_state=DesiredState.stopped.value,
                observed_state=ObservedState.error.value,
                browser_url=binding.browserUrl,
                internal_endpoint=binding.internalEndpoint,
                last_error=error_message,
            )
            task.fail(error_message)
            self._task_repo.save(task)
            return task

    def delete_runtime(self, user_id: str, retention_policy: Optional[str] = None) -> RuntimeTask:
        """
        删除 runtime，并按 retentionPolicy 更新 binding。
        """
        binding = self._binding_service.ensure_binding(user_id)
        effective_policy = retention_policy or binding.retentionPolicy.value
        task = self._new_task(user_id, binding.runtimeId, RuntimeAction.DELETE)
        task.start()
        self._task_repo.save(task)

        try:
            self._runtime_manager.delete(
                user_id=user_id,
                runtime_id=binding.runtimeId,
                retention_policy=effective_policy,
                compat={
                    "openclawConfigDir": f"/var/lib/clawloops/{user_id}/openclaw-config",
                    "openclawWorkspaceDir": f"/var/lib/clawloops/{user_id}/workspace",
                },
            )
            self._binding_service.patch_binding_state(
                user_id=user_id,
                desired_state=DesiredState.deleted.value,
                observed_state=ObservedState.deleted.value,
                browser_url=None,
                internal_endpoint=None,
                last_error=None,
            )
            task.succeed("deleted")
            self._task_repo.save(task)
            return task
        except Exception as exc:  # pragma: no cover
            error_message = str(exc)
            self._binding_service.patch_binding_state(
                user_id=user_id,
                desired_state=DesiredState.deleted.value,
                observed_state=ObservedState.error.value,
                browser_url=None,
                internal_endpoint=None,
                last_error=error_message,
            )
            task.fail(error_message)
            self._task_repo.save(task)
            return task

    def get_task(self, task_id: str) -> RuntimeTask | None:
        return self._task_repo.get(task_id)


class InMemoryRuntimeTaskRepository(RuntimeTaskRepository):
    def __init__(self) -> None:
        self._tasks: dict[str, RuntimeTask] = {}

    def save(self, task: RuntimeTask) -> None:
        self._tasks[task.task_id] = task

    def get(self, task_id: str) -> RuntimeTask | None:
        return self._tasks.get(task_id)


class UserRuntimeBindingServiceAdapter(UserRuntimeBindingServicePort):
    """
    基于内部 UserRuntimeBinding Pydantic 模型的适配器。
    """

    def __init__(self, ensure_binding_fn, patch_state_fn) -> None:
        self._ensure_binding_fn = ensure_binding_fn
        self._patch_state_fn = patch_state_fn

    def ensure_binding(self, user_id: str) -> RuntimeBindingSnapshot:
        return self._ensure_binding_fn(user_id)

    def patch_binding_state(
        self,
        user_id: str,
        desired_state: str,
        observed_state: str,
        browser_url: str | None,
        internal_endpoint: str | None,
        last_error: str | None,
    ) -> RuntimeBindingSnapshot | None:
        return self._patch_state_fn(
            user_id=user_id,
            desired_state=desired_state,
            observed_state=observed_state,
            browser_url=browser_url,
            internal_endpoint=internal_endpoint,
            last_error=last_error,
        )


class ModelConfigServiceAdapter(ModelConfigServicePort):
    """
    使用内部固定实现的模型配置服务适配器。
    """

    def __init__(self, get_model_config_fn) -> None:
        self._get_model_config_fn = get_model_config_fn

    def get_user_model_config(self, user_id: str):
        from app.domain.runtime_ports import ModelConfig

        resp = self._get_model_config_fn(user_id)
        return ModelConfig.from_response(resp)


class RuntimeManagerPortAdapter(RuntimeManagerPort):
    """
    基于 RuntimeManagerClient 的适配器。
    """

    def __init__(self, client) -> None:
        self._client = client

    def ensure_running(self, payload: dict) -> dict:
        return self._client.ensure_running(payload)

    def stop(self, user_id: str, runtime_id: str) -> dict:
        return self._client.stop(user_id=user_id, runtime_id=runtime_id)

    def delete(
        self,
        user_id: str,
        runtime_id: str,
        retention_policy: str,
        compat: dict[str, str] | None = None,
    ) -> dict:
        return self._client.delete(
            user_id=user_id,
            runtime_id=runtime_id,
            retention_policy=retention_policy,
            compat=compat,
        )

