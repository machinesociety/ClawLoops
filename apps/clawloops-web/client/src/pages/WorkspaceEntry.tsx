/**
 * WorkspaceEntry Page - /workspace-entry
 * Design: Crafted Dark - ClawLoops Platform
 *
 * State machine per UI_状态模型.md §4.4 (v0.4):
 *   loadingEntry → readyToRedirect   (ready=true → immediate redirect)
 *               → runtimeNotReady   (ready=false, runtimeId exists → staged progress + poll)
 *               → runtimeMissing    (ready=false, no runtimeId → guide back to /app)
 *               → noWorkspace       (hasWorkspace=false)
 *               → entryFailed       (error)
 *               → timedOut          (180s exceeded)
 *
 * Polling strategy per 页面调用流程_BFF编排.md §7.3 (v0.4):
 *   - First 60s: every 2s
 *   - After 60s: every 3s
 *   - Max 180s total, then manual refresh
 *
 * Staged progress (4 steps):
 *   1. 已接入 Workspace
 *   2. 正在创建运行环境
 *   3. 正在启动服务
 *   4. 正在验证工作区入口
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, Link } from 'wouter';
import { workspaceApi, WorkspaceEntry, isAppError } from '@/lib/api';
import { RequireAuth } from '@/components/guards/RouteGuard';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { MonoText } from '@/components/shared/PageComponents';
import {
  Loader2,
  ExternalLink,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  ArrowLeft,
  AlertTriangle,
  XCircle,
  ShieldCheck,
  Layers,
  Zap,
  PlugZap,
} from 'lucide-react';

// ─── State machine ────────────────────────────────────────────────────────────

type WorkspaceEntryState =
  | 'loadingEntry'
  | 'readyToRedirect'
  | 'runtimeNotReady'
  | 'runtimeMissing'
  | 'noWorkspace'
  | 'entryFailed'
  | 'timedOut';

// ─── Staged progress ──────────────────────────────────────────────────────────

interface ProgressStep {
  id: number;
  label: string;
  subLabel: string;
  icon: React.ComponentType<{ className?: string }>;
}

const PROGRESS_STEPS: ProgressStep[] = [
  { id: 1, label: '已接入 Workspace',     subLabel: '身份验证完成，成员资格已确认',   icon: ShieldCheck },
  { id: 2, label: '正在创建运行环境',      subLabel: '分配计算资源，初始化容器',         icon: Layers      },
  { id: 3, label: '正在启动服务',          subLabel: '加载 AI 工具链，配置工作区',       icon: Zap         },
  { id: 4, label: '正在验证工作区入口',    subLabel: '检查网络可达性，准备访问地址',     icon: PlugZap     },
];

// ─── Main component ───────────────────────────────────────────────────────────

function WorkspaceEntryContent() {
  const [, navigate] = useLocation();
  const [pageState, setPageState] = useState<WorkspaceEntryState>('loadingEntry');
  const [entry, setEntry] = useState<WorkspaceEntry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [progressStep, setProgressStep] = useState(1);

  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startTimeRef = useRef<number>(0);

  const MAX_POLL_MS = 180_000;   // 180 s total
  const FAST_THRESHOLD_MS = 60_000; // first 60 s → 2 s interval
  const FAST_INTERVAL = 2_000;
  const SLOW_INTERVAL = 3_000;

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearTimeout(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const loadEntry = useCallback(async (): Promise<boolean> => {
    try {
      const data = await workspaceApi.entry();
      setEntry(data);

      if (data.ready && data.browserUrl) {
        setPageState('readyToRedirect');
        window.open('/api/v1/workspace-entry/redirect', '_blank');
        return true;
      }

      if (data.hasWorkspace === false) {
        setPageState('noWorkspace');
        return true;
      }

      if (!data.runtimeId) {
        // Runtime doesn't exist yet – user needs to start it from /app
        setPageState('runtimeMissing');
        return true;
      }

      // Runtime exists but not ready yet
      setProgressStep(data.ready ? 4 : 2);
      setPageState('runtimeNotReady');
      return false;
    } catch (e) {
      if (isAppError(e)) {
        if (e.code === 'USER_DISABLED') {
          navigate('/error/disabled');
          return true;
        }
        if (e.code === 'NO_WORKSPACE' || e.httpStatus === 404) {
          setPageState('noWorkspace');
          return true;
        }
        setError(e.message);
      } else {
        setError('加载工作区入口失败，请检查网络连接后重试。');
      }
      setPageState('entryFailed');
      return true;
    }
  }, [navigate]);

  const startPolling = useCallback(async () => {
    stopPolling();
    startTimeRef.current = Date.now();
    setElapsed(0);

    const tick = async () => {
      const now = Date.now();
      const elapsedMs = now - startTimeRef.current;
      setElapsed(Math.floor(elapsedMs / 1000));

      if (elapsedMs >= MAX_POLL_MS) {
        setPageState('timedOut');
        return;
      }

      const done = await loadEntry();
      if (!done) {
        const interval = elapsedMs < FAST_THRESHOLD_MS ? FAST_INTERVAL : SLOW_INTERVAL;
        pollingRef.current = setTimeout(tick, interval);
      }
    };

    tick();
  }, [loadEntry, stopPolling]);

  useEffect(() => {
    startPolling();
    return () => stopPolling();
  }, []);

  const handleManualRefresh = () => startPolling();
  const remainingSeconds = Math.max(0, 180 - elapsed);

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="w-full max-w-lg">

        {/* ── Loading initial ── */}
        {pageState === 'loadingEntry' && (
          <div className="bg-card border border-border rounded-2xl p-10 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-4" />
            <p className="font-medium text-foreground mb-1">正在检查工作区状态...</p>
            <p className="text-muted-foreground text-sm">请稍候</p>
          </div>
        )}

        {/* ── Redirecting ── */}
        {pageState === 'readyToRedirect' && (
          <div className="bg-card border border-green-500/20 rounded-2xl p-10 text-center">
            <CheckCircle2 className="w-10 h-10 text-green-400 mx-auto mb-4" />
            <p className="font-semibold text-foreground mb-1">工作区已就绪</p>
            <p className="text-muted-foreground text-sm mb-4">正在跳转到您的工作区...</p>
            {entry?.browserUrl && (
              <a href="/api/v1/workspace-entry/redirect" className="inline-flex items-center gap-1.5 text-xs text-primary hover:text-primary/80">
                <ExternalLink className="w-3.5 h-3.5" />
                手动跳转
              </a>
            )}
          </div>
        )}

        {/* ── Runtime not ready – staged progress ── */}
        {pageState === 'runtimeNotReady' && (
          <div className="bg-card border border-border rounded-2xl overflow-hidden">
            <div className="px-6 pt-6 pb-4 border-b border-border/50">
              <div className="flex items-center gap-3">
                <Loader2 className="w-7 h-7 animate-spin text-primary" />
                <div>
                  <p className="font-semibold text-foreground">工作区准备中</p>
                  <p className="text-xs text-muted-foreground">
                    已等待 {elapsed}s · 最长等待 180s
                  </p>
                </div>
              </div>
            </div>

            {/* Staged steps */}
            <div className="px-6 py-5 space-y-1">
              {PROGRESS_STEPS.map((step, idx) => {
                const stepNum = idx + 1;
                const isCompleted = stepNum < progressStep;
                const isCurrent = stepNum === progressStep;

                return (
                  <div
                    key={step.id}
                    className={`flex items-start gap-3 p-3 rounded-xl transition-colors ${
                      isCurrent ? 'bg-primary/5 border border-primary/15' :
                      isCompleted ? 'opacity-60' : 'opacity-25'
                    }`}
                  >
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
                      isCompleted ? 'bg-green-500/15' :
                      isCurrent ? 'bg-primary/15' : 'bg-muted/30'
                    }`}>
                      {isCompleted ? (
                        <CheckCircle2 className="w-4 h-4 text-green-400" />
                      ) : isCurrent ? (
                        <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />
                      ) : (
                        <step.icon className="w-3.5 h-3.5 text-muted-foreground" />
                      )}
                    </div>
                    <div>
                      <p className={`text-sm font-medium ${isCurrent ? 'text-foreground' : 'text-muted-foreground'}`}>
                        {step.label}
                      </p>
                      {isCurrent && (
                        <p className="text-xs text-muted-foreground mt-0.5">{step.subLabel}</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mx-6 mb-5 rounded-lg bg-muted/20 border border-border px-4 py-3">
              <p className="text-xs text-muted-foreground leading-relaxed">
                <Clock className="w-3 h-3 inline mr-1 align-middle" />
                准备仍在继续，您可以安全离开此页面，回来后将从最新进度继续显示。
              </p>
            </div>

            <div className="px-6 pb-6">
              <Button variant="outline" className="w-full gap-2" onClick={() => navigate('/app')}>
                <ArrowLeft className="w-4 h-4" />
                返回工作台稍后再试
              </Button>
            </div>
          </div>
        )}

        {/* ── Runtime missing – guide to /app ── */}
        {pageState === 'runtimeMissing' && (
          <div className="bg-card border border-border rounded-2xl p-8">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <p className="font-semibold text-foreground">工作区尚未准备</p>
                <p className="text-xs text-muted-foreground">需要先在工作台启动运行环境</p>
              </div>
            </div>
            <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
              您的工作区运行环境尚未启动。请返回工作台，点击"启动"按钮后再进入工作区。
            </p>
            <Button className="w-full gap-2" onClick={() => navigate('/app')}>
              <ArrowLeft className="w-4 h-4" />
              返回工作台启动运行环境
            </Button>
          </div>
        )}

        {/* ── No workspace ── */}
        {pageState === 'noWorkspace' && (
          <div className="bg-card border border-border rounded-2xl p-8">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                <XCircle className="w-5 h-5 text-muted-foreground" />
              </div>
              <div>
                <p className="font-semibold text-foreground">暂无可用工作区</p>
                <p className="text-xs text-muted-foreground">请联系管理员分配工作区</p>
              </div>
            </div>
            <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
              您的账号目前没有绑定任何工作区。请联系系统管理员，通过邀请链接加入工作区后再试。
            </p>
            <div className="space-y-2">
              <Button variant="outline" className="w-full gap-2" onClick={() => navigate('/app')}>
                <ArrowLeft className="w-4 h-4" />
                返回工作台
              </Button>
              <p className="text-xs text-muted-foreground text-center">如有疑问，请联系系统管理员</p>
            </div>
          </div>
        )}

        {/* ── Timed out ── */}
        {pageState === 'timedOut' && (
          <div className="bg-card border border-amber-500/20 rounded-2xl p-8">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
                <Clock className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <p className="font-semibold text-foreground">仍在准备中，可稍后回来</p>
                <p className="text-xs text-muted-foreground">已等待超过 180 秒</p>
              </div>
            </div>

            {/* Show last known progress */}
            {entry?.runtimeId && (
              <div className="mb-5 space-y-1.5">
                {PROGRESS_STEPS.map((step, idx) => {
                  const isCompleted = (idx + 1) < progressStep;
                  return (
                    <div key={step.id} className={`flex items-center gap-2.5 py-1 ${isCompleted ? '' : 'opacity-35'}`}>
                      {isCompleted ? (
                        <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
                      ) : (
                        <div className="w-4 h-4 rounded-full border border-border flex-shrink-0" />
                      )}
                      <span className="text-sm text-muted-foreground">{step.label}</span>
                    </div>
                  );
                })}
              </div>
            )}

            <p className="text-sm text-muted-foreground mb-5 leading-relaxed">
              工作区准备时间较长，但仍在后台进行中。您可以稍后回来继续，或手动刷新查看最新状态。
            </p>
            <div className="space-y-2">
              <Button className="w-full gap-2" onClick={handleManualRefresh}>
                <RefreshCw className="w-4 h-4" />
                手动刷新
              </Button>
              <Button variant="outline" className="w-full gap-2" onClick={() => navigate('/app')}>
                <ArrowLeft className="w-4 h-4" />
                返回工作台稍后再试
              </Button>
            </div>
          </div>
        )}

        {/* ── Entry failed ── */}
        {pageState === 'entryFailed' && (
          <div className="bg-card border border-red-500/20 rounded-2xl p-8">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
                <XCircle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <p className="font-semibold text-foreground">无法获取工作区状态</p>
                <p className="text-xs text-muted-foreground">请重试或返回工作台</p>
              </div>
            </div>
            {error && <p className="text-sm text-red-400/80 mb-4">{error}</p>}
            <div className="space-y-2">
              <Button className="w-full gap-2" onClick={handleManualRefresh}>
                <RefreshCw className="w-4 h-4" />
                重试
              </Button>
              <Button variant="outline" className="w-full gap-2" onClick={() => navigate('/app')}>
                <ArrowLeft className="w-4 h-4" />
                返回工作台
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function WorkspaceEntryPage() {
  return (
    <RequireAuth>
      <AppShell>
        <WorkspaceEntryContent />
      </AppShell>
    </RequireAuth>
  );
}
