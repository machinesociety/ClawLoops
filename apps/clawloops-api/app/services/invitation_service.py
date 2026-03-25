from __future__ import annotations

import hashlib
import secrets
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx

from app.core.errors import (
    InvitationAlreadyConsumedError,
    InvitationConfigError,
    InvitationEmailMismatchError,
    InvitationExpiredError,
    InvitationNotFoundError,
    InvitationRevokedError,
    InvitationError,
)
from app.core.settings import AppSettings
from app.domain.invitations import Invitation, InvitationStatus
from app.repositories.invitation_repository import InvitationRepository


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_hex(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class InvitationService:
    def __init__(self, repo: InvitationRepository, settings: AppSettings) -> None:
        self._repo = repo
        self._settings = settings

    def create_admin_invitation(
        self,
        *,
        target_email: str,
        login_username: str | None,
        workspace_id: str,
        role: str,
        expires_in_hours: int,
        created_by_user_id: str | None,
    ) -> Invitation:
        # MVP：为避免在平台侧保存明文 token，同时便于管理员随时复制链接，
        # 先把 platform token 固定为 invitationId（通过状态机保证一次性消费）。
        invitation_id = f"inv_{secrets.token_hex(8)}"
        token_hash = sha256_hex(invitation_id)

        now = _now_utc()
        inv = Invitation(
            invitation_id=invitation_id,
            invite_token_hash=token_hash,
            target_email=target_email.strip().lower(),
            login_username=login_username.strip() if login_username and login_username.strip() else None,
            workspace_id=workspace_id.strip(),
            role=role.strip(),
            status=InvitationStatus.PENDING,
            expires_at=_iso(now + timedelta(hours=max(1, int(expires_in_hours)))),
            consumed_at=None,
            consumed_by_user_id=None,
            authentik_invitation_ref=None,
            last_error=None,
            created_at=_iso(now),
            created_by_user_id=created_by_user_id,
        )
        self._repo.save(inv)
        return inv

    def list_invitations(self) -> list[Invitation]:
        return self._repo.list_all()

    def get_admin_invitation(self, invitation_id: str) -> Invitation:
        inv = self._repo.get_by_id(invitation_id)
        if inv is None:
            raise InvitationNotFoundError()
        return inv

    def revoke(self, invitation_id: str) -> Invitation:
        inv = self.get_admin_invitation(invitation_id)
        if inv.status == InvitationStatus.REVOKED:
            return inv
        if inv.status == InvitationStatus.CONSUMED:
            # 业务上可选择拒绝撤销已消费邀请，这里保持幂等：返回现状
            return inv
        updated = replace(inv, status=InvitationStatus.REVOKED)
        self._repo.save(updated)
        return updated

    def consume(self, *, invitation_id: str, user_id: str, email: str) -> Invitation:
        inv = self.get_admin_invitation(invitation_id)
        if inv.target_email.strip().lower() != email.strip().lower():
            raise InvitationEmailMismatchError()

        if inv.status == InvitationStatus.CONSUMED:
            return inv
        if inv.status == InvitationStatus.REVOKED:
            raise InvitationRevokedError()

        # expired 派生
        self._ensure_pending_valid(inv)

        now = _iso(_now_utc())
        updated = replace(
            inv,
            status=InvitationStatus.CONSUMED,
            consumed_at=now,
            consumed_by_user_id=user_id,
        )
        self._repo.save(updated)
        return updated

    def _ensure_pending_valid(self, inv: Invitation) -> None:
        if inv.status == InvitationStatus.REVOKED:
            raise InvitationRevokedError()
        if inv.status == InvitationStatus.CONSUMED:
            raise InvitationAlreadyConsumedError()
        # expired 派生
        try:
            expires = datetime.fromisoformat(inv.expires_at.replace("Z", "+00:00"))
        except ValueError:
            # 无法解析则视为已过期
            raise InvitationExpiredError()
        if _now_utc() > expires:
            raise InvitationExpiredError()

    def get_public_preview(self, token: str) -> Invitation:
        token_hash = sha256_hex(token)
        inv = self._repo.get_by_token_hash(token_hash)
        if inv is None:
            raise InvitationNotFoundError()
        self._ensure_pending_valid(inv)
        return inv

    def start(self, token: str) -> Invitation:
        inv = self.get_public_preview(token)
        return inv

    def build_authentik_redirect_url(self, inv: Invitation | None = None) -> str:
        """
        返回 Authentik enrollment flow 跳转 URL。

        - 必须显式绑定 AUTHENTIK_ENROLLMENT_FLOW_SLUG（缺失直接失败）
        - 生产期需要创建 Authentik invitation，换取真实 itoken；否则 Invitation Stage 会拒绝
        """
        base = (self._settings.authentik_public_url or "").rstrip("/")
        flow_slug = (self._settings.authentik_enrollment_flow_slug or "").strip()
        if not flow_slug:
            raise InvitationConfigError("Missing AUTHENTIK_ENROLLMENT_FLOW_SLUG.")

        itoken = self._create_authentik_invitation(inv)
        return f"{base}/if/flow/{quote(flow_slug)}/?itoken={quote(itoken)}"

    def _create_authentik_invitation(self, inv: Invitation | None) -> str:
        """
        通过 Authentik API 创建 Invitation，并返回 itoken（uuid/pk）。
        """
        api_base = (self._settings.authentik_api_base_url or "").rstrip("/") or "http://authentik-server:9000"
        token = (self._settings.authentik_api_token or "").strip()
        if not token:
            raise InvitationConfigError("Missing AUTHENTIK_API_TOKEN.")

        payload: dict[str, object] = {
            "name": f"clawloops-inv-{inv.invitation_id}" if inv is not None else f"clawloops-inv-{secrets.token_hex(8)}",
            "single_use": True,
        }
        if inv is not None:
            # 复用平台 invitation 的过期时间（Authentik 字段名为 expires）
            try:
                expires_dt = datetime.fromisoformat(inv.expires_at.replace("Z", "+00:00"))
                payload["expires"] = expires_dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
                    "+00:00", "Z"
                )
            except ValueError:
                # 平台过期字段不可解析时不传，交由 Authentik 默认策略
                pass

        url = f"{api_base}/api/v3/stages/invitation/invitations/"
        try:
            resp = httpx.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=5.0,
            )
        except httpx.HTTPError as e:
            raise InvitationError(f"Authentik API request failed: {e}") from e

        if resp.status_code not in (200, 201):
            raise InvitationError(f"Authentik API returned {resp.status_code}: {resp.text}")

        data = resp.json()
        itoken = data.get("pk") or data.get("id") or data.get("uuid")
        if not itoken or not isinstance(itoken, str):
            raise InvitationError("Authentik invitation response missing itoken.")
        return itoken

