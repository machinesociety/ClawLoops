from abc import ABC, abstractmethod
from typing import Protocol

from sqlalchemy.orm import Session

from app.domain.users import (
    DesiredState,
    ObservedState,
    RetentionPolicy,
    User,
    UserRuntimeBinding,
    UserRole,
    UserStatus,
)
from app.models.user import UserModel, UserRuntimeBindingModel


class UserRepository(ABC):
    """
    User 持久化仓储接口。

    TODO:
    - 提供数据库实现（如基于 SQLAlchemy）。
    """

    @abstractmethod
    def get_by_id(self, user_id: str) -> User | None: ...

    @abstractmethod
    def get_by_subject_id(self, subject_id: str) -> User | None: ...

    @abstractmethod
    def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    def save(self, user: User) -> None: ...

    @abstractmethod
    def list_users(self) -> list[User]: ...


class UserRuntimeBindingRepository(Protocol):
    """
    UserRuntimeBinding 持久化接口。

    TODO:
    - 定义与实现完整的 CRUD 操作。
    """

    def get_by_user_id(self, user_id: str) -> UserRuntimeBinding | None: ...

    def save(self, binding: UserRuntimeBinding) -> None: ...


class InMemoryUserRepository(UserRepository):
    """
    内存版用户仓储，便于开发与单元测试。
    """

    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    def get_by_id(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    def get_by_subject_id(self, subject_id: str) -> User | None:
        return next((u for u in self._users.values() if u.subject_id == subject_id), None)

    def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._users.values() if u.username == username), None)

    def save(self, user: User) -> None:
        self._users[user.user_id] = user

    def list_users(self) -> list[User]:
        return list(self._users.values())


class SqlAlchemyUserRepository(UserRepository):
    """
    基于 SQLAlchemy 的 User 仓储实现。
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: str) -> User | None:
        row = (
            self._session.query(UserModel)
            .filter(UserModel.user_id == user_id)
            .one_or_none()
        )
        if row is None:
            return None
        return self._to_domain(row)

    def get_by_subject_id(self, subject_id: str) -> User | None:
        row = (
            self._session.query(UserModel)
            .filter(UserModel.subject_id == subject_id)
            .one_or_none()
        )
        if row is None:
            return None
        return self._to_domain(row)

    def get_by_username(self, username: str) -> User | None:
        row = (
            self._session.query(UserModel)
            .filter(UserModel.username == username)
            .one_or_none()
        )
        if row is None:
            return None
        return self._to_domain(row)

    def save(self, user: User) -> None:
        row = (
            self._session.query(UserModel)
            .filter(UserModel.user_id == user.user_id)
            .one_or_none()
        )
        if row is None:
            row = UserModel(
                user_id=user.user_id,
                subject_id=user.subject_id,
                username=user.username,
                password_hash=user.password_hash,
                tenant_id=user.tenant_id,
                role=user.role,
                status=user.status,
                must_change_password=user.must_change_password,
                password_change_reason=user.password_change_reason,
                created_at=user.created_at,
                last_login_at=user.last_login_at,
            )
            self._session.add(row)
        else:
            row.subject_id = user.subject_id
            row.username = user.username
            row.password_hash = user.password_hash
            row.tenant_id = user.tenant_id
            row.role = user.role
            row.status = user.status
            row.must_change_password = user.must_change_password
            row.password_change_reason = user.password_change_reason
            row.created_at = user.created_at
            row.last_login_at = user.last_login_at

        self._session.commit()

    def list_users(self) -> list[User]:
        rows = self._session.query(UserModel).all()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: UserModel) -> User:
        return User(
            user_id=row.user_id,
            subject_id=row.subject_id,
            username=row.username,
            password_hash=row.password_hash,
            tenant_id=row.tenant_id,
            role=row.role,
            status=row.status,
            must_change_password=row.must_change_password,
            password_change_reason=row.password_change_reason,
            created_at=row.created_at,
            last_login_at=row.last_login_at,
        )


class SqlAlchemyUserRuntimeBindingRepository(UserRuntimeBindingRepository):
    """
    基于 SQLAlchemy 的 UserRuntimeBinding 仓储实现。
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_user_id(self, user_id: str) -> UserRuntimeBinding | None:
        row = (
            self._session.query(UserRuntimeBindingModel)
            .filter(UserRuntimeBindingModel.user_id == user_id)
            .one_or_none()
        )
        if row is None:
            return None
        return self._to_domain(row)

    def save(self, binding: UserRuntimeBinding) -> None:
        row = (
            self._session.query(UserRuntimeBindingModel)
            .filter(UserRuntimeBindingModel.user_id == binding.user_id)
            .one_or_none()
        )
        if row is None:
            row = UserRuntimeBindingModel(
                user_id=binding.user_id,
                runtime_id=binding.runtime_id,
                volume_id=binding.volume_id,
                image_ref=binding.image_ref,
                desired_state=binding.desired_state,
                observed_state=binding.observed_state,
                browser_url=binding.browser_url,
                internal_endpoint=binding.internal_endpoint,
                retention_policy=binding.retention_policy,
                last_error=binding.last_error,
            )
            self._session.add(row)
        else:
            row.runtime_id = binding.runtime_id
            row.volume_id = binding.volume_id
            row.image_ref = binding.image_ref
            row.desired_state = binding.desired_state
            row.observed_state = binding.observed_state
            row.browser_url = binding.browser_url
            row.internal_endpoint = binding.internal_endpoint
            row.retention_policy = binding.retention_policy
            row.last_error = binding.last_error

        self._session.commit()

    @staticmethod
    def _to_domain(row: UserRuntimeBindingModel) -> UserRuntimeBinding:
        return UserRuntimeBinding(
            user_id=row.user_id,
            runtime_id=row.runtime_id,
            volume_id=row.volume_id,
            image_ref=row.image_ref,
            desired_state=row.desired_state,
            observed_state=row.observed_state,
            retention_policy=row.retention_policy,
            browser_url=row.browser_url,
            internal_endpoint=row.internal_endpoint,
            last_error=row.last_error,
        )

