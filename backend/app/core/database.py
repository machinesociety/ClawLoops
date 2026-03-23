from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.settings import AppSettings, get_settings


Base = declarative_base()


def _build_database_url(settings: AppSettings) -> str:
    """
    返回用于 SQLAlchemy 的数据库 URL。

    - 若未显式配置，则回退到本地 SQLite 文件，便于开发与测试。
    """

    if settings.database_url:
        return settings.database_url

    # 默认使用本地 SQLite 文件，避免额外依赖。
    return "sqlite:///./clawloops.db"


def create_engine_from_settings(settings: AppSettings | None = None):
    if settings is None:
        settings = get_settings()

    database_url = _build_database_url(settings)

    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        # SQLite 需要额外的线程选项。
        connect_args["check_same_thread"] = False

    engine = create_engine(database_url, connect_args=connect_args)
    return engine


engine = create_engine_from_settings()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI 依赖注入使用的 Session 工厂。
    """

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    在应用启动时调用，用于创建所有表。MVP 阶段直接使用 metadata.create_all。
    """

    # 延迟导入以避免循环依赖。
    from app.models import user as user_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

