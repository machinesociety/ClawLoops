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


class FakeBindingPort:
    def __init__(self) -> None:
        self.binding: RuntimeBindingSnapshot | None = None
        self.patched: list[RuntimeBindingSnapshot] = []

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
        self.patched.append(self.binding)
        return self.binding


class FakeModelConfigPort:
    def get_user_model_config(self, user_id: str) -> ModelConfig:
        return ModelConfig(
            base_url="http://litellm:4000",
            models=["gpt-4-mini"],
            gateway_access_token_ref="token_ref_001",
            config_render_version="v1",
        )


class FakeRuntimeManagerPort:
    def __init__(self) -> None:
        self.ensure_payloads: list[dict] = []

    def ensure_running(self, payload: dict) -> dict:
        self.ensure_payloads.append(payload)
        return {
            "runtimeId": payload["runtimeId"],
            "observedState": "creating",
            "internalEndpoint": "http://clawloops-u001:3000",
            "browserUrl": "http://127.0.0.1:18789", # 新增本地测试
            "message": "creating",
        }

    def stop(self, user_id: str, runtime_id: str) -> dict:
        _ = user_id
        return {"status": "accepted"}

    def delete(self,user_id: str,runtime_id: str,retention_policy: str,compat: dict | None = None,) -> dict:
        _ = user_id
        _ = runtime_id
        _ = retention_policy
        _ = compat # 新增
        return {"status": "accepted"}


def _make_fake_runtime_service() -> tuple[RuntimeService, FakeBindingPort, FakeRuntimeManagerPort]:
    binding_port = FakeBindingPort()
    model_port = FakeModelConfigPort()
    runtime_manager = FakeRuntimeManagerPort()
    task_repo = InMemoryRuntimeTaskRepository()
    # 注释掉 base_dir，因为测试环境没有挂载文件系统
    # renderer = RuntimeConfigRenderer(base_dir="/tmp/clawloops-int-tests")
    renderer = RuntimeConfigRenderer(litellm_api_key="sk-test")
    svc = RuntimeService(
        binding_service=binding_port,
        model_config_service=model_port,
        runtime_manager=runtime_manager,
        task_repo=task_repo,
        config_renderer=renderer,
        route_host_suffix="clawloops.test",
    )
    return svc, binding_port, runtime_manager


def test_half_main_flow_login_sync_ensure_start_and_query_task(client, app):
    """
    半主流程测试：
    登录 -> 同步用户 -> ensure binding -> 启动 runtime -> 查任务状态。
    同时覆盖模块 3 的启动编排与状态回写。
    """
    svc, binding_port, runtime_manager = _make_fake_runtime_service()

    # 覆盖依赖注入
    app.dependency_overrides[get_runtime_service] = lambda: svc

    try:
        subject = "authentik:runtime-int"
        headers = _auth_headers(subject)

        # 通过模块 1/2 跑一次同步与 binding ensure
        resp_sync = client.post("/internal/users/sync", json={"subjectId": subject})
        assert resp_sync.status_code == status.HTTP_200_OK
        user_id = resp_sync.json()["userId"]

        resp_binding = client.post(f"/internal/users/{user_id}/runtime-binding/ensure")
        assert resp_binding.status_code == status.HTTP_200_OK

        # 调用模块 3 对外启动接口
        resp_start = client.post("/api/v1/users/me/runtime/start", headers=headers)
        assert resp_start.status_code == status.HTTP_202_ACCEPTED
        start_body = resp_start.json()
        assert start_body["action"] == "ensure_running"
        assert start_body["status"] == "accepted"
        task_id = start_body["taskId"]

        # runtime manager 被调用，并携带关键字段
        assert len(runtime_manager.ensure_payloads) == 1
        payload = runtime_manager.ensure_payloads[0]
        assert payload["volumeId"]
        assert payload["routeHost"]
        assert "compat" in payload
        assert payload["compat"]["openclawConfigDir"]
        assert payload["compat"]["openclawWorkspaceDir"]
        
        # assert "configMount" in payload
        # assert "configFilePath" in payload["configMount"]
        # assert "secretFilePath" in payload["configMount"]
        
        assert "renderedConfig" in payload
        assert payload["renderedConfig"]["configVersion"]
        assert payload["renderedConfig"]["openclawJson"]

        # binding 状态被回写
        assert binding_port.binding is not None
        assert binding_port.binding.browserUrl is not None
        assert binding_port.binding.internalEndpoint is not None
        assert binding_port.binding.observedState.value in ("creating", "running")
        assert binding_port.binding.lastError is None

        # 任务查询接口能返回最终状态
        resp_task = client.get(f"/api/v1/runtime/tasks/{task_id}", headers=headers)
        assert resp_task.status_code == status.HTTP_200_OK
        task_body = resp_task.json()
        assert task_body["taskId"] == task_id
        assert task_body["action"] == "ensure_running"
        assert task_body["status"] in ("running", "succeeded", "failed")
    finally:
        app.dependency_overrides.pop(get_runtime_service, None)

