from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1 import admin as admin_api
from app.api.v1 import auth as auth_api
from app.api.v1 import credentials as credentials_api
from app.api.v1 import internal as internal_api
from app.api.v1 import models as models_api
from app.api.v1 import runtime as runtime_api
from app.api.v1 import usage as usage_api
from app.api.v1 import users as users_api
from app.api.v1 import workspace as workspace_api
from app.core.errors import AppError
from app.core.logging import setup_logging
from app.core.settings import get_settings


def create_app() -> FastAPI:
    """
    创建 CrewClaw 控制面 FastAPI 应用实例。
    """
    settings = get_settings()
    setup_logging(settings)

    app = FastAPI(
        title="CrewClaw Control Plane",
        version="0.1.0",
        description="CrewClaw 平台 MVP 控制面 API 服务。",
    )

    # 健康检查与根路径
    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {"service": "crewclaw-control-plane", "status": "ok"}

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict:
        # 后续可增加对数据库、下游服务的探活检查。
        return {"status": "healthy"}

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:  # type: ignore[override]
        # 统一 AppError 响应结构：至少包含 code 和 message。
        return JSONResponse(
            status_code=exc.spec.http_status,
            content={"code": exc.spec.code, "message": exc.spec.message},
        )

    # 挂载 v1 路由
    app.include_router(auth_api.router, prefix="/api/v1")
    app.include_router(users_api.router, prefix="/api/v1")
    app.include_router(runtime_api.router, prefix="/api/v1")
    app.include_router(models_api.router, prefix="/api/v1")
    app.include_router(credentials_api.router, prefix="/api/v1")
    app.include_router(usage_api.router, prefix="/api/v1")
    app.include_router(workspace_api.router, prefix="/api/v1")
    app.include_router(admin_api.router, prefix="/api/v1")
    app.include_router(internal_api.router)

    return app


app = create_app()

