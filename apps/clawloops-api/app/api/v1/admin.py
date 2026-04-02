import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.dependencies import (
    get_db_session_dep,
    get_invitation_repository,
    get_runtime_service,
    get_user_service,
    require_active_user,
)
from app.core.errors import AccessDeniedError, InvitationNotFoundError, UserNotFoundError
from app.domain.users import UserStatus
from app.models.invitation import InvitationModel
from app.models.user import UserModel, UserRuntimeBindingModel
from app.repositories.invitation_repository import InvitationRepository
from app.repositories.model_repository import (
    ModelRepository,
    ProviderCredentialRepository,
    UsageRepository,
    get_inmemory_model_repository,
    get_inmemory_provider_credential_repository,
    get_inmemory_usage_repository,
)
from app.schemas.admin import (
    AdminUsageSummaryResponse,
    AdminUserDetailResponse,
    AdminUserListResponse,
    AdminUserListItem,
    AdminUserRuntimeResponse,
    UpdateUserStatusRequest,
)
from app.schemas.credentials import (
    CreateProviderCredentialRequest,
    ProviderCredentialItem,
    ProviderCredentialListResponse,
    VerifyProviderCredentialResponse,
)
from app.schemas.models import AdminModelItem, AdminModelListResponse, UpdateAdminModelRequest
from app.services.model_service import ModelService, ProviderCredentialService, UsageService
from app.services.runtime_service import RuntimeService
from app.services.user_service import UserService


router = APIRouter(tags=["admin"])


class AdminHomeSummary(BaseModel):
    totalUsers: int
    activeUsers: int
    disabledUsers: int
    pendingInvitations: int
    expiringInvitations24h: int
    runningRuntimes: int
    runtimeErrors: int


class AdminHomePendingInvitation(BaseModel):
    invitationId: str
    targetEmail: str
    loginUsername: str | None = None
    workspaceId: str
    role: str
    expiresAt: str
    status: str


class AdminHomeRuntimeAlert(BaseModel):
    userId: str
    runtimeId: str
    observedState: str
    lastError: str | None = None
    updatedAt: str | None = None


class AdminHomeResponse(BaseModel):
    summary: AdminHomeSummary
    attention: dict


class CreateAdminInvitationRequest(BaseModel):
    targetEmail: str
    loginUsername: str | None = None
    workspaceId: str
    role: str
    expiresInHours: int = 72


class AdminInvitationItem(BaseModel):
    invitationId: str
    targetEmail: str
    loginUsername: str | None = None
    workspaceId: str
    role: str
    status: str
    expiresAt: str
    consumedAt: str | None = None
    consumedByUserId: str | None = None
    lastError: str | None = None
    createdAt: str | None = None


def _to_admin_invitation_item(row: InvitationModel) -> AdminInvitationItem:
    return AdminInvitationItem(
        invitationId=row.invitation_id,
        targetEmail=row.target_email,
        loginUsername=row.login_username,
        workspaceId=row.workspace_id,
        role=row.role,
        status=row.status,
        expiresAt=row.expires_at.isoformat(),
        consumedAt=row.consumed_at.isoformat() if row.consumed_at else None,
        consumedByUserId=row.consumed_by_user_id,
        lastError=None,
        createdAt=None,
    )


def _require_admin(ctx: AuthContext = Depends(require_active_user)) -> AuthContext:
    if not ctx.isAdmin:
        raise AccessDeniedError()
    return ctx


def get_model_service(model_repo: ModelRepository = Depends(get_inmemory_model_repository)) -> ModelService:
    return ModelService(model_repo=model_repo)


def get_provider_credential_service(
    repo: ProviderCredentialRepository = Depends(get_inmemory_provider_credential_repository),
) -> ProviderCredentialService:
    return ProviderCredentialService(credential_repo=repo)


def get_usage_service(repo: UsageRepository = Depends(get_inmemory_usage_repository)) -> UsageService:
    return UsageService(usage_repo=repo)


