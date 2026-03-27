from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.errors import RuntimeManagerError
from app.core.settings import get_settings
from app.schemas.contracts import (
    ContainerStateResponse,
    DeleteContainerRequest,
    EnsureContainerRequest,
    ErrorResponse,
    StopContainerRequest,
)
from app.services.runtime_executor import RuntimeExecutor

router = APIRouter(prefix="/internal/runtime-manager", tags=["runtime-manager"])


def _raise_http(err: RuntimeManagerError) -> None:
    raise HTTPException(status_code=err.status_code, detail={"code": err.code, "message": err.message})


@router.post(
    "/containers/ensure-running",
    response_model=ContainerStateResponse,
    responses={409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
def ensure_running(body: EnsureContainerRequest) -> ContainerStateResponse:
    executor = RuntimeExecutor(get_settings())
    try:
        return executor.ensure_running(body)
    except RuntimeManagerError as err:
        _raise_http(err)


@router.post(
    "/containers/stop",
    response_model=ContainerStateResponse,
    responses={409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def stop_container(body: StopContainerRequest) -> ContainerStateResponse:
    executor = RuntimeExecutor(get_settings())
    try:
        return executor.stop(body)
    except RuntimeManagerError as err:
        _raise_http(err)


@router.post(
    "/containers/delete",
    response_model=ContainerStateResponse,
    responses={409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def delete_container(body: DeleteContainerRequest) -> ContainerStateResponse:
    executor = RuntimeExecutor(get_settings())
    try:
        return executor.delete(body)
    except RuntimeManagerError as err:
        _raise_http(err)


@router.get(
    "/containers/{runtime_id}",
    response_model=ContainerStateResponse,
    responses={409: {"model": ErrorResponse}},
)
def get_container(runtime_id: str) -> ContainerStateResponse:
    executor = RuntimeExecutor(get_settings())
    try:
        return executor.get_state(runtime_id)
    except RuntimeManagerError as err:
        _raise_http(err)
