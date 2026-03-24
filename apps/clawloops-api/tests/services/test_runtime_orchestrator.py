from app.domain.runtime import RuntimeAction, RuntimeTask, TaskStatus
from app.domain.runtime_ports import ModelConfig
from app.schemas.runtime import DesiredState, ObservedState, RetentionPolicy, RuntimeBindingSnapshot
from app.services.runtime_config_renderer import RuntimeConfigRenderer
from app.services.runtime_service import InMemoryRuntimeTaskRepository, RuntimeService


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
        self.stop_calls: list[tuple[str, str]] = []
        self.delete_calls: list[tuple[str, str, str]] = []
        self.should_fail = False

    def ensure_running(self, payload: dict) -> dict:
        self.ensure_payloads.append(payload)
        if self.should_fail:
            raise RuntimeError("runtime manager error")
        return {
            "runtimeId": payload["runtimeId"],
            "observedState": "creating",
            "internalEndpoint": "http://clawloops-u001:3000",
            "message": "creating",
        }

    def stop(self, user_id: str, runtime_id: str) -> dict:
        self.stop_calls.append((user_id, runtime_id))
        if self.should_fail:
            raise RuntimeError("stop error")
        return {"status": "accepted"}

    def delete(self, user_id: str, runtime_id: str, retention_policy: str) -> dict:
        self.delete_calls.append((user_id, runtime_id, retention_policy))
        if self.should_fail:
            raise RuntimeError("delete error")
        return {"status": "accepted"}


def _make_service() -> tuple[RuntimeService, FakeBindingPort, FakeRuntimeManagerPort, InMemoryRuntimeTaskRepository]:
    binding_port = FakeBindingPort()
    model_port = FakeModelConfigPort()
    runtime_manager = FakeRuntimeManagerPort()
    task_repo = InMemoryRuntimeTaskRepository()
    renderer = RuntimeConfigRenderer(base_dir="/tmp/clawloops-tests")
    svc = RuntimeService(
        binding_service=binding_port,
        model_config_service=model_port,
        runtime_manager=runtime_manager,
        task_repo=task_repo,
        config_renderer=renderer,
        route_host_suffix="clawloops.test",
    )
    return svc, binding_port, runtime_manager, task_repo


def test_task_state_machine_happy_path():
    task = RuntimeTask(
        task_id="t1",
        user_id="u1",
        runtime_id="rt1",
        action=RuntimeAction.ENSURE_RUNNING,
        status=TaskStatus.PENDING,
    )
    task.start()
    assert task.status == TaskStatus.RUNNING
    task.succeed("ok")
    assert task.status == TaskStatus.SUCCEEDED
    assert task.message == "ok"


def test_task_fail_and_cancel_transitions():
    task = RuntimeTask(
        task_id="t2",
        user_id="u1",
        runtime_id="rt1",
        action=RuntimeAction.STOP,
        status=TaskStatus.PENDING,
    )
    task.fail("err")
    assert task.status == TaskStatus.FAILED
    assert task.message == "err"

    # terminal 状态下 cancel 不应改变状态
    task.cancel("cancel")
    assert task.status == TaskStatus.FAILED


def test_ensure_running_creates_binding_and_calls_runtime_manager(tmp_path):
    svc, binding_port, runtime_manager, task_repo = _make_service()

    task = svc.ensure_running("u_001")
    assert task.action == RuntimeAction.ENSURE_RUNNING
    assert task.status == TaskStatus.SUCCEEDED
    assert task.task_id in task_repo._tasks  # type: ignore[attr-defined]

    assert binding_port.binding is not None
    assert binding_port.binding.desiredState == DesiredState.running
    assert binding_port.binding.observedState == ObservedState.creating
    assert binding_port.binding.browserUrl is not None
    assert binding_port.binding.lastError is None

    assert len(runtime_manager.ensure_payloads) == 1
    payload = runtime_manager.ensure_payloads[0]
    assert payload["runtimeId"] == binding_port.binding.runtimeId
    assert "configMount" in payload
    assert "configFilePath" in payload["configMount"]
    assert "secretFilePath" in payload["configMount"]
    assert "compat" in payload
    assert payload["compat"]["openclawConfigDir"]
    assert payload["compat"]["openclawWorkspaceDir"]


def test_ensure_running_failure_sets_error_state_and_last_error():
    svc, binding_port, runtime_manager, _ = _make_service()
    runtime_manager.should_fail = True

    task = svc.ensure_running("u_err")
    assert task.status == TaskStatus.FAILED
    assert task.message

    assert binding_port.binding is not None
    assert binding_port.binding.observedState == ObservedState.error
    assert binding_port.binding.lastError is not None


def test_stop_runtime_idempotent_and_updates_state():
    svc, binding_port, runtime_manager, _ = _make_service()

    # 先确保有 binding
    binding_port.ensure_binding("u_001")
    task = svc.stop_runtime("u_001")
    assert task.action == RuntimeAction.STOP
    assert task.status == TaskStatus.SUCCEEDED
    assert binding_port.binding is not None
    assert binding_port.binding.desiredState == DesiredState.stopped
    assert binding_port.binding.observedState == ObservedState.stopped
    assert runtime_manager.stop_calls == [("u_001", binding_port.binding.runtimeId)]


def test_delete_respects_retention_policy_and_marks_deleted():
    svc, binding_port, runtime_manager, _ = _make_service()
    binding_port.ensure_binding("u_001")

    task = svc.delete_runtime("u_001", retention_policy="wipe_workspace")
    assert task.action == RuntimeAction.DELETE
    assert task.status == TaskStatus.SUCCEEDED
    assert binding_port.binding is not None
    assert binding_port.binding.desiredState == DesiredState.deleted
    assert binding_port.binding.observedState == ObservedState.deleted
    assert binding_port.binding.browserUrl is None
    assert binding_port.binding.internalEndpoint is None
    assert runtime_manager.delete_calls == [
        ("u_001", binding_port.binding.runtimeId, "wipe_workspace")
    ]

