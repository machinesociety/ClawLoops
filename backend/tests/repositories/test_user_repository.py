from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.domain.users import DesiredState, ObservedState, RetentionPolicy, User, UserRuntimeBinding, UserRole, UserStatus
from app.models import user as _user_models  # noqa: F401 - ensure tables registered
from app.repositories.user_repository import SqlAlchemyUserRepository, SqlAlchemyUserRuntimeBindingRepository


def _setup_inmemory_db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def test_sqlalchemy_user_repository_crud():
    session = _setup_inmemory_db()
    repo = SqlAlchemyUserRepository(session)

    user = User(
        user_id="u_001",
        subject_id="authentik:001",
        tenant_id="t_default",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )

    repo.save(user)

    fetched = repo.get_by_id("u_001")
    assert fetched is not None
    assert fetched.subject_id == "authentik:001"

    fetched2 = repo.get_by_subject_id("authentik:001")
    assert fetched2 is not None
    assert fetched2.user_id == "u_001"


def test_sqlalchemy_user_runtime_binding_repository_crud_and_unique():
    session = _setup_inmemory_db()
    binding_repo = SqlAlchemyUserRuntimeBindingRepository(session)

    binding = UserRuntimeBinding(
        user_id="u_001",
        runtime_id="rt_001",
        volume_id="vol_001",
        image_ref="clawloops-runtime-wrapper:openclaw-1.0.0",
        desired_state=DesiredState.RUNNING,
        observed_state=ObservedState.RUNNING,
        retention_policy=RetentionPolicy.PRESERVE_WORKSPACE,
        browser_url=None,
        internal_endpoint=None,
        last_error=None,
    )

    binding_repo.save(binding)

    fetched = binding_repo.get_by_user_id("u_001")
    assert fetched is not None
    assert fetched.runtime_id == "rt_001"

    # 更新同一 user 的 binding，验证唯一约束语义
    binding2 = UserRuntimeBinding(
        user_id="u_001",
        runtime_id="rt_002",
        volume_id="vol_002",
        image_ref="clawloops-runtime-wrapper:openclaw-1.0.1",
        desired_state=DesiredState.STOPPED,
        observed_state=ObservedState.STOPPED,
        retention_policy=RetentionPolicy.PRESERVE_WORKSPACE,
        browser_url="https://u-001.clawloops.example.com",
        internal_endpoint="http://clawloops-u001:3000",
        last_error="none",
    )

    binding_repo.save(binding2)

    fetched2 = binding_repo.get_by_user_id("u_001")
    assert fetched2 is not None
    assert fetched2.runtime_id == "rt_002"
    assert fetched2.volume_id == "vol_002"
    assert fetched2.browser_url is not None

