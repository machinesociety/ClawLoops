import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import (
    get_runtime_binding_repository,
    get_sqlalchemy_user_repository,
    get_user_service,
)
from app.main import create_app
from app.repositories.user_repository import InMemoryUserRepository
from app.services.user_service import UserService


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    return TestClient(app)


class _InMemoryBindingRepo:
    def __init__(self) -> None:
        self._bindings: dict[str, "UserRuntimeBinding"] = {}

    def get_by_user_id(self, user_id: str):
        from app.domain.users import UserRuntimeBinding

        return self._bindings.get(user_id)

    def save(self, binding):
        self._bindings[binding.user_id] = binding


def _make_user_repo():
    return InMemoryUserRepository()


def _make_binding_repo():
    return _InMemoryBindingRepo()


def _make_user_service(user_repo, binding_repo):
    return UserService(
        user_repo=user_repo,
        binding_repo=binding_repo,
        default_image_ref="crewclaw-runtime-wrapper:openclaw-1.0.0",
        default_retention_policy="preserve_workspace",
    )


@pytest.fixture
def client_with_inmemory(app):
    """Fixture that overrides user/binding repos and UserService with in-memory implementations."""
    user_repo = _make_user_repo()
    binding_repo = _make_binding_repo()
    service = _make_user_service(user_repo, binding_repo)

    app.dependency_overrides[get_sqlalchemy_user_repository] = lambda: user_repo
    app.dependency_overrides[get_runtime_binding_repository] = lambda: binding_repo
    app.dependency_overrides[get_user_service] = lambda: service

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


