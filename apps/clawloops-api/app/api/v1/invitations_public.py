from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.core.dependencies import get_invitation_service
from app.schemas.invitations import (
    InvitationPublicPreviewItem,
    InvitationPublicPreviewResponse,
    InvitationStartResponse,
    PendingInvitationSession,
)
from app.services.invitation_service import InvitationService


router = APIRouter(tags=["invitations-public"])

PENDING_INV_COOKIE = "clawloops_pending_invitation_id"


@router.get("/public/invitations/{token}", response_model=InvitationPublicPreviewResponse)
async def preview_invitation(
    token: str,
    svc: InvitationService = Depends(get_invitation_service),
) -> InvitationPublicPreviewResponse:
    inv = svc.get_public_preview(token)
    return InvitationPublicPreviewResponse(
        valid=True,
        invitation=InvitationPublicPreviewItem(
            targetEmail=inv.target_email,
            loginUsername=inv.login_username,
            workspaceId=inv.workspace_id,
            workspaceName=None,
            role=inv.role,
            status=inv.status.value,
            expiresAt=inv.expires_at,
        ),
    )


@router.post("/public/invitations/{token}/start", response_model=InvitationStartResponse)
async def start_invitation(
    token: str,
    response: Response,
    svc: InvitationService = Depends(get_invitation_service),
) -> InvitationStartResponse:
    inv = svc.start(token)

    ttl_seconds = 20 * 60
    response.set_cookie(
        key=PENDING_INV_COOKIE,
        value=inv.invitation_id,
        max_age=ttl_seconds,
        httponly=True,
        samesite="lax",
        path="/",
    )

    return InvitationStartResponse(
        status="accepted",
        pendingInvitationSession=PendingInvitationSession(ttlSeconds=ttl_seconds),
        redirectUrl=svc.build_authentik_redirect_url(inv),
    )

