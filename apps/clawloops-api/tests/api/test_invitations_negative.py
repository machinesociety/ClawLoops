from datetime import datetime, timedelta, timezone

from fastapi import status

from app.core.dependencies import get_invitation_repository
from app.repositories.invitation_repository import InvitationRecord, InvitationRepository


class _InMemoryInvitationRepository(InvitationRepository):
    def __init__(self) -> None:
        self._by_id: dict[str, InvitationRecord] = {}
        self._by_hash: dict[str, InvitationRecord] = {}

    def seed(self, record: InvitationRecord) -> None:
        self._by_id[record.invitation_id] = record
        self._by_hash[record.invite_token_hash] = record

    def get_by_token_hash(self, token_hash: str) -> InvitationRecord | None:
        return self._by_hash.get(token_hash)

    def get_by_invitation_id(self, invitation_id: str) -> InvitationRecord | None:
        return self._by_id.get(invitation_id)

    def consume_idempotent(
        self,
        *,
        invitation_id: str,
        consumed_by_user_id: str,
        now: datetime,
    ) -> tuple[InvitationRecord, bool]:
        record = self._by_id.get(invitation_id)
        if record is None:
            raise ValueError("invitation not found")
        if record.status == "consumed":
            return record, record.consumed_by_user_id == consumed_by_user_id
        if record.status == "revoked":
            return record, False
        record.status = "consumed"
        record.consumed_by_user_id = consumed_by_user_id
        record.consumed_at = now
        return record, False


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_pending_record(
    *,
    invitation_id: str,
    expires_at: datetime,
    status_value: str = "pending",
    login_username: str | None = None,
    consumed_by_user_id: str | None = None,
) -> InvitationRecord:
    return InvitationRecord(
        invitation_id=invitation_id,
        invite_token_hash=f"hash_{invitation_id}",
        target_email="user@example.com",
        login_username=login_username,
        workspace_id="ws_001",
        workspace_name="Workspace",
        role="user",
        status=status_value,
        expires_at=expires_at,
        consumed_by_user_id=consumed_by_user_id,
        consumed_at=None,
    )


def test_invitation_token_not_found_accept_returns_404(client_with_inmemory):
    client = client_with_inmemory
    repo = _InMemoryInvitationRepository()
    client.app.dependency_overrides[get_invitation_repository] = lambda: repo
    try:
        resp = client.post(
            "/api/v1/public/invitations/inv_missing/accept",
            json={"username": "alice", "password": "Abcdefg1", "passwordConfirm": "Abcdefg1"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.json()["code"] == "INVITATION_NOT_FOUND"
    finally:
        client.app.dependency_overrides.pop(get_invitation_repository, None)


def test_invitation_expired_accept_returns_410(client_with_inmemory):
    client = client_with_inmemory
    repo = _InMemoryInvitationRepository()
    record = _make_pending_record(
        invitation_id="inv_expired",
        expires_at=_now_naive() - timedelta(days=1),
    )
    repo.seed(record)
    client.app.dependency_overrides[get_invitation_repository] = lambda: repo
    try:
        resp = client.post(
            "/api/v1/public/invitations/inv_expired/accept",
            json={"username": "alice", "password": "Abcdefg1", "passwordConfirm": "Abcdefg1"},
        )
        assert resp.status_code == status.HTTP_410_GONE
        assert resp.json()["code"] == "INVITATION_EXPIRED"
    finally:
        client.app.dependency_overrides.pop(get_invitation_repository, None)


def test_invitation_revoked_accept_returns_409(client_with_inmemory):
    client = client_with_inmemory
    repo = _InMemoryInvitationRepository()
    record = _make_pending_record(
        invitation_id="inv_revoked",
        expires_at=_now_naive() + timedelta(days=1),
        status_value="revoked",
    )
    repo.seed(record)
    client.app.dependency_overrides[get_invitation_repository] = lambda: repo
    try:
        resp = client.post(
            "/api/v1/public/invitations/inv_revoked/accept",
            json={"username": "alice", "password": "Abcdefg1", "passwordConfirm": "Abcdefg1"},
        )
        assert resp.status_code == status.HTTP_409_CONFLICT
        assert resp.json()["code"] == "INVITATION_REVOKED"
    finally:
        client.app.dependency_overrides.pop(get_invitation_repository, None)


def test_invitation_consumed_replay_by_different_user_returns_409(client_with_inmemory):
    client = client_with_inmemory
    repo = _InMemoryInvitationRepository()
    record = _make_pending_record(
        invitation_id="inv_consumed",
        expires_at=_now_naive() + timedelta(days=1),
        status_value="consumed",
        consumed_by_user_id="u_existing",
    )
    repo.seed(record)
    client.app.dependency_overrides[get_invitation_repository] = lambda: repo
    try:
        resp = client.post(
            "/api/v1/public/invitations/inv_consumed/accept",
            json={"username": "otheruser", "password": "Abcdefg1", "passwordConfirm": "Abcdefg1"},
        )
        assert resp.status_code == status.HTTP_409_CONFLICT
        assert resp.json()["code"] == "INVITATION_ALREADY_CONSUMED"
    finally:
        client.app.dependency_overrides.pop(get_invitation_repository, None)


def test_invitation_password_mismatch_returns_422(client_with_inmemory):
    client = client_with_inmemory
    repo = _InMemoryInvitationRepository()
    record = _make_pending_record(
        invitation_id="inv_pwd_mismatch",
        expires_at=_now_naive() + timedelta(days=1),
    )
    repo.seed(record)
    client.app.dependency_overrides[get_invitation_repository] = lambda: repo
    try:
        resp = client.post(
            "/api/v1/public/invitations/inv_pwd_mismatch/accept",
            json={"username": "alice", "password": "Abcdefg1", "passwordConfirm": "Xbcdefg1"},
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert resp.json()["code"] == "INVITATION_PASSWORD_INVALID"
    finally:
        client.app.dependency_overrides.pop(get_invitation_repository, None)


def test_invitation_username_mismatch_returns_422(client_with_inmemory):
    client = client_with_inmemory
    repo = _InMemoryInvitationRepository()
    record = _make_pending_record(
        invitation_id="inv_username_mismatch",
        expires_at=_now_naive() + timedelta(days=1),
        login_username="expected_user",
    )
    repo.seed(record)
    client.app.dependency_overrides[get_invitation_repository] = lambda: repo
    try:
        resp = client.post(
            "/api/v1/public/invitations/inv_username_mismatch/accept",
            json={"username": "other_user", "password": "Abcdefg1", "passwordConfirm": "Abcdefg1"},
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert resp.json()["code"] == "INVITATION_USERNAME_MISMATCH"
    finally:
        client.app.dependency_overrides.pop(get_invitation_repository, None)
