from fastapi import status

from app.core.dependencies import get_runtime_service
from app.domain.runtime_ports import ModelConfig
from app.schemas.runtime import DesiredState, ObservedState, RetentionPolicy, RuntimeBindingSnapshot
from app.services.runtime_config_renderer import RuntimeConfigRenderer
from app.services.runtime_service import (
    InMemoryRuntimeTaskRepository,
    RuntimeService,
)


def _auth_headers(subject: str) -> dict[str, str]:
    return {"X-Authentik-Subject": subject}


class _FakeBindingPort:
    def __init__(self) -> None:
        self.binding: RuntimeBindingSnapshot | None = None

    def ensure_binding(self, user_id: str) -> RuntimeBindingSnapshot:
        if self.binding is None:
            self.binding = RuntimeBindingSnapshot(
                runtimeId="rt_001",
                volumeId="vol_001",
                imageRef="clawloops-runtime-wrapper:openclaw-1.0.0",
                desiredState=DesiredState.stopped,
                observedState=ObservedState.stopped,
                browserUrl=None,
                internalEndpoint=None,
                retentionPolicy=RetentionPolicy.preserve_workspace,
                lastError=None,
            )
        return self.binding

    def patch_binding_state(
        self,
        user_id: str,
        desired_state: str,
        observed_state: str,
        browser_url: str | None,
        internal_endpoint: str | None,
        last_error: str | None,
    ) -> RuntimeBindingSnapshot:
        assert self.binding is not None
        self.binding = RuntimeBindingSnapshot(
            runtimeId=self.binding.runtimeId,
            volumeId=self.binding.volumeId,
            imageRef=self.binding.imageRef,
            desiredState=DesiredState(desired_state),
            observedState=ObservedState(observed_state),
            browserUrl=browser_url,
            internalEndpoint=internal_endpoint,
            retentionPolicy=self.binding.retentionPolicy,
            lastError=last_error,
        )
        return self.binding


class _FakeModelConfigPort:
    def get_user_model_config(self, user_id: str) -> ModelConfig:
        return ModelConfig(
            base_url="http://litellm:4000",
            models=["gpt-4-mini"],
            gateway_access_token_ref="token_ref_001",
            config_render_version="v1",
        )


class _FakeRuntimeManagerPort:
    def __init__(self) -> None:
        self.ensure_payloads: list[dict] = []

    def ensure_running(self, payload: dict) -> dict:
        self.ensure_payloads.append(payload)
        return {
            "runtimeId": payload["runtimeId"],
            "observedState": "creating",
            "internalEndpoint": "http://clawloops-u001:3000",
            "message": "creating",
        }

    def stop(self, user_id: str, runtime_id: str) -> dict:
        _ = user_id
        return {"status": "accepted"}

    def delete(self, user_id: str, runtime_id: str, retention_policy: str) -> dict:
        _ = user_id
        _ = runtime_id
        _ = retention_policy
        return {"status": "accepted"}


def _make_fake_runtime_service() -> RuntimeService:
    binding_port = _FakeBindingPort()
    model_port = _FakeModelConfigPort()
    runtime_manager = _FakeRuntimeManagerPort()
    task_repo = InMemoryRuntimeTaskRepository()
    renderer = RuntimeConfigRenderer(base_dir="/tmp/clawloops-int-tests")
    return RuntimeService(
        binding_service=binding_port,
        model_config_service=model_port,
        runtime_manager=runtime_manager,
        task_repo=task_repo,
        config_renderer=renderer,
        route_host_suffix="clawloops.test",
    )


def test_module6_full_smoke_flow_login_to_workspace_entry(client, app):
    """
    完整 smoke test：
    登录 -> 同步用户 -> ensure binding -> 启动 runtime -> 查询状态 -> 获取 workspace-entry。
    """
    svc = _make_fake_runtime_service()
    app.dependency_overrides[get_runtime_service] = lambda: svc

    try:
        subject = "authentik:workbench-smoke"
        headers = _auth_headers(subject)

        # 同步或创建用户
        resp_sync = client.post("/internal/users/sync", json={"subjectId": subject})
        assert resp_sync.status_code == status.HTTP_200_OK
        user_id = resp_sync.json()["userId"]

        # ensure binding 存在
        resp_binding = client.post(f"/internal/users/{user_id}/runtime-binding/ensure")
        assert resp_binding.status_code == status.HTTP_200_OK
        runtime_id = resp_binding.json()["runtimeId"]

        # 启动 runtime
        resp_start = client.post("/api/v1/users/me/runtime/start", headers=headers)
        assert resp_start.status_code == status.HTTP_202_ACCEPTED
        start_body = resp_start.json()
        assert start_body["action"] == "ensure_running"
        assert start_body["status"] == "accepted"
        task_id = start_body["taskId"]

        # 查询任务状态
        resp_task = client.get(f"/api/v1/runtime/tasks/{task_id}", headers=headers)
        assert resp_task.status_code == status.HTTP_200_OK
        task_body = resp_task.json()
        assert task_body["taskId"] == task_id
        assert task_body["action"] == "ensure_running"
        assert task_body["status"] in ("running", "succeeded", "failed")

        # 查询 runtime/status
        resp_status = client.get("/api/v1/users/me/runtime/status", headers=headers)
        assert resp_status.status_code == status.HTTP_200_OK
        status_body = resp_status.json()
        # 只要求字段存在且 runtimeId 已写入
        assert status_body["runtimeId"] is not None
        assert status_body["desiredState"] in (None, "running", "stopped", "deleted")
        assert status_body["observedState"] in (
            None,
            "creating",
            "running",
            "stopped",
            "error",
            "deleted",
        )
        assert isinstance(status_body["ready"], bool)

        # 获取 workspace-entry
        resp_workspace = client.get("/api/v1/workspace-entry", headers=headers)
        assert resp_workspace.status_code == status.HTTP_200_OK
        workspace_body = resp_workspace.json()
        assert "ready" in workspace_body
        assert "runtimeId" in workspace_body
        assert "browserUrl" in workspace_body
        assert "reason" in workspace_body
        # runtimeId 至少要与 ensure-binding 时保持一致或为空（尚未 ready）
        assert workspace_body["runtimeId"] in (None, runtime_id)
    finally:
        app.dependency_overrides.pop(get_runtime_service, None)

