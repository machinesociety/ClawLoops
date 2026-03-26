/**
 * Login Page - /login
 * Design: Crafted Dark - ClawLoops Platform
 *
 * v0.5 (轻量认证修订):
 * - Inline username/password form → POST /api/v1/auth/login
 * - No Authentik redirect, no external IAM
 * - Error handling: INVALID_CREDENTIALS, USER_DISABLED, PASSWORD_CHANGE_REQUIRED, SESSION_ERROR
 * - Redirect: /force-password-change | /admin | /app
 * - Helper text: "请优先使用管理员提供的用户名登录"
 * - Loads passwordPolicy from /auth/options for hints
 */

import { useEffect, useState } from 'react';
import { useLocation } from 'wouter';
import { authApi, AuthOptionsResponse, isAppError, getErrorCode } from '@/lib/api';
import { RedirectIfAuthenticated } from '@/components/guards/RouteGuard';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Eye, EyeOff, Loader2, AlertCircle, Lock, User, Shield, Zap } from 'lucide-react';

type LoginState = 'idle' | 'submitting' | 'success';

interface FormErrors {
  username?: string;
  password?: string;
  general?: string;
}

function LoginForm() {
  const [, navigate] = useLocation();
  const { refresh } = useAuth();
  const [options, setOptions] = useState<AuthOptionsResponse | null>(null);
  const [loginState, setLoginState] = useState<LoginState>('idle');
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Load auth options for label and passwordPolicy
  useEffect(() => {
    authApi.options().then(setOptions).catch(() => {
      setOptions({
        provider: 'local',
        methods: [{ type: 'local_password', label: '用户名优先登录' }],
      });
    });
  }, []);

  const validate = (): boolean => {
    const errors: FormErrors = {};
    if (!username.trim()) errors.username = '请输入用户名';
    if (!password) errors.password = '请输入密码';
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setLoginState('submitting');
    setFormErrors({});

    try {
      const result = await authApi.login({ username: username.trim(), password });
      setLoginState('success');

      // Critical: AuthProvider boot state doesn't auto-refresh after login.
      // Without this, guards may still treat user as unauthenticated until full page reload.
      try {
        await refresh();
      } catch {
        // ignore; still try to navigate based on login result
      }

      // Navigate based on server response
      if (result.redirectTo === '/force-password-change' || result.mustChangePassword) {
        navigate('/force-password-change');
      } else if (result.redirectTo === '/admin') {
        navigate('/admin');
      } else if (result.redirectTo === '/app') {
        navigate('/app');
      } else {
        // Default: check role from user object
        const isAdmin = result.user?.isAdmin ?? result.user?.role === 'admin';
        navigate(isAdmin ? '/admin' : '/app');
      }
    } catch (e) {
      setLoginState('idle');
      const code = getErrorCode(e);

      if (code === 'INVALID_CREDENTIALS') {
        setFormErrors({ general: '用户名或密码错误，请重新输入' });
      } else if (code === 'USER_DISABLED') {
        setFormErrors({ general: '账号已被禁用，请联系管理员' });
      } else if (code === 'PASSWORD_CHANGE_REQUIRED') {
        navigate('/force-password-change');
      } else if (code === 'SESSION_ERROR') {
        setFormErrors({ general: '系统繁忙，请稍后重试' });
      } else if (isAppError(e) && e.httpStatus === 401) {
        setFormErrors({ general: '用户名或密码错误，请重新输入' });
      } else {
        setFormErrors({ general: '登录失败，请稍后重试' });
      }
    }
  };

  const localMethod = options?.methods?.find(m => m.type === 'local_password');
  const buttonLabel = localMethod?.label ?? '用户名优先登录';
  const isBusy = loginState === 'submitting' || loginState === 'success';

  return (
    <div className="min-h-screen bg-background flex">
      {/* Left panel - brand */}
      <div
        className="hidden lg:flex lg:w-1/2 relative flex-col justify-between p-12 overflow-hidden"
        style={{
          background: 'linear-gradient(135deg, oklch(0.18 0.04 260) 0%, oklch(0.12 0.06 280) 50%, oklch(0.10 0.03 260) 100%)',
        }}
      >
        {/* Background image */}
        <div className="absolute inset-0">
          <img
            src="https://d2xsxph8kpxj0f.cloudfront.net/310519663268444302/6zuH3qxGrch8vwpDVc4ZMU/clawloops-hero-bg-oDsU6vAAJLGfYqXm2WAN6e.webp"
            alt=""
            className="w-full h-full object-cover opacity-40"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/30 to-black/70" />
        </div>
        {/* Grid overlay */}
        <div
          className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: `linear-gradient(oklch(0.6 0.1 260 / 0.5) 1px, transparent 1px),
                              linear-gradient(90deg, oklch(0.6 0.1 260 / 0.5) 1px, transparent 1px)`,
            backgroundSize: '48px 48px',
          }}
        />

        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/30 border border-primary/40 flex items-center justify-center backdrop-blur-sm">
              <span className="text-primary font-bold text-base" style={{ fontFamily: 'Space Grotesk' }}>CL</span>
            </div>
            <span className="text-white font-bold text-xl" style={{ fontFamily: 'Space Grotesk' }}>ClawLoops</span>
          </div>
        </div>

        <div className="relative z-10 space-y-6">
          <div>
            <h1 className="text-4xl font-bold text-white leading-tight" style={{ fontFamily: 'Space Grotesk' }}>
              AI 工作区
              <br />
              <span className="text-primary">管理平台</span>
            </h1>
            <p className="mt-4 text-white/60 text-base leading-relaxed">
              统一管理用户、模型与 Runtime，
              <br />
              为团队提供安全可控的 AI 工作环境。
            </p>
          </div>

          <div className="space-y-3">
            {[
              { icon: Shield, title: '企业级安全', desc: '邀请制接入，session 级隔离' },
              { icon: Zap, title: '弹性 Runtime', desc: '按需启停，资源高效利用' },
              { icon: Lock, title: '精细权限控制', desc: 'workspace 级模型策略管理' },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Icon className="w-4 h-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">{title}</p>
                  <p className="text-xs text-white/50">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative z-10">
          <p className="text-white/30 text-xs">ClawLoops Platform · 内部使用</p>
        </div>
      </div>

      {/* Right panel - login form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md space-y-8">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-9 h-9 rounded-xl bg-primary/20 border border-primary/30 flex items-center justify-center">
              <span className="text-primary font-bold text-sm" style={{ fontFamily: 'Space Grotesk' }}>CL</span>
            </div>
            <span className="text-foreground font-bold text-lg" style={{ fontFamily: 'Space Grotesk' }}>ClawLoops</span>
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-foreground" style={{ fontFamily: 'Space Grotesk' }}>
              欢迎回来
            </h2>
            <p className="text-muted-foreground text-sm">
              请使用管理员提供的账号登录
            </p>
          </div>

          {/* Helper text */}
          <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-4 py-3">
            <p className="text-amber-400/90 text-xs leading-relaxed">
              <span className="font-medium">提示：</span>
              请优先使用管理员提供的用户名登录。如未收到账号信息，请联系您的管理员。
            </p>
          </div>

          {/* Error alert */}
          {formErrors.general && (
            <Alert variant="destructive" className="border-destructive/50 bg-destructive/10">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{formErrors.general}</AlertDescription>
            </Alert>
          )}

          {/* Login form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-sm font-medium text-foreground">
                用户名
              </Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                <Input
                  id="username"
                  type="text"
                  autoComplete="username"
                  placeholder="请输入用户名"
                  value={username}
                  onChange={e => {
                    setUsername(e.target.value);
                    if (formErrors.username) setFormErrors(prev => ({ ...prev, username: undefined }));
                    if (formErrors.general) setFormErrors(prev => ({ ...prev, general: undefined }));
                  }}
                  className={`pl-10 bg-background/50 border-border/60 focus:border-primary/60 transition-colors ${
                    formErrors.username ? 'border-destructive' : ''
                  }`}
                  disabled={isBusy}
                />
              </div>
              {formErrors.username && (
                <p className="text-destructive text-xs">{formErrors.username}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium text-foreground">
                密码
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="请输入密码"
                  value={password}
                  onChange={e => {
                    setPassword(e.target.value);
                    if (formErrors.password) setFormErrors(prev => ({ ...prev, password: undefined }));
                    if (formErrors.general) setFormErrors(prev => ({ ...prev, general: undefined }));
                  }}
                  className={`pl-10 pr-10 bg-background/50 border-border/60 focus:border-primary/60 transition-colors ${
                    formErrors.password ? 'border-destructive' : ''
                  }`}
                  disabled={isBusy}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {formErrors.password && (
                <p className="text-destructive text-xs">{formErrors.password}</p>
              )}
            </div>

            <Button
              type="submit"
              className="w-full font-semibold h-11"
              disabled={isBusy}
            >
              {loginState === 'submitting' ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  登录中...
                </>
              ) : loginState === 'success' ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  跳转中...
                </>
              ) : (
                buttonLabel
              )}
            </Button>
          </form>

          <p className="text-center text-muted-foreground/50 text-xs">
            首次使用？请联系系统管理员获取邀请链接
          </p>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <RedirectIfAuthenticated>
      <LoginForm />
    </RedirectIfAuthenticated>
  );
}
