from app.domain.users import DesiredState, ObservedState, RetentionPolicy, User, UserRuntimeBinding, UserRole, UserStatus
from app.repositories.user_repository import InMemoryUserRepository, UserRuntimeBindingRepository
from app.services.user_service import UserService


class InMemoryBindingRepo(UserRuntimeBindingRepository):
    def __init__(self) -> None:
        self._bindings: dict[str, UserRuntimeBinding] = {}

    def get_by_user_id(self, user_id: str) -> UserRuntimeBinding | None:
        return self._bindings.get(user_id)

    def save(self, binding: UserRuntimeBinding) -> None:
        self._bindings[binding.user_id] = binding


def test_get_or_create_user_idempotent():
    user_repo = InMemoryUserRepository()
    binding_repo = InMemoryBindingRepo()
    service = UserService(
        user_repo=user_repo,
        binding_repo=binding_repo,
        default_image_ref="clawloops-runtime-wrapper:openclaw-1.0.0",
        default_retention_policy="preserve_workspace",
    )

    subject = "authentik:123"
    u1 = service.get_or_create_user(subject)
    u2 = service.get_or_create_user(subject)

    assert u1.user_id == u2.user_id
    assert u1.subject_id == subject
    assert u1.tenant_id == "t_default"
    assert u1.role == UserRole.USER
    assert u1.status == UserStatus.ACTIVE


def test_ensure_runtime_binding_first_and_idempotent():
    user_repo = InMemoryUserRepository()
    binding_repo = InMemoryBindingRepo()
    service = UserService(
        user_repo=user_repo,
        binding_repo=binding_repo,
        default_image_ref="clawloops-runtime-wrapper:openclaw-1.0.0",
        default_retention_policy="preserve_workspace",
    )

    user_id = "u_001"
    user_repo.save(
        User(
            user_id=user_id,
            subject_id="authentik:001",
            tenant_id="t_default",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
    )

    b1 = service.ensure_runtime_binding(user_id)
    assert b1.user_id == user_id
    assert b1.runtime_id.startswith("rt_")
    assert b1.volume_id.startswith("vol_")
    assert b1.image_ref == "clawloops-runtime-wrapper:openclaw-1.0.0"
    assert b1.desired_state == DesiredState.STOPPED
    assert b1.observed_state == ObservedState.STOPPED
    assert b1.retention_policy == RetentionPolicy.PRESERVE_WORKSPACE
    assert b1.browser_url is None
    assert b1.internal_endpoint is None

    b2 = service.ensure_runtime_binding(user_id)
    assert b2.runtime_id == b1.runtime_id
    assert b2.volume_id == b1.volume_id