@router.get("/admin/home", response_model=AdminHomeResponse)
async def get_admin_home(
    _: AuthContext = Depends(_require_admin),
    db: Session = Depends(get_db_session_dep),
) -> AdminHomeResponse:
    now = datetime.now(timezone.utc)
    in_24h = now + timedelta(hours=24)

    total_users = db.query(UserModel).count()
    active_users = db.query(UserModel).filter(UserModel.status == "ACTIVE").count()
    disabled_users = db.query(UserModel).filter(UserModel.status == "DISABLED").count()

    pending_invitations_q = db.query(InvitationModel).filter(InvitationModel.status == "pending")
    pending_invitations = pending_invitations_q.count()
    expiring_24h = (
        pending_invitations_q.filter(InvitationModel.expires_at <= in_24h.replace(tzinfo=None)).count()
    )

    running_runtimes = db.query(UserRuntimeBindingModel).filter(
        UserRuntimeBindingModel.observed_state == "RUNNING"
    ).count()
    runtime_errors = db.query(UserRuntimeBindingModel).filter(
        UserRuntimeBindingModel.observed_state == "ERROR"
    ).count()

    pending_rows = (
        pending_invitations_q.order_by(InvitationModel.expires_at.asc()).limit(5).all()
    )
    runtime_error_rows = (
        db.query(UserRuntimeBindingModel)
        .filter(UserRuntimeBindingModel.observed_state == "ERROR")
        .limit(5)
        .all()
    )

    return AdminHomeResponse(
        summary=AdminHomeSummary(
            totalUsers=total_users,
            activeUsers=active_users,
            disabledUsers=disabled_users,
            pendingInvitations=pending_invitations,
            expiringInvitations24h=expiring_24h,
            runningRuntimes=running_runtimes,
            runtimeErrors=runtime_errors,
        ),
        attention={
            "pendingInvitations": [
                AdminHomePendingInvitation(
                    invitationId=row.invitation_id,
                    targetEmail=row.target_email,
                    loginUsername=row.login_username,
                    workspaceId=row.workspace_id,
                    role=row.role,
                    expiresAt=row.expires_at.isoformat(),
                    status=row.status,
                )
                for row in pending_rows
            ],
            "runtimeAlerts": [
                AdminHomeRuntimeAlert(
                    userId=row.user_id,
                    runtimeId=row.runtime_id,
                    observedState=row.observed_state.value.lower(),
                    lastError=row.last_error,
                    updatedAt=None,
                )
                for row in runtime_error_rows
            ],
        },
    )


@router.get("/admin/users", response_model=AdminUserListResponse)
async def list_users(
    _: AuthContext = Depends(_require_admin),
    user_service: UserService = Depends(get_user_service),
) -> AdminUserListResponse:
    users = user_service.list_users()
    items: list[AdminUserListItem] = []
    for u in users:
        binding = user_service.get_runtime_binding(u.user_id)
        items.append(
            AdminUserListItem(
                userId=u.user_id,
                subjectId=u.subject_id,
                role=u.role.value,
                status=u.status.value,
                authMethod="local_password",
                runtimeObservedState=binding.observed_state.value if binding else None,
                lastLoginAt=u.last_login_at.isoformat() if u.last_login_at else None,
                username=u.username,
                email=None,
            )
        )
    return AdminUserListResponse(users=items)


@router.get("/admin/users/{user_id}", response_model=AdminUserDetailResponse)
async def get_admin_user_detail(
    user_id: str,
    _: AuthContext = Depends(_require_admin),
    user_service: UserService = Depends(get_user_service),
) -> AdminUserDetailResponse:
    user = user_service.get_user_by_id(user_id)
    if user is None:
        raise UserNotFoundError()

    binding = user_service.get_runtime_binding(user_id)
    return AdminUserDetailResponse(
        userId=user.user_id,
        subjectId=user.subject_id,
        tenantId=user.tenant_id,
        role=user.role.value,
        status=user.status.value,
        authMethod="local_password",
        runtimeObservedState=binding.observed_state.value if binding else None,
        lastLoginAt=user.last_login_at.isoformat() if user.last_login_at else None,
        username=user.username,
        email=None,
        createdAt=user.created_at.isoformat() if user.created_at else None,
    )


