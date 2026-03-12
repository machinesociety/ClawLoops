from fastapi import Depends, Request

from app.core.auth import AuthContext, build_auth_context_from_request
from app.core.errors import UserDisabledError
from app.core.settings import AppSettings, get_settings
from app.repositories.user_repository import InMemoryUserRepository, UserRepository


_user_repo_singleton: UserRepository | None = None


def get_app_settings() -> AppSettings:
    return get_settings()


def get_user_repository() -> UserRepository:
    global _user_repo_singleton
    if _user_repo_singleton is None:
        _user_repo_singleton = InMemoryUserRepository()
    return _user_repo_singleton


def get_auth_context(
    request: Request,
    settings: AppSettings = Depends(get_app_settings),
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthContext:
    return build_auth_context_from_request(request, settings, user_repo)


def require_active_user(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if ctx.isDisabled:
        raise UserDisabledError()
    return ctx


