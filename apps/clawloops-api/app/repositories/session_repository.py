from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.session import SessionModel


def _as_utc_aware(dt: datetime) -> datetime:
    """
    Normalize datetime for safe comparison.

    SQLite (and some SQLAlchemy configs) may return naive datetimes even if the
    app uses timezone-aware values. We treat naive values as UTC.
    """

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class SessionRecord:
    def __init__(
        self,
        *,
        user_id: str,
        session_id_hash: str,
        issued_at: datetime,
        expires_at: datetime,
        revoked_at: datetime | None,
        created_by_ip: str | None,
        user_agent: str | None,
    ) -> None:
        self.user_id = user_id
        self.session_id_hash = session_id_hash
        self.issued_at = issued_at
        self.expires_at = expires_at
        self.revoked_at = revoked_at
        self.created_by_ip = created_by_ip
        self.user_agent = user_agent


class SessionRepository(ABC):
    @abstractmethod
    def get_valid_by_hash(self, session_id_hash: str, now: datetime) -> SessionRecord | None: ...

    @abstractmethod
    def create(
        self,
        *,
        user_id: str,
        session_id_hash: str,
        issued_at: datetime,
        expires_at: datetime,
        created_by_ip: str | None,
        user_agent: str | None,
    ) -> None: ...

    @abstractmethod
    def revoke(self, session_id_hash: str, revoked_at: datetime) -> None: ...


class SqlAlchemySessionRepository(SessionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_valid_by_hash(self, session_id_hash: str, now: datetime) -> SessionRecord | None:
        now_utc = _as_utc_aware(now)
        row = (
            self._session.query(SessionModel)
            .filter(SessionModel.session_id_hash == session_id_hash)
            .one_or_none()
        )
        if row is None:
            return None
        if row.revoked_at is not None:
            return None
        if _as_utc_aware(row.expires_at) <= now_utc:
            return None
        return SessionRecord(
            user_id=row.user_id,
            session_id_hash=row.session_id_hash,
            issued_at=row.issued_at,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            created_by_ip=row.created_by_ip,
            user_agent=row.user_agent,
        )

    def create(
        self,
        *,
        user_id: str,
        session_id_hash: str,
        issued_at: datetime,
        expires_at: datetime,
        created_by_ip: str | None,
        user_agent: str | None,
    ) -> None:
        row = SessionModel(
            user_id=user_id,
            session_id_hash=session_id_hash,
            issued_at=issued_at,
            expires_at=expires_at,
            revoked_at=None,
            created_by_ip=created_by_ip,
            user_agent=user_agent,
        )
        self._session.add(row)
        self._session.commit()

    def revoke(self, session_id_hash: str, revoked_at: datetime) -> None:
        row = (
            self._session.query(SessionModel)
            .filter(SessionModel.session_id_hash == session_id_hash)
            .one_or_none()
        )
        if row is None:
            return
        row.revoked_at = revoked_at
        self._session.commit()


class InMemorySessionRepository(SessionRepository):
    def __init__(self) -> None:
        self._records: dict[str, SessionRecord] = {}

    def get_valid_by_hash(self, session_id_hash: str, now: datetime) -> SessionRecord | None:
        now_utc = _as_utc_aware(now)
        rec = self._records.get(session_id_hash)
        if rec is None:
            return None
        if rec.revoked_at is not None:
            return None
        if _as_utc_aware(rec.expires_at) <= now_utc:
            return None
        return rec

    def create(
        self,
        *,
        user_id: str,
        session_id_hash: str,
        issued_at: datetime,
        expires_at: datetime,
        created_by_ip: str | None,
        user_agent: str | None,
    ) -> None:
        self._records[session_id_hash] = SessionRecord(
            user_id=user_id,
            session_id_hash=session_id_hash,
            issued_at=issued_at,
            expires_at=expires_at,
            revoked_at=None,
            created_by_ip=created_by_ip,
            user_agent=user_agent,
        )

    def revoke(self, session_id_hash: str, revoked_at: datetime) -> None:
        rec = self._records.get(session_id_hash)
        if rec is None:
            return
        rec.revoked_at = revoked_at

