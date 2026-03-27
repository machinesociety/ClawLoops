from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, build_auth_context_from_request
from app.core.database import get_db_session, init_db
from app.core.errors import PasswordChangeRequiredError, UnauthenticatedError, UserDisabledError
from app.core.settings import AppSettings, get_settings
from app.infra.runtime_manager_client import RuntimeManagerClient
from app.repositories.session_repository import SqlAlchemySessionRepository, SessionRepository
from app.repositories.invitation_repository import InvitationRepository, SqlAlchemyInvitationRepository
from app.repositories.user_repository import (
    InMemoryUserRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserRuntimeBindingRepository,
    UserRepository,
    UserRuntimeBindingRepository,
)
from app.services.runtime_config_renderer import RuntimeConfigRenderer
from app.services.runtime_service import (
    InMemoryRuntimeTaskRepository,
    ModelConfigServiceAdapter,
    RuntimeManagerPortAdapter,
    RuntimeService,
    UserRuntimeBindingServiceAdapter,
)
from app.services.user_service import UserService


_user_repo_singleton: UserRepository | None = None
_runtime_task_repo_singleton: InMemoryRuntimeTaskRepository | None = None


def get_app_settings() -> AppSettings:
    return get_settings()


def get_user_repository() -> UserRepository:
    """
    默认返回基于 SQLAlchemy 的 UserRepository。

    测试中可以通过覆盖依赖或直接修改 _user_repo_singleton 来替换实现。
    """

    global _user_repo_singleton
    if _user_repo_singleton is not None:
        return _user_repo_singleton

    # 默认使用内存实现（主要用于早期阶段和某些测试场景）。
    return InMemoryUserRepository()


def get_db_session_dep() -> Session:
    """
    提供给 FastAPI 的 DB Session 依赖封装，便于在测试中覆盖。
    """

    # 确保表已创建。
    init_db()
    yield from get_db_session()


def get_runtime_binding_repository(
    db: Session = Depends(get_db_session_dep),
) -> UserRuntimeBindingRepository:
    return SqlAlchemyUserRuntimeBindingRepository(db)


def get_sqlalchemy_user_repository(
    db: Session = Depends(get_db_session_dep),
) -> UserRepository:
    return SqlAlchemyUserRepository(db)


def get_session_repository(
    db: Session = Depends(get_db_session_dep),
) -> SessionRepository:
    return SqlAlchemySessionRepository(db)


def get_invitation_repository(
    db: Session = Depends(get_db_session_dep),
) -> InvitationRepository:
    return SqlAlchemyInvitationRepository(db)


def get_auth_context(
    request: Request,
    settings: AppSettings = Depends(get_app_settings),
    user_repo: UserRepository = Depends(get_sqlalchemy_user_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
) -> AuthContext:
    return build_auth_context_from_request(request, settings, user_repo, session_repo)


def try_get_auth_context(
    request: Request,
    settings: AppSettings = Depends(get_app_settings),
    user_repo: UserRepository = Depends(get_sqlalchemy_user_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
) -> AuthContext | None:
    try:
        return build_auth_context_from_request(request, settings, user_repo, session_repo)
    except UnauthenticatedError:
        return None


def require_active_user(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if ctx.isDisabled:
        raise UserDisabledError()
    if ctx.mustChangePassword:
        raise PasswordChangeRequiredError()
    return ctx


def get_user_service(
    user_repo: UserRepository = Depends(get_sqlalchemy_user_repository),
    binding_repo: UserRuntimeBindingRepository = Depends(get_runtime_binding_repository),
    settings: AppSettings = Depends(get_app_settings),
) -> UserService:
    return UserService(
        user_repo=user_repo,
        binding_repo=binding_repo,
        default_image_ref="clawloops-runtime-wrapper:openclaw-1.0.0",
        default_retention_policy="preserve_workspace",
    )


def get_runtime_task_repository() -> InMemoryRuntimeTaskRepository:
    global _runtime_task_repo_singleton
    if _runtime_task_repo_singleton is None:
        _runtime_task_repo_singleton = InMemoryRuntimeTaskRepository()
    return _runtime_task_repo_singleton


def get_runtime_service(
    user_service: UserService = Depends(get_user_service),
    settings: AppSettings = Depends(get_app_settings),
    task_repo: InMemoryRuntimeTaskRepository = Depends(get_runtime_task_repository),
) -> RuntimeService:
    """
    组装 RuntimeService 所需依赖。
    """

    # 绑定服务适配到 Pydantic UserRuntimeBinding 视图
    from app.schemas.internal import ModelConfigResponse
    from app.schemas.runtime import RuntimeBindingSnapshot as BindingSchema

    def ensure_binding_schema(user_id: str) -> BindingSchema:
        binding = user_service.ensure_runtime_binding(user_id)
        return BindingSchema(
            runtimeId=binding.runtime_id,
            volumeId=binding.volume_id,
            imageRef=binding.image_ref,
            desiredState=binding.desired_state.value,  # type: ignore[arg-type]
            observedState=binding.observed_state.value,  # type: ignore[arg-type]
            browserUrl=binding.browser_url,
            internalEndpoint=binding.internal_endpoint,
            retentionPolicy=binding.retention_policy.value,  # type: ignore[arg-type]
            lastError=binding.last_error,
        )

    def patch_binding_state_schema(
        user_id: str,
        desired_state: str,
        observed_state: str,
        browser_url: str | None,
        internal_endpoint: str | None,
        last_error: str | None,
    ) -> BindingSchema | None:
        from app.domain.users import DesiredState as DomainDesired, ObservedState as DomainObserved

        updated = user_service.update_runtime_binding_state(
            user_id=user_id,
            desired_state=DomainDesired(desired_state),
            observed_state=DomainObserved(observed_state),
            browser_url=browser_url,
            internal_endpoint=internal_endpoint,
            last_error=last_error,
        )
        if updated is None:
            return None
        return BindingSchema(
            runtimeId=updated.runtime_id,
            volumeId=updated.volume_id,
            imageRef=updated.image_ref,
            desiredState=updated.desired_state.value,  # type: ignore[arg-type]
            observedState=updated.observed_state.value,  # type: ignore[arg-type]
            browserUrl=updated.browser_url,
            internalEndpoint=updated.internal_endpoint,
            retentionPolicy=updated.retention_policy.value,  # type: ignore[arg-type]
            lastError=updated.last_error,
        )

    def get_model_config(user_id: str) -> ModelConfigResponse:
        _ = user_id
        model_base_url = settings.model_gateway_base_url or "http://litellm:4000"
        model_ids = settings.get_model_gateway_default_models()
        return ModelConfigResponse(
            baseUrl=model_base_url,
            models=model_ids,
            gatewayAccessTokenRef="token_ref_001",
            configRenderVersion="v1",
        )

    binding_port = UserRuntimeBindingServiceAdapter(
        ensure_binding_fn=ensure_binding_schema,
        patch_state_fn=patch_binding_state_schema,
    )
    model_config_port = ModelConfigServiceAdapter(get_model_config_fn=get_model_config)

    base_url = settings.runtime_manager_base_url or "http://runtime-manager:18080"
    runtime_manager_client = RuntimeManagerClient(base_url=base_url)
    runtime_manager_port = RuntimeManagerPortAdapter(runtime_manager_client)

    renderer = RuntimeConfigRenderer(litellm_api_key=settings.litellm_api_key)

    return RuntimeService(
        binding_service=binding_port,
        model_config_service=model_config_port,
        runtime_manager=runtime_manager_port,
        task_repo=task_repo,
        config_renderer=renderer,
        route_host_suffix=settings.route_host_suffix,
    )