@router.patch("/admin/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    body: UpdateUserStatusRequest,
    _: AuthContext = Depends(_require_admin),
    user_service: UserService = Depends(get_user_service),
    runtime_service: RuntimeService = Depends(get_runtime_service),
) -> dict:
    new_status = UserStatus(body.status)
    user = user_service.set_user_status(user_id, new_status)

    if new_status == UserStatus.DISABLED:
        runtime_service.stop_runtime(user_id)

    return {"userId": user.user_id, "status": user.status.value}


@router.get("/admin/users/{user_id}/runtime", response_model=AdminUserRuntimeResponse)
async def get_admin_user_runtime(
    user_id: str,
    _: AuthContext = Depends(_require_admin),
    user_service: UserService = Depends(get_user_service),
) -> AdminUserRuntimeResponse:
    binding = user_service.get_runtime_binding(user_id)
    if binding is None:
        from app.core.errors import RuntimeNotFoundError

        raise RuntimeNotFoundError()

    return AdminUserRuntimeResponse(
        runtimeId=binding.runtime_id,
        volumeId=binding.volume_id,
        imageRef=binding.image_ref,
        desiredState=binding.desired_state.value,
        observedState=binding.observed_state.value,
        browserUrl=binding.browser_url,
        internalEndpoint=binding.internal_endpoint,
        retentionPolicy=binding.retention_policy.value,
        lastError=binding.last_error,
    )


@router.get("/admin/models", response_model=AdminModelListResponse)
async def list_admin_models(
    _: AuthContext = Depends(_require_admin),
    service: ModelService = Depends(get_model_service),
) -> AdminModelListResponse:
    return AdminModelListResponse(
        models=[
            AdminModelItem(
                modelId=model.model_id,
                name=model.name,
                provider=model.provider,
                source=model.source.value,
                enabled=model.enabled,
                defaultRoute=model.default_route,
                userVisible=model.user_visible,
                defaultProviderCredentialId=model.default_provider_credential_id,
            )
            for model in service.list_models_for_admin()
        ]
    )


@router.put("/admin/models/{model_id}", response_model=AdminModelItem)
async def update_admin_model(
    model_id: str,
    body: UpdateAdminModelRequest,
    _: AuthContext = Depends(_require_admin),
    service: ModelService = Depends(get_model_service),
) -> AdminModelItem:
    model = service.update_model(
        model_id,
        enabled=body.enabled,
        user_visible=body.userVisible,
        default_route=body.defaultRoute,
        default_provider_credential_id=body.defaultProviderCredentialId,
    )
    return AdminModelItem(
        modelId=model.model_id,
        name=model.name,
        provider=model.provider,
        source=model.source.value,
        enabled=model.enabled,
        defaultRoute=model.default_route,
        userVisible=model.user_visible,
        defaultProviderCredentialId=model.default_provider_credential_id,
    )


@router.get("/admin/provider-credentials", response_model=ProviderCredentialListResponse)
async def list_provider_credentials(
    _: AuthContext = Depends(_require_admin),
    service: ProviderCredentialService = Depends(get_provider_credential_service),
) -> ProviderCredentialListResponse:
    return ProviderCredentialListResponse(
        credentials=[
            ProviderCredentialItem(
                credentialId=item.credential_id,
                provider=item.provider,
                name=item.name,
                status=item.status.value,
                verified=item.status.value == "active",
                lastValidatedAt=item.last_validated_at,
            )
            for item in service.list_credentials()
        ]
    )


@router.post("/admin/provider-credentials", response_model=ProviderCredentialItem, status_code=201)
async def create_provider_credential(
    body: CreateProviderCredentialRequest,
    _: AuthContext = Depends(_require_admin),
    service: ProviderCredentialService = Depends(get_provider_credential_service),
) -> ProviderCredentialItem:
    item = service.create_credential(body.provider, body.name, body.secret)
    return ProviderCredentialItem(
        credentialId=item.credential_id,
        provider=item.provider,
        name=item.name,
        status=item.status.value,
        verified=item.status.value == "active",
        lastValidatedAt=item.last_validated_at,
    )


