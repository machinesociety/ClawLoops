from __future__ import annotations

from app.domain.users import (
    DesiredState,
    ObservedState,
    RetentionPolicy,
    User,
    UserRuntimeBinding,
    UserRole,
    UserStatus,
)
from app.repositories.user_repository import UserRepository, UserRuntimeBindingRepository


class UserService:
    """
    用户与 UserRuntimeBinding 相关服务。
    """

    def __init__(
        self,
        user_repo: UserRepository,
        binding_repo: UserRuntimeBindingRepository,
        default_image_ref: str,
        default_retention_policy: str,
    ) -> None:
        self._user_repo = user_repo
        self._binding_repo = binding_repo
        self._default_image_ref = default_image_ref
        self._default_retention_policy = RetentionPolicy(default_retention_policy)

    def get_or_create_user(self, subject_id: str) -> User:
        """
        以 subjectId 幂等创建用户，tenantId=t_default，role=user，status=active。
        """

        user = self._user_repo.get_by_subject_id(subject_id)
        if user is not None:
            return user

        user_id = f"u_{abs(hash(subject_id))}"
        user = User(
            user_id=user_id,
            subject_id=subject_id,
            tenant_id="t_default",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
        self._user_repo.save(user)
        return user

    def get_user_by_id(self, user_id: str) -> User | None:
        """
        根据 user_id 获取用户。
        """

        return self._user_repo.get_by_id(user_id)

    def list_users(self) -> list[User]:
        return self._user_repo.list_users()

    def set_user_status(self, user_id: str, status: UserStatus) -> User:
        """
        更新用户状态（例如 active/disabled），并持久化。
        """

        user = self._user_repo.get_by_id(user_id)
        if user is None:
            from app.core.errors import UserNotFoundError

            raise UserNotFoundError()

        user.status = status
        self._user_repo.save(user)
        return user

    def get_runtime_binding(self, user_id: str) -> UserRuntimeBinding | None:
        return self._binding_repo.get_by_user_id(user_id)

    def ensure_runtime_binding(self, user_id: str) -> UserRuntimeBinding:
        """
        首次 runtime 启动前，幂等创建 UserRuntimeBinding。
        """

        existing = self._binding_repo.get_by_user_id(user_id)
        if existing is not None:
            return existing

        runtime_id = f"rt_{user_id}"
        volume_id = f"vol_{user_id}"

        binding = UserRuntimeBinding(
            user_id=user_id,
            runtime_id=runtime_id,
            volume_id=volume_id,
            image_ref=self._default_image_ref,
            desired_state=DesiredState.STOPPED,
            observed_state=ObservedState.STOPPED,
            retention_policy=self._default_retention_policy,
            browser_url=None,
            internal_endpoint=None,
            last_error=None,
        )
        self._binding_repo.save(binding)
        return binding

    def upsert_runtime_binding(
        self,
        user_id: str,
        runtime_id: str,
        volume_id: str,
        image_ref: str,
        desired_state: DesiredState,
        observed_state: ObservedState,
        retention_policy: RetentionPolicy,
        browser_url: str | None = None,
        internal_endpoint: str | None = None,
        last_error: str | None = None,
    ) -> UserRuntimeBinding:
        binding = UserRuntimeBinding(
            user_id=user_id,
            runtime_id=runtime_id,
            volume_id=volume_id,
            image_ref=image_ref,
            desired_state=desired_state,
            observed_state=observed_state,
            retention_policy=retention_policy,
            browser_url=browser_url,
            internal_endpoint=internal_endpoint,
            last_error=last_error,
        )
        self._binding_repo.save(binding)
        return binding

    def update_runtime_binding_state(
        self,
        user_id: str,
        desired_state: DesiredState,
        observed_state: ObservedState,
        browser_url: str | None = None,
        internal_endpoint: str | None = None,
        last_error: str | None = None,
    ) -> UserRuntimeBinding | None:
        binding = self._binding_repo.get_by_user_id(user_id)
        if binding is None:
            return None
        binding.desired_state = desired_state
        binding.observed_state = observed_state
        binding.browser_url = browser_url
        binding.internal_endpoint = internal_endpoint
        binding.last_error = last_error
        self._binding_repo.save(binding)
        return binding
