/**
 * Invitation Onboarding Page - /invite/:token
 * Design: Crafted Dark - ClawLoops Platform
 *
 * State machine per UI_状态模型.md §4.2 (v0.4):
 *   loadingPreview → previewValid
 *                  → previewAccountMismatchRisk  (logged-in user ≠ invite target)
 *                  → previewInvalid
 *   previewValid / previewAccountMismatchRisk → starting → redirectingToAuthentik
 *                                                        → startFailed
 *
 * Key v0.4 rules:
 * - loginUsername takes priority over targetEmail as display name
 * - proxy emails (*.noemail.local) must NOT be shown as primary copy
 * - account mismatch must be an actionable flow, not just a warning
 * - risk card must offer: 切换账号后继续接入 / 返回登录入口 / 联系管理员
 */

import { useEffect, useState } from 'react';
import { useParams, useLocation } from 'wouter';
import {
  invitationPublicApi,
  authApi,
  InvitationPreview,
  SessionUser,
  isAppError,
  AppError,
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRight,
  LogIn,
  RefreshCw,
  UserCheck,
  Building2,
  Shield,
  Clock,
  User,
  AlertCircle,
  ArrowLeft,
} from 'lucide-react';

// ─── State machine ────────────────────────────────────────────────────────────

type InvitePageState =
  | 'loadingPreview'
  | 'previewValid'
  | 'previewAccountMismatchRisk'
  | 'previewInvalid'
  | 'starting'
  | 'redirectingToAuthentik'
  | 'startFailed';

type InvalidCode =
  | 'INVITATION_NOT_FOUND'
  | 'INVITATION_ALREADY_CONSUMED'
  | 'INVITATION_REVOKED'
  | 'INVITATION_EXPIRED'
  | 'INVITATION_WORKSPACE_INVALID'
  | 'INVITATION_CONFIG_ERROR'
  | 'INVITATION_ERROR'
  | 'UNKNOWN';

