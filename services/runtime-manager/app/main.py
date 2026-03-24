from __future__ import annotations

from fastapi import FastAPI

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

_runtime_states: dict[str, ObservedState] = {}


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
    _runtime_states[body.runtime_id] = ObservedState.CREATING
    return EnsureRunningResponse(
        runtime_id=body.runtime_id,
        observed_state=ObservedState.CREATING,
        internal_endpoint=f"http://rt-{body.runtime_id}:18789",
        message="creating",
    )


@app.post("/internal/runtime-manager/containers/stop", response_model=StopResponse)
async def stop_container(body: StopRequest) -> StopResponse:
    _runtime_states[body.runtime_id] = ObservedState.STOPPED
    return StopResponse(runtime_id=body.runtime_id, observed_state=ObservedState.STOPPED, message="stopped")


@app.post("/internal/runtime-manager/containers/delete", response_model=DeleteResponse)
async def delete_container(body: DeleteRequest) -> DeleteResponse:
    _ = body.retention_policy
    _runtime_states[body.runtime_id] = ObservedState.DELETED
    return DeleteResponse(runtime_id=body.runtime_id, observed_state=ObservedState.DELETED, message="deleted")


@app.get("/internal/runtime-manager/containers/{runtime_id}", response_model=RuntimeStatusResponse)
async def get_container_status(runtime_id: str) -> RuntimeStatusResponse:
    observed = _runtime_states.get(runtime_id, ObservedState.DELETED)
    return RuntimeStatusResponse(
        runtime_id=runtime_id,
        observed_state=observed,
        internal_endpoint=None if observed == ObservedState.DELETED else f"http://rt-{runtime_id}:18789",
        message=observed.value,
    )
