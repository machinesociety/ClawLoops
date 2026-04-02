import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response

from app.core.dependencies import get_app_settings, get_invitation_repository, get_session_repository, get_sqlalchemy_user_repository
from app.core.errors import (
    InvitationAlreadyConsumedError,
    InvitationExpiredError,
    InvitationNotFoundError,
    InvitationPasswordInvalidError,
    InvitationRevokedError,
    InvitationUsernameMismatchError,
)
from app.core.password_policy import validate_password_policy
from app.core.passwords import hash_password_pbkdf2_sha256
from app.core.sessions import create_session
from app.core.settings import AppSettings
from app.domain.users import User, UserRole, UserStatus
from app.repositories.invitation_repository import InvitationRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import SessionAuthInfo, SessionUser
from app.schemas.invitations import (
    InvitationAcceptRequest,
    InvitationAcceptResult,
    InvitationAcceptWorkspaceBinding,
    InvitationPreviewItem,
    InvitationPreviewResponse,
)


router = APIRouter(tags=["public"])


def _set_session_cookie(resp: Response, settings: AppSettings, token: str) -> None:
    resp.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _resolve_invitation_record(repo: InvitationRepository, token: str):
    # Backward compatibility:
    # admin UI currently shares /invite/{invitation_id} links (e.g. inv_xxx),
    # while public endpoints historically expected raw token then hash lookup.
    # Accept both formats to avoid breaking existing invites.
    if token.startswith("inv_"):
        record = repo.get_by_invitation_id(token)
        if record is not None:
            return record
    return repo.get_by_token_hash(_hash_token(token))


def _to_session_user(user: User) -> SessionUser:
    return SessionUser(
        userId=user.user_id,
        subjectId=user.subject_id,
        username=user.username,
        tenantId=user.tenant_id,
        role=user.role.value,
        status=user.status.value,
        auth=SessionAuthInfo(provider="clawloops", method="local_password"),
        isAdmin=user.role == UserRole.ADMIN,
        isDisabled=user.is_disabled(),
        mustChangePassword=user.must_change_password,
        passwordChangeReason=user.password_change_reason,
    )


@router.get("/public/invitations/{token}", response_model=InvitationPreviewResponse)
async def preview_invitation(
    token: str,
    repo: InvitationRepository = Depends(get_invitation_repository),
) -> InvitationPreviewResponse:
    record = _resolve_invitation_record(repo, token)
    if record is None:
        raise InvitationNotFoundError()

    now = datetime.now(timezone.utc)
    if record.status == "revoked":
        raise InvitationRevokedError()
    if record.status == "consumed":
        raise InvitationAlreadyConsumedError()
    if record.expires_at.replace(tzinfo=timezone.utc) < now:
        raise InvitationExpiredError()

    return InvitationPreviewResponse(
        valid=True,
        invitation=InvitationPreviewItem(
            invitationId=record.invitation_id,
            targetEmail=record.target_email,
            loginUsername=record.login_username,
            workspaceId=record.workspace_id,
            workspaceName=record.workspace_name,
            role=record.role,
            status=record.status,
            expiresAt=record.expires_at.isoformat(),
        ),
    )


@router.post("/public/invitations/{token}/accept", response_model=InvitationAcceptResult)
async def accept_invitation(
    token: str,
    body: InvitationAcceptRequest,
    response: Response,
    settings: AppSettings = Depends(get_app_settings),
    repo: InvitationRepository = Depends(get_invitation_repository),
    user_repo: UserRepository = Depends(get_sqlalchemy_user_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
) -> InvitationAcceptResult:
    record = _resolve_invitation_record(repo, token)
    if record is None:
        raise InvitationNotFoundError()

    now = datetime.now(timezone.utc)
    if record.expires_at.replace(tzinfo=timezone.utc) < now:
        raise InvitationExpiredError()
    if record.status == "revoked":
        raise InvitationRevokedError()

    if body.password != body.passwordConfirm:
        raise InvitationPasswordInvalidError("Password confirmation does not match.")
    if record.login_username and body.username != record.login_username:
        raise InvitationUsernameMismatchError()
    if not validate_password_policy(username=body.username, password=body.password):
        raise InvitationPasswordInvalidError()

    # If already consumed, allow idempotent replay for the same user only.
    existing_user = user_repo.get_by_username(body.username)
    if record.status == "consumed":
        if (
            existing_user is None
            or record.consumed_by_user_id is None
            or existing_user.user_id != record.consumed_by_user_id
        ):
            raise InvitationAlreadyConsumedError()

        new_sess = create_session(ttl_seconds=settings.session_ttl_seconds)
        session_repo.create(
            user_id=existing_user.user_id,
            session_id_hash=new_sess.token_hash,
            issued_at=new_sess.issued_at,
            expires_at=new_sess.expires_at,
            created_by_ip=None,
            user_agent=None,
        )
        _set_session_cookie(response, settings, new_sess.token)
        return InvitationAcceptResult(
            accepted=True,
            replayed=True,
            redirectTo="/app",
            user=_to_session_user(existing_user),
            workspaceBinding=InvitationAcceptWorkspaceBinding(
                workspaceId=record.workspace_id,
                workspaceName=record.workspace_name,
                role=record.role,
            ),
        )

    # First consume path: create user if needed, set password, consume invitation
    if existing_user is None:
        user_id = f"u_{hashlib.sha256(f'{body.username}{now.isoformat()}'.encode('utf-8')).hexdigest()[:12]}"
        user = User(
            user_id=user_id,
            subject_id=f"clawloops:{user_id}",
            tenant_id="t_default",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
            username=body.username,
            password_hash=hash_password_pbkdf2_sha256(body.password),
            must_change_password=False,
            password_change_reason=None,
            created_at=now,
            last_login_at=now,
        )
        user_repo.save(user)
    else:
        # If user already has password_hash, treat as already onboarded and reject.
        if existing_user.password_hash:
            raise InvitationAlreadyConsumedError()
        existing_user.password_hash = hash_password_pbkdf2_sha256(body.password)
        existing_user.last_login_at = now
        user_repo.save(existing_user)
        user = existing_user

    updated, replayed = repo.consume_idempotent(
        invitation_id=record.invitation_id,
        consumed_by_user_id=user.user_id,
        now=now,
    )
    if updated.status == "consumed" and updated.consumed_by_user_id != user.user_id and not replayed:
        raise InvitationAlreadyConsumedError()

    new_sess = create_session(ttl_seconds=settings.session_ttl_seconds)
    session_repo.create(
        user_id=user.user_id,
        session_id_hash=new_sess.token_hash,
        issued_at=new_sess.issued_at,
        expires_at=new_sess.expires_at,
        created_by_ip=None,
        user_agent=None,
    )
    _set_session_cookie(response, settings, new_sess.token)

    return InvitationAcceptResult(
        accepted=True,
        replayed=False,
        redirectTo="/app",
        user=_to_session_user(user),
        workspaceBinding=InvitationAcceptWorkspaceBinding(
            workspaceId=record.workspace_id,
            workspaceName=record.workspace_name,
            role=record.role,
        ),
    )