const INVALID_MESSAGES: Record<InvalidCode, { title: string; desc: string; recoverable: boolean }> = {
  INVITATION_NOT_FOUND:         { title: '邀请链接不存在',   desc: '该邀请链接无效或已被删除，请向管理员确认链接是否正确。', recoverable: false },
  INVITATION_ALREADY_CONSUMED:  { title: '邀请链接已使用',   desc: '该邀请链接已被使用过，每个链接只能使用一次。',         recoverable: false },
  INVITATION_REVOKED:           { title: '邀请已撤销',       desc: '该邀请已被管理员撤销，请联系管理员重新发起邀请。',     recoverable: false },
  INVITATION_EXPIRED:           { title: '邀请已过期',       desc: '该邀请链接已超过有效期，请联系管理员重新发起邀请。',   recoverable: false },
  INVITATION_WORKSPACE_INVALID: { title: '工作区不可用',     desc: '邀请对应的工作区当前不可用，请联系管理员处理。',       recoverable: false },
  INVITATION_CONFIG_ERROR:      { title: '接入配置缺失',     desc: '平台未配置 enrollment flow（AUTHENTIK_ENROLLMENT_FLOW_SLUG）。请联系管理员完成配置后重试。', recoverable: false },
  INVITATION_ERROR:             { title: '系统暂时无法接入', desc: '接入流程遇到临时错误，您可以稍后重试。',               recoverable: true  },
  UNKNOWN:                      { title: '未知错误',         desc: '发生了未知错误，请稍后重试或联系管理员。',             recoverable: true  },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

type InvitationData = NonNullable<InvitationPreview['invitation']>;

/** True if email looks like a proxy/no-real-email address */
function isProxyEmail(email: string): boolean {
  return email.endsWith('.noemail.local') || email.endsWith('.placeholder.local');
}

/** Primary display name: loginUsername > non-proxy email > local part of proxy email */
function getPrimaryDisplayName(inv: InvitationData): string {
  if (inv.loginUsername) return inv.loginUsername;
  if (!isProxyEmail(inv.targetEmail)) return inv.targetEmail;
  return inv.targetEmail.split('@')[0];
}

/** Whether two account identifiers look different */
function accountsLookDifferent(currentUser: SessionUser, inv: InvitationData): boolean {
  const currentName = (currentUser as any).username ?? currentUser.userId ?? '';
  if (inv.loginUsername) {
    return inv.loginUsername.toLowerCase() !== currentName.toLowerCase();
  }
  const currentEmail = (currentUser as any).email ?? '';
  if (!currentEmail) return false;
  return inv.targetEmail.toLowerCase() !== currentEmail.toLowerCase();
}

function formatExpiry(expiresAt: string): string {
  const d = new Date(expiresAt);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  if (diffMs <= 0) return '已过期';
  const diffH = Math.floor(diffMs / 3600000);
  if (diffH < 24) return `${diffH} 小时后到期`;
  return `${Math.floor(diffH / 24)} 天后到期`;
}

const ROLE_LABELS: Record<string, string> = {
  workspace_member: '工作区成员',
  workspace_admin:  '工作区管理员',
  admin:            '系统管理员',
  user:             '普通用户',
};

// ─── Main component ───────────────────────────────────────────────────────────

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const [, navigate] = useLocation();

  const [pageState, setPageState] = useState<InvitePageState>('loadingPreview');
  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [currentUser, setCurrentUser] = useState<SessionUser | null>(null);
  const [invalidCode, setInvalidCode] = useState<InvalidCode>('UNKNOWN');
  const [startError, setStartError] = useState<string | null>(null);

  // ── Load preview + current session ──────────────────────────────────────────
  useEffect(() => {
    if (!token) {
      setInvalidCode('INVITATION_NOT_FOUND');
      setPageState('previewInvalid');
      return;
    }

    let cancelled = false;

    async function load() {
      try {
        const [previewResult, meResult] = await Promise.allSettled([
          invitationPublicApi.preview(token!),
          authApi.me(),
        ]);

        if (cancelled) return;

        // Resolve current user
        let user: SessionUser | null = null;
        if (meResult.status === 'fulfilled' && meResult.value.authenticated && meResult.value.user) {
          user = meResult.value.user;
          setCurrentUser(user);
        }

        // Resolve preview
        if (previewResult.status === 'rejected') {
          const err = previewResult.reason;
          if (isAppError(err)) {
            setInvalidCode((err.code as InvalidCode) ?? 'UNKNOWN');
          } else {
            setInvalidCode('UNKNOWN');
          }
          setPageState('previewInvalid');
          return;
        }

        const data = previewResult.value;
        setPreview(data);

        if (!data.valid || !data.invitation) {
          setInvalidCode('INVITATION_NOT_FOUND');
          setPageState('previewInvalid');
          return;
        }

        // Check status
        if (data.invitation.status === 'consumed') {
          setInvalidCode('INVITATION_ALREADY_CONSUMED');
          setPageState('previewInvalid');
          return;
        }
        if (data.invitation.status === 'revoked') {
          setInvalidCode('INVITATION_REVOKED');
          setPageState('previewInvalid');
          return;
        }

        // Check account mismatch
        if (user && accountsLookDifferent(user, data.invitation)) {
          setPageState('previewAccountMismatchRisk');
        } else {
          setPageState('previewValid');
        }
      } catch {
        if (!cancelled) {
          setInvalidCode('UNKNOWN');
          setPageState('previewInvalid');
        }
      }
    }

    load();
    return () => { cancelled = true; };
  }, [token]);

  // ── Start invitation ─────────────────────────────────────────────────────────
  const handleStart = async () => {
    if (!token) return;
    setPageState('starting');
    setStartError(null);
    try {
      const result = await invitationPublicApi.start(token);
      if (result.redirectUrl) {
        setPageState('redirectingToAuthentik');
        window.location.href = result.redirectUrl;
      } else {
        setStartError('接入服务未返回跳转地址，请稍后重试。');
        setPageState('startFailed');
      }
    } catch (e) {
      if (isAppError(e)) {
        const code = e.code as InvalidCode;
        const info = INVALID_MESSAGES[code];
        if (info && !info.recoverable) {
          setInvalidCode(code);
          setPageState('previewInvalid');
        } else {
          setStartError(e.message);
          setPageState('startFailed');
        }
      } else {
        setStartError('网络错误，请检查连接后重试。');
        setPageState('startFailed');
      }
    }
  };

  const inv = preview?.invitation;

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Brand header */}
        <div className="flex items-center gap-2.5 mb-8">
          <div className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center">
            <span className="text-primary font-bold text-sm" style={{ fontFamily: 'Space Grotesk' }}>CL</span>
          </div>
          <span className="font-semibold text-foreground" style={{ fontFamily: 'Space Grotesk' }}>ClawLoops</span>
        </div>

        {/* ── Loading ── */}
        {pageState === 'loadingPreview' && (
          <div className="rounded-2xl border border-border bg-card p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-4" />
            <p className="text-muted-foreground text-sm">正在验证邀请链接...</p>
          </div>
        )}

        {/* ── Invalid / expired / revoked ── */}
        {pageState === 'previewInvalid' && (
          <InvalidCard code={invalidCode} onBack={() => navigate('/login')} />
        )}

        {/* ── Account mismatch risk ── */}
        {pageState === 'previewAccountMismatchRisk' && inv && currentUser && (
          <MismatchRiskCard
            invitation={inv}
            currentUser={currentUser}
            onSwitchAndContinue={() => navigate(`/login?next=/invite/${token}`)}
            onBackToLogin={() => navigate('/login')}
            onIgnoreAndContinue={() => setPageState('previewValid')}
          />
        )}

        {/* ── Valid preview ── */}
        {pageState === 'previewValid' && inv && (
          <ValidPreviewCard
            invitation={inv}
            currentUser={currentUser}
            onContinue={handleStart}
          />
        )}

        {/* ── Starting ── */}
        {pageState === 'starting' && (
          <div className="rounded-2xl border border-border bg-card p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-4" />
            <p className="font-medium text-foreground mb-1">正在发起接入...</p>
            <p className="text-muted-foreground text-sm">即将跳转到身份验证页面</p>
          </div>
        )}

        {/* ── Redirecting ── */}
        {pageState === 'redirectingToAuthentik' && (
          <div className="rounded-2xl border border-border bg-card p-8 text-center">
            <CheckCircle2 className="w-8 h-8 text-green-400 mx-auto mb-4" />
            <p className="font-medium text-foreground mb-1">接入已发起</p>
            <p className="text-muted-foreground text-sm">正在跳转到身份验证页面...</p>
          </div>
        )}

        {/* ── Start failed (retryable) ── */}
        {pageState === 'startFailed' && (
          <div className="rounded-2xl border border-red-500/20 bg-card p-8">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
                <XCircle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <p className="font-medium text-foreground">接入发起失败</p>
                <p className="text-xs text-muted-foreground">可以稍后重试</p>
              </div>
            </div>
            {startError && (
              <p className="text-sm text-red-400/80 mb-4 px-1">{startError}</p>
            )}
            <div className="space-y-2">
              <Button className="w-full gap-2" onClick={handleStart}>
                <RefreshCw className="w-4 h-4" />
                重试
              </Button>
              <Button variant="outline" className="w-full gap-2" onClick={() => navigate('/login')}>
                <ArrowLeft className="w-4 h-4" />
                返回登录入口
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function InvalidCard({ code, onBack }: { code: InvalidCode; onBack: () => void }) {
  const info = INVALID_MESSAGES[code] ?? INVALID_MESSAGES.UNKNOWN;
  return (
    <div className="rounded-2xl border border-border bg-card p-8">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-full bg-destructive/10 flex items-center justify-center">
          <XCircle className="w-5 h-5 text-destructive" />
        </div>
        <div>
          <p className="font-semibold text-foreground">{info.title}</p>
          <p className="text-xs text-muted-foreground">邀请链接无法使用</p>
        </div>
      </div>
      <p className="text-sm text-muted-foreground mb-6 leading-relaxed">{info.desc}</p>
      <div className="space-y-2">
        <Button variant="outline" className="w-full gap-2" onClick={onBack}>
          <ArrowLeft className="w-4 h-4" />
          返回登录入口
        </Button>
        <p className="text-xs text-muted-foreground text-center pt-1">
          如有疑问，请联系系统管理员
        </p>
      </div>
    </div>
  );
}

function ValidPreviewCard({
  invitation,
  currentUser,
  onContinue,
}: {
  invitation: InvitationData;
  currentUser: SessionUser | null;
  onContinue: () => void;
}) {
  const displayName = getPrimaryDisplayName(invitation);
  const isProxy = isProxyEmail(invitation.targetEmail);
  const expiryText = formatExpiry(invitation.expiresAt);
  const roleLabel = ROLE_LABELS[invitation.role] ?? invitation.role;

  return (
    <div className="rounded-2xl border border-border bg-card overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-border/50">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center">
            <UserCheck className="w-5 h-5 text-primary" />
          </div>
          <div>
            <p className="font-semibold text-foreground">您收到了一份工作区邀请</p>
            <p className="text-xs text-muted-foreground">确认信息后继续接入</p>
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="px-6 py-4 space-y-3">
        {/* Recommended login account – primary info */}
        <div className="rounded-xl bg-primary/5 border border-primary/15 p-3.5">
          <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1.5">
            <User className="w-3 h-3" />
            推荐登录账号
          </p>
          <p className="font-semibold text-foreground text-base">{displayName}</p>
          {isProxy && (
            <p className="text-xs text-muted-foreground/70 mt-0.5">
              请使用此用户名登录，无需邮箱地址
            </p>
          )}
        </div>

        <div className="flex items-center gap-3 py-2">
          <Building2 className="w-4 h-4 text-muted-foreground flex-shrink-0" />
          <div>
            <p className="text-xs text-muted-foreground">目标工作区</p>
            <p className="text-sm font-medium text-foreground">{invitation.workspaceName || invitation.workspaceId}</p>
          </div>
        </div>

        <div className="flex items-center gap-3 py-2">
          <Shield className="w-4 h-4 text-muted-foreground flex-shrink-0" />
          <div>
            <p className="text-xs text-muted-foreground">邀请角色</p>
            <p className="text-sm font-medium text-foreground">{roleLabel}</p>
          </div>
        </div>

        <div className="flex items-center gap-3 py-2">
          <Clock className="w-4 h-4 text-muted-foreground flex-shrink-0" />
          <div>
            <p className="text-xs text-muted-foreground">有效期</p>
            <p className="text-sm font-medium text-foreground">{expiryText}</p>
          </div>
        </div>

        {/* Current logged-in user hint */}
        {currentUser && (
          <div className="rounded-lg bg-muted/30 border border-border px-3 py-2.5">
            <p className="text-xs text-muted-foreground">
              当前已登录账号：
              <span className="text-foreground font-medium ml-1">
                {(currentUser as any).username ?? currentUser.userId}
              </span>
            </p>
          </div>
        )}
      </div>

      {/* CTA */}
      <div className="px-6 pb-6 pt-2">
        <Button className="w-full gap-2 h-11" onClick={onContinue}>
          继续接入
          <ArrowRight className="w-4 h-4" />
        </Button>
        <p className="text-xs text-muted-foreground text-center mt-3">
          点击继续即表示您同意加入该工作区
        </p>
      </div>
    </div>
  );
}

function MismatchRiskCard({
  invitation,
  currentUser,
  onSwitchAndContinue,
  onBackToLogin,
  onIgnoreAndContinue,
}: {
  invitation: InvitationData;
  currentUser: SessionUser;
  onSwitchAndContinue: () => void;
  onBackToLogin: () => void;
  onIgnoreAndContinue: () => void;
}) {
  const inviteDisplayName = getPrimaryDisplayName(invitation);
  const currentDisplayName = (currentUser as any).username ?? currentUser.userId;

  return (
    <div className="rounded-2xl border border-amber-500/30 bg-card overflow-hidden">
      {/* Warning header */}
      <div className="px-6 pt-6 pb-4 bg-amber-500/5 border-b border-amber-500/20">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-amber-500/15 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <p className="font-semibold text-foreground">账号可能不匹配</p>
            <p className="text-xs text-amber-400/80">请确认您使用的是正确账号</p>
          </div>
        </div>
      </div>

      {/* Account comparison */}
      <div className="px-6 py-4 space-y-3">
        <p className="text-sm text-muted-foreground leading-relaxed">
          您当前登录的账号与此邀请的目标账号看起来不一致，请确认后再继续接入。
        </p>

        <div className="rounded-xl border border-border bg-muted/20 p-3.5">
          <p className="text-xs text-muted-foreground mb-1.5 flex items-center gap-1.5">
            <User className="w-3 h-3" />
            当前登录账号
          </p>
          <p className="font-semibold text-foreground">{currentDisplayName}</p>
        </div>

        <div className="flex items-center justify-center gap-2 text-muted-foreground/40">
          <AlertCircle className="w-3.5 h-3.5" />
          <span className="text-xs">邀请目标账号</span>
          <AlertCircle className="w-3.5 h-3.5" />
        </div>

        <div className="rounded-xl border border-primary/20 bg-primary/5 p-3.5">
          <p className="text-xs text-muted-foreground mb-1.5 flex items-center gap-1.5">
            <UserCheck className="w-3 h-3" />
            推荐登录账号（邀请目标）
          </p>
          <p className="font-semibold text-foreground">{inviteDisplayName}</p>
          {isProxyEmail(invitation.targetEmail) && (
            <p className="text-xs text-muted-foreground/70 mt-0.5">
              请使用此用户名登录，无需邮箱地址
            </p>
          )}
        </div>
      </div>

      {/* Actions – per v0.4: 切换账号 / 返回登录 / 联系管理员 */}
      <div className="px-6 pb-6 pt-2 space-y-2">
        <Button className="w-full gap-2 h-11" onClick={onSwitchAndContinue}>
          <LogIn className="w-4 h-4" />
          切换账号后继续接入
        </Button>

        <Button variant="outline" className="w-full gap-2" onClick={onBackToLogin}>
          <ArrowLeft className="w-4 h-4" />
          返回登录入口
        </Button>

        <div className="pt-1 text-center">
          <button
            className="text-xs text-muted-foreground hover:text-foreground transition-colors underline underline-offset-2"
            onClick={() => alert('请联系系统管理员处理账号问题。')}
          >
            联系管理员
          </button>
        </div>

        {/* Escape hatch */}
        <div className="pt-2 border-t border-border/50">
          <button
            className="w-full text-xs text-muted-foreground/40 hover:text-muted-foreground transition-colors py-1"
            onClick={onIgnoreAndContinue}
          >
            确认是同一账号，仍继续接入 →
          </button>
        </div>
      </div>
    </div>
  );
}
