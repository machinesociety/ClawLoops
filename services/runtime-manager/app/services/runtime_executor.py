from __future__ import annotations

import shutil
import socket
import time
from pathlib import Path

import docker
from docker.errors import APIError, NotFound

from app.core.errors import RuntimeManagerError
from app.core.settings import Settings
from app.schemas.contracts import (
    ContainerStateResponse,
    DeleteContainerRequest,
    EnsureContainerRequest,
    StopContainerRequest,
)
from app.services.config_writer import prepare_runtime_dirs, write_openclaw_config
from app.services.drift_detector import detect_drift


class RuntimeExecutor:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._docker = docker.from_env()

    def _internal_endpoint(self, runtime_id: str) -> str:
        return f"http://rt-{runtime_id}:18789"

    def _browser_url_from_container(self, container) -> str | None:
        container.reload()
        ports = container.attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
        bindings = ports.get("18789/tcp")
        if not bindings:
            return None
        host_port = bindings[0].get("HostPort")
        if not host_port:
            return None
        return f"http://{self._settings.runtime_public_host}:{host_port}"

    def _list_managed(self, runtime_id: str):
        return self._docker.containers.list(
            all=True,
            filters={
                "label": [
                    "clawloops.managed=true",
                    f"clawloops.runtimeId={runtime_id}",
                ]
            },
        )

    def _get_single_container(self, runtime_id: str):
        containers = self._list_managed(runtime_id)
        if len(containers) > 1:
            raise RuntimeManagerError(
                "RUNTIME_ACTION_CONFLICT",
                "multiple managed containers matched the same runtimeId",
                409,
            )
        return containers[0] if containers else None

    def _wait_ready(self, host: str, port: int) -> bool:
        deadline = time.time() + self._settings.runtime_startup_grace_seconds
        consecutive = 0
        while time.time() < deadline:
            try:
                with socket.create_connection((host, port), timeout=0.5):
                    consecutive += 1
            except OSError:
                consecutive = 0
            if consecutive >= self._settings.runtime_startup_consecutive_successes:
                return True
            time.sleep(self._settings.runtime_startup_poll_seconds)
        return False

    def _create_runtime_container(self, req: EnsureContainerRequest, labels: dict[str, str], alias: str):
        container = self._docker.containers.create(
            image=self._settings.runtime_openclaw_image_ref,
            command=self._settings.runtime_openclaw_command.split(" "),
            labels=labels,
            environment={
                "HOME": "/home/node",
                "TERM": "xterm-256color",
                "TZ": "UTC",
                "OPENAI_BASE_URL": "http://litellm:4000",
            },
            volumes={
                req.compat.openclawConfigDir: {"bind": "/home/node/.openclaw", "mode": "rw"},
                req.compat.openclawWorkspaceDir: {
                    "bind": "/home/node/.openclaw/workspace",
                    "mode": "rw",
                },
            },
            ports={"18789/tcp": None},
        )
        network = self._docker.networks.get(self._settings.runtime_openclaw_network)
        network.connect(container, aliases=[alias])
        container.start()
        return container

    def ensure_running(self, req: EnsureContainerRequest) -> ContainerStateResponse:
        try:
            prepare_runtime_dirs(req.compat.openclawConfigDir, req.compat.openclawWorkspaceDir)
            write_openclaw_config(req.compat.openclawConfigDir, req.renderedConfig.openclawJson)

            def container_ip(c) -> str:
                c.reload()
                return (
                    c.attrs.get("NetworkSettings", {})
                    .get("Networks", {})
                    .get(self._settings.runtime_openclaw_network, {})
                    .get("IPAddress", "")
                )

            existing = self._get_single_container(req.runtimeId)
            if existing is not None:
                drifts = detect_drift(existing, req, self._settings)
                if drifts:
                    raise RuntimeManagerError(
                        "RUNTIME_CONTRACT_DRIFT",
                        "existing container contract drift detected",
                        409,
                    )
                if existing.status != "running":
                    existing.start()
                    existing.reload()
                    ip = container_ip(existing)
                    if existing.status == "running" and ip and not self._wait_ready(ip, 18789):
                        raise RuntimeManagerError(
                            "RUNTIME_START_FAILED",
                            "failed to prepare config or start container",
                            500,
                        )
                endpoint = self._internal_endpoint(req.runtimeId)
                browser_url = self._browser_url_from_container(existing)
                # Legacy runtimes created before host-port mapping rollout are auto-migrated once.
                if browser_url is None:
                    existing.remove(force=True)
                    labels = {
                        "clawloops.managed": "true",
                        "clawloops.userId": req.userId,
                        "clawloops.runtimeId": req.runtimeId,
                        "clawloops.volumeId": req.volumeId,
                        "clawloops.routeHost": req.routeHost,
                        "clawloops.retentionPolicy": req.retentionPolicy,
                        "clawloops.configVersion": req.renderedConfig.configVersion,
                    }
                    alias = f"rt-{req.runtimeId}"
                    migrated = self._create_runtime_container(req, labels, alias)
                    ip = container_ip(migrated)
                    if not ip or not self._wait_ready(ip, 18789):
                        raise RuntimeManagerError(
                            "RUNTIME_START_FAILED",
                            "failed to prepare config or start container",
                            500,
                        )
                    browser_url = self._browser_url_from_container(migrated)
                return ContainerStateResponse(
                    runtimeId=req.runtimeId,
                    observedState="running" if existing.status == "running" else "creating",
                    internalEndpoint=endpoint,
                    browserUrl=browser_url,
                    message="already running" if existing.status == "running" else "creating",
                )

            labels = {
                "clawloops.managed": "true",
                "clawloops.userId": req.userId,
                "clawloops.runtimeId": req.runtimeId,
                "clawloops.volumeId": req.volumeId,
                "clawloops.routeHost": req.routeHost,
                "clawloops.retentionPolicy": req.retentionPolicy,
                "clawloops.configVersion": req.renderedConfig.configVersion,
            }
            alias = f"rt-{req.runtimeId}"
            container = self._create_runtime_container(req, labels, alias)
            container.reload()
            if container.status != "running":
                raise RuntimeManagerError("RUNTIME_START_FAILED", "container is not running", 500)

            ip = container_ip(container)
            if not ip or not self._wait_ready(ip, 18789):
                raise RuntimeManagerError(
                    "RUNTIME_START_FAILED",
                    "failed to prepare config or start container",
                    500,
                )
            browser_url = self._browser_url_from_container(container)
            return ContainerStateResponse(
                runtimeId=req.runtimeId,
                observedState="running",
                internalEndpoint=self._internal_endpoint(req.runtimeId),
                browserUrl=browser_url,
                message="creating",
            )
        except RuntimeManagerError:
            raise
        except (APIError, OSError, ValueError) as exc:
            raise RuntimeManagerError(
                "RUNTIME_START_FAILED",
                "failed to prepare config or start container",
                500,
            ) from exc

    def stop(self, req: StopContainerRequest) -> ContainerStateResponse:
        try:
            container = self._get_single_container(req.runtimeId)
            if container is None or container.status in {"exited", "created"}:
                return ContainerStateResponse(
                    runtimeId=req.runtimeId,
                    observedState="stopped",
                    message="already stopped",
                )
            container.stop(timeout=10)
            return ContainerStateResponse(runtimeId=req.runtimeId, observedState="stopped", message="stopped")
        except RuntimeManagerError:
            raise
        except (APIError, NotFound) as exc:
            raise RuntimeManagerError("RUNTIME_STOP_FAILED", "failed to stop container", 500) from exc

    def delete(self, req: DeleteContainerRequest) -> ContainerStateResponse:
        try:
            container = self._get_single_container(req.runtimeId)
            if container is not None:
                container.remove(force=True)
            if req.retentionPolicy == "wipe_workspace" and req.compat is not None:
                roots = {Path(req.compat.openclawConfigDir), Path(req.compat.openclawWorkspaceDir)}
                dedup: list[Path] = []
                for p in roots:
                    if any(parent in p.parents for parent in dedup):
                        continue
                    dedup = [x for x in dedup if p not in x.parents]
                    dedup.append(p)
                for path in dedup:
                    if path.exists():
                        shutil.rmtree(path)
            return ContainerStateResponse(runtimeId=req.runtimeId, observedState="deleted", message="deleted")
        except RuntimeManagerError:
            raise
        except (APIError, OSError) as exc:
            raise RuntimeManagerError(
                "RUNTIME_DELETE_FAILED",
                "failed to delete container or cleanup directories",
                500,
            ) from exc

    def get_state(self, runtime_id: str) -> ContainerStateResponse:
        container = self._get_single_container(runtime_id)
        if container is None:
            return ContainerStateResponse(
                runtimeId=runtime_id,
                observedState="deleted",
                internalEndpoint=None,
                message="not found as container fact",
            )
        status_map = {
            "running": "running",
            "exited": "stopped",
            "created": "creating",
            "paused": "error",
            "restarting": "creating",
            "dead": "error",
        }
        observed = status_map.get(container.status, "error")
        return ContainerStateResponse(
            runtimeId=runtime_id,
            observedState=observed,  # type: ignore[arg-type]
            internalEndpoint=self._internal_endpoint(runtime_id) if observed != "deleted" else None,
            browserUrl=self._browser_url_from_container(container) if observed != "deleted" else None,
            message="ok",
        )