@router.post(
    "/admin/provider-credentials/{credential_id}/verify",
    response_model=VerifyProviderCredentialResponse,
)
async def verify_provider_credential(
    credential_id: str,
    _: AuthContext = Depends(_require_admin),
    service: ProviderCredentialService = Depends(get_provider_credential_service),
) -> VerifyProviderCredentialResponse:
    item = service.verify_credential(credential_id)
    return VerifyProviderCredentialResponse(
        verified=item.status.value == "active",
        status=item.status.value,
        lastValidatedAt=item.last_validated_at,
    )


@router.delete("/admin/provider-credentials/{credential_id}", status_code=204)
async def delete_provider_credential(
    credential_id: str,
    _: AuthContext = Depends(_require_admin),
    service: ProviderCredentialService = Depends(get_provider_credential_service),
) -> None:
    service.delete_credential(credential_id)
    return None


@router.get("/admin/usage/summary", response_model=AdminUsageSummaryResponse)
async def get_admin_usage_summary(
    _: AuthContext = Depends(_require_admin),
    service: UsageService = Depends(get_usage_service),
) -> AdminUsageSummaryResponse:
    summary = service.get_total_usage()
    return AdminUsageSummaryResponse(
        totalTokens=summary.total_tokens,
        usedTokens=summary.used_tokens,
    )


@router.get("/admin/invitations")
async def list_admin_invitations(
    _: AuthContext = Depends(_require_admin),
    db: Session = Depends(get_db_session_dep),
) -> dict:
    rows = db.query(InvitationModel).order_by(InvitationModel.expires_at.desc()).all()
    return {"invitations": [_to_admin_invitation_item(row) for row in rows]}


@router.get("/admin/invitations/{invitation_id}", response_model=AdminInvitationItem)
async def get_admin_invitation(
    invitation_id: str,
    _: AuthContext = Depends(_require_admin),
    db: Session = Depends(get_db_session_dep),
) -> AdminInvitationItem:
    row = (
        db.query(InvitationModel)
        .filter(InvitationModel.invitation_id == invitation_id)
        .one_or_none()
    )
    if row is None:
        raise InvitationNotFoundError()
    return _to_admin_invitation_item(row)


@router.post("/admin/invitations", response_model=AdminInvitationItem)
async def create_admin_invitation(
    body: CreateAdminInvitationRequest,
    _: AuthContext = Depends(_require_admin),
    db: Session = Depends(get_db_session_dep),
) -> AdminInvitationItem:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=body.expiresInHours)
    token = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    invitation_id = f"inv_{secrets.token_hex(8)}"
    target_email = body.targetEmail.strip() or f"{(body.loginUsername or 'user')}@noemail.local"
    row = InvitationModel(
        invitation_id=invitation_id,
        invite_token_hash=token_hash,
        target_email=target_email,
        login_username=body.loginUsername,
        workspace_id=body.workspaceId,
        workspace_name=body.workspaceId,
        role=body.role,
        status="pending",
        expires_at=expires_at.replace(tzinfo=None),
        consumed_by_user_id=None,
        consumed_at=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_admin_invitation_item(row)


@router.post("/admin/invitations/{invitation_id}/revoke")
async def revoke_admin_invitation(
    invitation_id: str,
    _: AuthContext = Depends(_require_admin),
    db: Session = Depends(get_db_session_dep),
) -> dict:
    row = (
        db.query(InvitationModel)
        .filter(InvitationModel.invitation_id == invitation_id)
        .one_or_none()
    )
    if row is None:
        raise InvitationNotFoundError()
    row.status = "revoked"
    db.commit()
    return {"ok": True}


@router.post("/admin/invitations/{invitation_id}/resend")
async def resend_admin_invitation(
    invitation_id: str,
    _: AuthContext = Depends(_require_admin),
    repo: InvitationRepository = Depends(get_invitation_repository),
) -> dict:
    # MVP: currently no outbound mail service wired.
    # Keep endpoint available for frontend interaction contract.
    _ = repo
    return {"ok": True, "invitationId": invitation_id}
