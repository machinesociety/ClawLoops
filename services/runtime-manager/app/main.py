from __future__ import annotations

import os
from typing import Any

import docker
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from docker.errors import APIError, DockerException, NotFound

from contracts.enums import ObservedState
from contracts.models import (
    DeleteRequest,
    DeleteResponse,
    EnsureRunningRequest,
    EnsureRunningResponse,
    RuntimeStatusResponse,
    StopRequest,
    StopResponse,
)

app = FastAPI(
    title="Runtime Manager",
    version="0.1.0",
    description="Internal Runtime Manager service bootstrap endpoint.",
)

OPENCLAW_IMAGE = os.getenv(
    "RUNTIME_OPENCLAW_IMAGE",
    "ghcr.io/openclaw/openclaw@sha256:a5a4c83b773aca85a8ba99cf155f09afa33946c0aa5cc6a9ccb6162738b5da02",
)
OPENCLAW_COMMAND = ["node", "dist/index.js", "gateway", "--bind", "lan", "--port", "18789"]
OPENCLAW_NETWORK = os.getenv("RUNTIME_OPENCLAW_NETWORK", "clawloops_shared")
INTERNAL_PORT = 18789
_runtime_states: dict[str, ObservedState] = {}


def _docker_client():
    return docker.from_env()


def _runtime_container_name(runtime_id: str) -> str:
    return f"rt-{runtime_id}"


def _internal_endpoint(runtime_id: str) -> str:
    return f"http://rt-{runtime_id}:{INTERNAL_PORT}"


def _browser_url_from_container(container) -> str | None:
    ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
    bound = ports.get(f"{INTERNAL_PORT}/tcp") or []
    if not bound:
        return None
    host_port = bound[0].get("HostPort")
    if not host_port:
        return None
    return f"http://127.0.0.1:{host_port}"


def _ensure_host_dirs(body: EnsureRunningRequest) -> None:
    os.makedirs(body.compat.openclaw_config_dir, exist_ok=True)
    os.makedirs(body.compat.openclaw_workspace_dir, exist_ok=True)


def _build_environment(body: EnsureRunningRequest) -> dict[str, str]:
    env = {
        "HOME": "/home/node",
        "TERM": "xterm-256color",
        "TZ": "UTC",
        "OPENAI_BASE_URL": "http://litellm:4000",
    }
    if body.env:
        env.update(body.env)
    if body.env_overrides:
        env.update(body.env_overrides)
    # Frozen contract: this value cannot be overridden.
    env["OPENAI_BASE_URL"] = "http://litellm:4000"
    return env


def _build_volumes(body: EnsureRunningRequest) -> dict[str, dict[str, Any]]:
    volumes: dict[str, dict[str, Any]] = {
        body.compat.openclaw_config_dir: {"bind": "/home/node/.openclaw", "mode": "rw"},
        body.compat.openclaw_workspace_dir: {"bind": "/home/node/.openclaw/workspace", "mode": "rw"},
    }
    if body.config_mount:
        volumes[body.config_mount.config_file_path] = {"bind": "/home/node/.openclaw/openclaw.json", "mode": "ro"}
        volumes[body.config_mount.secret_file_path] = {"bind": "/run/clawloops/secrets/gateway.token", "mode": "ro"}
    return volumes


def _container_contract_matches(container) -> bool:
    image_id = container.image.id or ""
    command = container.attrs.get("Config", {}).get("Cmd") or []
    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
    ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
    return (
        image_id.startswith("sha256:")
        and command == OPENCLAW_COMMAND
        and OPENCLAW_NETWORK in networks
        and f"{INTERNAL_PORT}/tcp" in ports
    )


