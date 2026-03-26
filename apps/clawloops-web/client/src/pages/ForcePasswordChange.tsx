/**
 * ForcePasswordChange Page - /force-password-change
 * Design: Crafted Dark - ClawLoops Platform
 *
 * v0.5 (轻量认证修订):
 * - Only accessible when mustChangePassword=true (seed admin first login)
 * - Three fields: currentPassword, newPassword, newPasswordConfirm
 * - Loads passwordPolicy from /auth/options for validation hints
 * - Error handling: CURRENT_PASSWORD_INCORRECT, PASSWORD_CHANGE_INVALID, UNAUTHENTICATED
 * - On success: redirects to /admin (or redirectTo from response)
 * - No skip option; only logout is available
 * - Does NOT render inside admin shell layer
 */

import { useEffect, useState } from 'react';
import { useLocation } from 'wouter';
import { authApi, PasswordPolicy, isAppError, getErrorCode } from '@/lib/api';
import { RequireForcePasswordChange } from '@/components/guards/RouteGuard';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Eye, EyeOff, Loader2, AlertCircle, Lock, ShieldAlert, LogOut } from 'lucide-react';

type PageState = 'idle' | 'submitting' | 'success';

interface FormErrors {
  currentPassword?: string;
  newPassword?: string;
  newPasswordConfirm?: string;
  general?: string;
}

