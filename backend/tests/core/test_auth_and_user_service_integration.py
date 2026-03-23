from fastapi import Request

from app.core import dependencies
from app.core.auth import build_auth_context_from_request
from app.core.settings import AppSettings
from app.domain.users import User, UserRole, UserStatus
from app.repositories.user_repository import InMemoryUserRepository
from app.services.user_service import UserService
from app.repositories.user_repository import UserRuntimeBindingRepository


class InMemoryBindingRepo(UserRuntimeBindingRepository):
    def __init__(self) -> None:
        self._bindings = {}

    def get_by_user_id(self, user_id: str):
        return self._bindings.get(user_id)

    def save(self, binding):
        self._bindings[binding.user_id] = binding


def test_auth_context_and_user_service_integration():
    user_repo = InMemoryUserRepository()
    binding_repo = InMemoryBindingRepo()
    service = UserService(
        user_repo=user_repo,
        binding_repo=binding_repo,
        default_image_ref="clawloops-runtime-wrapper:openclaw-1.0.0",
        default_retention_policy="preserve_workspace",
    )

    scope = {
        "type": "http",
        "headers": [(b"x-authentik-subject", b"authentik:int-user")],
    }
    request = Request(scope)
    settings = AppSettings()

    ctx = build_auth_context_from_request(request, settings, user_repo)
    assert ctx.subjectId == "authentik:int-user"
    user = service.get_or_create_user(ctx.subjectId)
    assert user.user_id == ctx.userId

    binding = service.ensure_runtime_binding(ctx.userId)
    assert binding.user_id == ctx.userId
    assert binding.runtime_id.startswith("rt_")