@app.exception_handler(DockerException)
async def handle_docker_exception(_, exc: DockerException):
    return JSONResponse(status_code=500, content={"code": "RUNTIME_START_FAILED", "message": str(exc)})


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "runtime-manager", "status": "ok"}


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/internal/runtime-manager/containers/ensure-running", response_model=EnsureRunningResponse)
async def ensure_running_container(body: EnsureRunningRequest) -> EnsureRunningResponse:
    _ensure_host_dirs(body)
    name = _runtime_container_name(body.runtime_id)
    aliases = [name]
    env = _build_environment(body)
    volumes = _build_volumes(body)
    client = _docker_client()

    try:
        container = client.containers.get(name)
        if not _container_contract_matches(container):
            return JSONResponse(
                status_code=409,
                content={"code": "RUNTIME_CONTRACT_DRIFT", "message": f"container {name} contract drift"},
            )
        if container.status != "running":
            _runtime_states[body.runtime_id] = ObservedState.CREATING
            container.start()
            container.reload()
        state = ObservedState.RUNNING if container.status == "running" else ObservedState.CREATING
        _runtime_states[body.runtime_id] = state
        return EnsureRunningResponse(
            runtime_id=body.runtime_id,
            observed_state=state,
            browser_url=_browser_url_from_container(container),
            internal_endpoint=_internal_endpoint(body.runtime_id),
            message=state.value,
        )
    except NotFound:
        _runtime_states[body.runtime_id] = ObservedState.CREATING
        container = client.containers.create(
            OPENCLAW_IMAGE,
            name=name,
            command=OPENCLAW_COMMAND,
            ports={f"{INTERNAL_PORT}/tcp": None},
            environment=env,
            volumes=volumes,
            labels={
                "clawloops.runtime_id": body.runtime_id,
                "clawloops.user_id": body.user_id,
                "clawloops.volume_id": body.volume_id,
                "clawloops.route_host": body.route_host,
            },
            restart_policy={"Name": "unless-stopped"},
        )
        client.api.connect_container_to_network(container.id, OPENCLAW_NETWORK, aliases=aliases)
        container.start()
        container.reload()
        state = ObservedState.RUNNING if container.status == "running" else ObservedState.CREATING
        _runtime_states[body.runtime_id] = state
        return EnsureRunningResponse(
            runtime_id=body.runtime_id,
            observed_state=state,
            browser_url=_browser_url_from_container(container),
            internal_endpoint=_internal_endpoint(body.runtime_id),
            message=state.value,
        )
    except APIError as exc:
        _runtime_states[body.runtime_id] = ObservedState.ERROR
        return JSONResponse(
            status_code=500,
            content={"code": "RUNTIME_START_FAILED", "message": str(exc)},
        )


@app.post("/internal/runtime-manager/containers/stop", response_model=StopResponse)
async def stop_container(body: StopRequest) -> StopResponse:
    name = _runtime_container_name(body.runtime_id)
    try:
        container = _docker_client().containers.get(name)
        if container.status == "running":
            container.stop(timeout=15)
    except NotFound:
        pass
    except APIError as exc:
        return JSONResponse(
            status_code=500,
            content={"code": "RUNTIME_STOP_FAILED", "message": str(exc)},
        )
    _runtime_states[body.runtime_id] = ObservedState.STOPPED
    return StopResponse(runtime_id=body.runtime_id, observed_state=ObservedState.STOPPED, message="stopped")


@app.post("/internal/runtime-manager/containers/delete", response_model=DeleteResponse)
async def delete_container(body: DeleteRequest) -> DeleteResponse:
    name = _runtime_container_name(body.runtime_id)
    try:
        container = _docker_client().containers.get(name)
        container.remove(force=True)
    except NotFound:
        pass
    except APIError as exc:
        return JSONResponse(
            status_code=500,
            content={"code": "RUNTIME_DELETE_FAILED", "message": str(exc)},
        )

    if body.retention_policy.value == "wipe_workspace":
        try:
            workspace_dir = os.path.join("/var/lib/clawloops", body.user_id, "workspace")
            if os.path.isdir(workspace_dir):
                for root, dirs, files in os.walk(workspace_dir, topdown=False):
                    for file_name in files:
                        os.remove(os.path.join(root, file_name))
                    for dir_name in dirs:
                        os.rmdir(os.path.join(root, dir_name))
        except OSError:
            # Workspace cleanup is best effort; container state should still be deleted.
            pass
    _runtime_states[body.runtime_id] = ObservedState.DELETED
    return DeleteResponse(runtime_id=body.runtime_id, observed_state=ObservedState.DELETED, message="deleted")


@app.get("/internal/runtime-manager/containers/{runtime_id}", response_model=RuntimeStatusResponse)
async def get_container_status(runtime_id: str) -> RuntimeStatusResponse:
    name = _runtime_container_name(runtime_id)
    observed = _runtime_states.get(runtime_id, ObservedState.DELETED)
    browser_url: str | None = None
    try:
        container = _docker_client().containers.get(name)
        container.reload()
        browser_url = _browser_url_from_container(container)
        if container.status == "running":
            observed = ObservedState.RUNNING
        else:
            observed = ObservedState.STOPPED
    except NotFound:
        observed = ObservedState.DELETED
    except APIError:
        observed = ObservedState.ERROR
    _runtime_states[runtime_id] = observed
    return RuntimeStatusResponse(
        runtime_id=runtime_id,
        observed_state=observed,
        browser_url=browser_url,
        internal_endpoint=None if observed == ObservedState.DELETED else _internal_endpoint(runtime_id),
        message=observed.value,
    )