function ForcePasswordChangeForm() {
  const [, navigate] = useLocation();
  const { user, logout, refresh } = useAuth();
  const [policy, setPolicy] = useState<PasswordPolicy | null>(null);
  const [pageState, setPageState] = useState<PageState>('idle');
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  // Load password policy
  useEffect(() => {
    authApi.options().then(opts => {
      if (opts.passwordPolicy) setPolicy(opts.passwordPolicy);
    }).catch(() => {
      // Use default policy hints if unavailable
    });
  }, []);

  const buildPolicyHints = (): string[] => {
    if (!policy) return [];
    const hints: string[] = [];
    if (policy.minLength) hints.push(`至少 ${policy.minLength} 个字符`);
    if (policy.maxLength) hints.push(`最多 ${policy.maxLength} 个字符`);
    if (policy.requireLetter) hints.push('包含字母');
    if (policy.requireNumber) hints.push('包含数字');
    if (policy.disallowUsernameAsPassword) hints.push('不能与用户名相同');
    return hints;
  };

  const validate = (): boolean => {
    const errors: FormErrors = {};
    if (!currentPassword) errors.currentPassword = '请输入当前密码';
    if (!newPassword) {
      errors.newPassword = '请输入新密码';
    } else if (policy?.minLength && newPassword.length < policy.minLength) {
      errors.newPassword = `密码至少需要 ${policy.minLength} 个字符`;
    }
    if (!newPasswordConfirm) {
      errors.newPasswordConfirm = '请再次输入新密码';
    } else if (newPassword && newPasswordConfirm !== newPassword) {
      errors.newPasswordConfirm = '两次输入的密码不一致';
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setPageState('submitting');
    setFormErrors({});

    try {
      const result = await authApi.changePassword({
        currentPassword,
        newPassword,
        newPasswordConfirm,
      });

      setPageState('success');

      // Critical: refresh session/access state so guards allow next page immediately.
      try {
        await refresh();
      } catch {
        // ignore; still navigate based on API response
      }

      // Navigate based on response
      if (result.redirectTo) {
        navigate(result.redirectTo);
      } else {
        navigate('/admin');
      }
    } catch (e) {
      setPageState('idle');
      const code = getErrorCode(e);

      if (code === 'CURRENT_PASSWORD_INCORRECT') {
        setFormErrors({ currentPassword: '当前密码错误，请重新输入' });
      } else if (code === 'PASSWORD_CHANGE_INVALID') {
        setFormErrors({ newPassword: '密码不符合要求，或新旧密码不能相同' });
      } else if (code === 'UNAUTHENTICATED' || (isAppError(e) && e.httpStatus === 401)) {
        navigate('/login');
      } else {
        setFormErrors({ general: '修改失败，请稍后重试' });
      }
    }
  };

  const policyHints = buildPolicyHints();
  const isBusy = pageState === 'submitting' || pageState === 'success';

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <div className="w-full max-w-md space-y-8">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/20 border border-primary/30 flex items-center justify-center">
            <span className="text-primary font-bold text-base" style={{ fontFamily: 'Space Grotesk' }}>CL</span>
          </div>
          <span className="text-foreground font-bold text-xl" style={{ fontFamily: 'Space Grotesk' }}>ClawLoops</span>
        </div>

        {/* Warning banner */}
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5 flex gap-4">
          <ShieldAlert className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="text-amber-400 font-semibold text-sm">需要修改初始密码</p>
            <p className="text-amber-400/70 text-xs leading-relaxed">
              当前使用的是系统默认初始密码，出于安全考虑，您必须先修改密码才能继续使用平台。
            </p>
          </div>
        </div>

        <div className="space-y-2">
          <h2 className="text-2xl font-bold text-foreground" style={{ fontFamily: 'Space Grotesk' }}>
            修改密码
          </h2>
          {user?.username && (
            <p className="text-muted-foreground text-sm">
              当前账号：<span className="text-foreground font-medium font-mono">{user.username}</span>
            </p>
          )}
        </div>

        {/* Error alert */}
        {formErrors.general && (
          <Alert variant="destructive" className="border-destructive/50 bg-destructive/10">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{formErrors.general}</AlertDescription>
          </Alert>
        )}

        {/* Password policy hints */}
        {policyHints.length > 0 && (
          <div className="rounded-lg border border-border/50 bg-muted/30 px-4 py-3">
            <p className="text-muted-foreground text-xs font-medium mb-1.5">密码要求：</p>
            <ul className="space-y-0.5">
              {policyHints.map(hint => (
                <li key={hint} className="text-muted-foreground/70 text-xs flex items-center gap-1.5">
                  <span className="w-1 h-1 rounded-full bg-muted-foreground/50 flex-shrink-0" />
                  {hint}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Current password */}
          <div className="space-y-2">
            <Label htmlFor="currentPassword" className="text-sm font-medium text-foreground">
              当前密码
            </Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
              <Input
                id="currentPassword"
                type={showCurrent ? 'text' : 'password'}
                autoComplete="current-password"
                placeholder="请输入当前密码"
                value={currentPassword}
                onChange={e => {
                  setCurrentPassword(e.target.value);
                  if (formErrors.currentPassword) setFormErrors(prev => ({ ...prev, currentPassword: undefined }));
                }}
                className={`pl-10 pr-10 bg-background/50 border-border/60 focus:border-primary/60 transition-colors ${
                  formErrors.currentPassword ? 'border-destructive' : ''
                }`}
                disabled={isBusy}
              />
              <button
                type="button"
                onClick={() => setShowCurrent(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                tabIndex={-1}
              >
                {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {formErrors.currentPassword && (
              <p className="text-destructive text-xs">{formErrors.currentPassword}</p>
            )}
          </div>

          {/* New password */}
          <div className="space-y-2">
            <Label htmlFor="newPassword" className="text-sm font-medium text-foreground">
              新密码
            </Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
              <Input
                id="newPassword"
                type={showNew ? 'text' : 'password'}
                autoComplete="new-password"
                placeholder="请输入新密码"
                value={newPassword}
                onChange={e => {
                  setNewPassword(e.target.value);
                  if (formErrors.newPassword) setFormErrors(prev => ({ ...prev, newPassword: undefined }));
                }}
                className={`pl-10 pr-10 bg-background/50 border-border/60 focus:border-primary/60 transition-colors ${
                  formErrors.newPassword ? 'border-destructive' : ''
                }`}
                disabled={isBusy}
              />
              <button
                type="button"
                onClick={() => setShowNew(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                tabIndex={-1}
              >
                {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {formErrors.newPassword && (
              <p className="text-destructive text-xs">{formErrors.newPassword}</p>
            )}
          </div>

          {/* Confirm new password */}
          <div className="space-y-2">
            <Label htmlFor="newPasswordConfirm" className="text-sm font-medium text-foreground">
              确认新密码
            </Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
              <Input
                id="newPasswordConfirm"
                type={showConfirm ? 'text' : 'password'}
                autoComplete="new-password"
                placeholder="请再次输入新密码"
                value={newPasswordConfirm}
                onChange={e => {
                  setNewPasswordConfirm(e.target.value);
                  if (formErrors.newPasswordConfirm) setFormErrors(prev => ({ ...prev, newPasswordConfirm: undefined }));
                }}
                className={`pl-10 pr-10 bg-background/50 border-border/60 focus:border-primary/60 transition-colors ${
                  formErrors.newPasswordConfirm ? 'border-destructive' : ''
                }`}
                disabled={isBusy}
              />
              <button
                type="button"
                onClick={() => setShowConfirm(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                tabIndex={-1}
              >
                {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {formErrors.newPasswordConfirm && (
              <p className="text-destructive text-xs">{formErrors.newPasswordConfirm}</p>
            )}
          </div>

          <Button
            type="submit"
            className="w-full font-semibold h-11"
            disabled={isBusy}
          >
            {pageState === 'submitting' ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                正在修改...
              </>
            ) : pageState === 'success' ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                跳转中...
              </>
            ) : (
              '更新密码并继续'
            )}
          </Button>
        </form>

        {/* Logout option */}
        <div className="pt-2 border-t border-border/50">
          <button
            type="button"
            onClick={logout}
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground text-sm transition-colors mx-auto"
            disabled={isBusy}
          >
            <LogOut className="w-4 h-4" />
            退出登录
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ForcePasswordChangePage() {
  return (
    <RequireForcePasswordChange>
      <ForcePasswordChangeForm />
    </RequireForcePasswordChange>
  );
}
