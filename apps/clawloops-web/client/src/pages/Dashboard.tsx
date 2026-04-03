/**
 * User Dashboard - /app
 * Design: Crafted Dark - ClawLoops Platform
 *
 * Per 页面调用流程_BFF编排.md §5.1 and UI_状态模型.md §4.5
 * Init: auth/me → auth/access → runtime/status + models (parallel)
 * Runtime card with start/stop/delete/open actions
 * Task polling per §7.2
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useSearch } from 'wouter';
import {
  runtimeApi,
  modelsApi,
  workspaceApi,
  RuntimeStatusProjection,
  RuntimeTask,
  Model,
  isAppError,
  pollRuntimeTask,
} from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { AppShell } from '@/components/layout/AppShell';
import { RequireAuth } from '@/components/guards/RouteGuard';
import { StatusBadge, runtimeStateVariant, taskStatusVariant } from '@/components/shared/StatusBadge';
import {
  PageHeader,
  LoadingCard,
  ErrorDisplay,
  MonoText,
  InfoRow,
  ConfirmDialog,
} from '@/components/shared/PageComponents';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import {
  Play,
  Square,
  Trash2,
  ExternalLink,
  Loader2,
  RefreshCw,
  Cpu,
  AlertCircle,
  CheckCircle2,
  Circle,
  Zap,
  Activity,
  PartyPopper,
  X,
  ShieldCheck,
  Layers,
  PlugZap,
} from 'lucide-react';

// ─── Staged progress steps (same 4 as WorkspaceEntry) ───────────────────────

const RUNTIME_PROGRESS_STEPS = [
  { id: 1, label: '已接入 Workspace',     icon: ShieldCheck },
  { id: 2, label: '正在创建运行环境',      icon: Layers      },
  { id: 3, label: '正在启动服务',          icon: Zap         },
  { id: 4, label: '正在验证工作区入口',    icon: PlugZap     },
];

// ─── Invitation applied banner ───────────────────────────────────────────────

function InvitationAppliedBanner({ workspaceName, onDismiss }: { workspaceName?: string | null; onDismiss: () => void }) {
  return (
    <div className="rounded-xl border border-green-500/30 bg-green-500/5 px-5 py-4 flex items-start gap-3 mb-5">
      <div className="w-8 h-8 rounded-full bg-green-500/15 flex items-center justify-center flex-shrink-0">
        <PartyPopper className="w-4 h-4 text-green-400" />
      </div>
      <div className="flex-1">
        <p className="text-sm font-semibold text-green-300">已成功加入工作区</p>
        <p className="text-xs text-green-400/70 mt-0.5">
          {workspaceName ? `欢迎加入「${workspaceName}」` : '邀请已接受，您的账号已绑定工作区。'}
          现在可以启动运行环境开始使用。
        </p>
      </div>
      <button onClick={onDismiss} className="text-muted-foreground hover:text-foreground transition-colors">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

// ============================================================
// Runtime UI state derivation (per UI_状态模型.md §4.5)
// ============================================================

type RuntimeUIState =
  | 'runtimeUnknown'
  | 'runtimeCreating'
  | 'runtimeRunning'
  | 'runtimeStopped'
  | 'runtimeError'
  | 'runtimeDeleting';

function deriveRuntimeUIState(status: RuntimeStatusProjection | null): RuntimeUIState {
  if (!status) return 'runtimeUnknown';
  const { observedState, ready } = status;

  if (observedState === 'creating') return 'runtimeCreating';
  if (observedState === 'running' && !ready) return 'runtimeCreating';
  if (observedState === 'running' && ready) return 'runtimeRunning';
  if (observedState === 'stopped') return 'runtimeStopped';
  if (observedState === 'deleted') return 'runtimeStopped';
  if (observedState === 'error' || status.lastError) return 'runtimeError';
  return 'runtimeUnknown';
}

// ============================================================
// Runtime state label/icon
// ============================================================

const STATE_CONFIG: Record<RuntimeUIState, { label: string; icon: React.ComponentType<{ className?: string }>; color: string }> = {
  runtimeUnknown: { label: '未知', icon: Circle, color: 'text-muted-foreground' },
  runtimeCreating: { label: '启动中', icon: Loader2, color: 'text-blue-400' },
  runtimeRunning: { label: '运行中', icon: CheckCircle2, color: 'text-green-400' },
  runtimeStopped: { label: '已停止', icon: Square, color: 'text-gray-400' },
  runtimeError: { label: '错误', icon: AlertCircle, color: 'text-red-400' },
  runtimeDeleting: { label: '删除中', icon: Loader2, color: 'text-orange-400' },
};

// ============================================================
// Task progress display
// ============================================================

function TaskProgress({ task }: { task: RuntimeTask | null }) {
  if (!task) return null;

  const actionLabels: Record<string, string> = {
    ensure_running: '启动',
    stop: '停止',
    delete: '删除',
  };

  return (
    <div className="rounded-lg bg-blue-500/5 border border-blue-500/15 p-3 mt-3">
      <div className="flex items-center gap-2 mb-1">
        <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />
        <span className="text-xs font-medium text-blue-400">
          {actionLabels[task.action] || task.action} 任务进行中
        </span>
        <StatusBadge variant={taskStatusVariant(task.status)} className="ml-auto">
          {task.status}
        </StatusBadge>
      </div>
      {task.message && (
        <p className="text-xs text-muted-foreground">{task.message}</p>
      )}
      <MonoText className="block mt-1">{task.taskId}</MonoText>
    </div>
  );
}

// ============================================================
// Runtime Card
// ============================================================

interface RuntimeCardProps {
  status: RuntimeStatusProjection | null;
  loading: boolean;
  error: string | null;
  activeTask: RuntimeTask | null;
  onStart: () => void;
  onStop: () => void;
  onDelete: () => void;
  onOpenWorkspace: () => void;
  onRefresh: () => void;
  actionInProgress: string | null;
}

function RuntimeCard({
  status,
  loading,
  error,
  activeTask,
  onStart,
  onStop,
  onDelete,
  onOpenWorkspace,
  onRefresh,
  actionInProgress,
}: RuntimeCardProps) {
  const uiState = deriveRuntimeUIState(status);
  const stateConfig = STATE_CONFIG[uiState];
  const StateIcon = stateConfig.icon;

  const isActionInProgress = !!actionInProgress;
  const canStart = !isActionInProgress && (uiState === 'runtimeStopped' || uiState === 'runtimeUnknown' || uiState === 'runtimeError');
  const canStop = !isActionInProgress && uiState === 'runtimeRunning';
  const canDelete = !isActionInProgress && (uiState === 'runtimeStopped' || uiState === 'runtimeError' || uiState === 'runtimeRunning');
  // const canOpen = !isActionInProgress && status?.ready === true;
  const canOpen = !isActionInProgress && !!status?.runtimeId;

  return (
    <Card className="card-glow">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
            <Cpu className="w-4.5 h-4.5 text-primary" />
            Runtime 状态
          </CardTitle>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onRefresh} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </CardHeader>

      <CardContent>
        {loading && !status && (
          <div className="space-y-2">
            <div className="h-4 skeleton rounded w-1/3" />
            <div className="h-3 skeleton rounded w-2/3" />
          </div>
        )}

        {error && !status && (
          <ErrorDisplay message={error} onRetry={onRefresh} />
        )}

        {status && (
          <>
            {/* State indicator */}
            <div className="flex items-center gap-3 mb-4 p-3 rounded-lg bg-white/3 border border-white/5">
              <div className={`w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center`}>
                <StateIcon className={`w-5 h-5 ${stateConfig.color} ${uiState === 'runtimeCreating' ? 'animate-spin' : ''}`} />
              </div>
              <div>
                <p className={`text-sm font-semibold ${stateConfig.color}`}>{stateConfig.label}</p>
                <p className="text-xs text-muted-foreground">
                  desired: <span className="mono">{status.desiredState}</span>
                  {' · '}
                  observed: <span className="mono">{status.observedState}</span>
                </p>
              </div>
              <div className="ml-auto">
                <StatusBadge variant={status.ready ? 'success' : 'neutral'} dot={status.ready}>
                  {status.ready ? 'ready' : 'not ready'}
                </StatusBadge>
              </div>
            </div>

            {/* Details */}
            <div className="space-y-0 mb-4">
              <InfoRow label="Runtime ID" value={<MonoText>{status.runtimeId}</MonoText>} />
              {status.browserUrl && (
                <InfoRow label="Browser URL" value={<MonoText className="text-blue-400/70">{status.browserUrl}</MonoText>} />
              )}
              {status.reason && (
                <InfoRow label="原因" value={<span className="text-yellow-400 text-xs">{status.reason}</span>} />
              )}
              {status.lastError && (
                <InfoRow label="最近错误" value={<span className="text-red-400 text-xs">{status.lastError}</span>} />
              )}
            </div>

            {/* Task progress */}
            {activeTask && <TaskProgress task={activeTask} />}

            {/* Actions */}
            <div className="flex flex-wrap gap-2 mt-4">
              <Button
                size="sm"
                className="gap-1.5"
                onClick={onStart}
                disabled={!canStart}
              >
                {actionInProgress === 'start' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Play className="w-3.5 h-3.5" />
                )}
                {actionInProgress === 'start' ? '正在启动' : '启动'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5"
                onClick={onStop}
                disabled={!canStop}
              >
                {actionInProgress === 'stop' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Square className="w-3.5 h-3.5" />
                )}
                {actionInProgress === 'stop' ? '正在停止' : '停止'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5 text-destructive hover:text-destructive"
                onClick={onDelete}
                disabled={!canDelete}
              >
                {actionInProgress === 'delete' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Trash2 className="w-3.5 h-3.5" />
                )}
                删除
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5 ml-auto"
                onClick={onOpenWorkspace}
                disabled={!canOpen}
              >
                <ExternalLink className="w-3.5 h-3.5" />
                进入工作区
              </Button>
            </div>
          </>
        )}

        {!status && !loading && !error && (
          <div className="text-center py-6">
            <p className="text-sm text-muted-foreground mb-3">尚未创建 Runtime</p>
            <Button size="sm" className="gap-1.5" onClick={onStart} disabled={isActionInProgress}>
              <Play className="w-3.5 h-3.5" />
              创建并启动
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================
// Models Card
// ============================================================

function ModelsCard({ models, loading }: { models: Model[]; loading: boolean }) {
  return (
    <Card className="card-glow">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
          <Zap className="w-4.5 h-4.5 text-primary" />
          可用模型
          <span className="text-xs text-muted-foreground font-normal ml-1">（只读）</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 skeleton rounded" />
            ))}
          </div>
        )}
        {!loading && models.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">暂无可用模型</p>
        )}
        {!loading && models.length > 0 && (
          <div className="space-y-1.5">
            {models.map((model) => (
              <div
                key={model.modelId}
                className="flex items-center justify-between px-3 py-2 rounded-md bg-white/3 border border-white/5"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">{model.name}</p>
                  {model.provider && (
                    <p className="text-xs text-muted-foreground">{model.provider}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {model.isDefault && (
                    <StatusBadge variant="info">默认</StatusBadge>
                  )}
                  <StatusBadge variant={model.enabled ? 'success' : 'neutral'}>
                    {model.enabled ? '启用' : '禁用'}
                  </StatusBadge>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================
// Delete Dialog
// ============================================================

function DeleteDialog({
  open,
  onOpenChange,
  onConfirm,
  loading,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onConfirm: (policy: 'preserve_workspace' | 'wipe_workspace') => void;
  loading: boolean;
}) {
  const [policy, setPolicy] = useState<'preserve_workspace' | 'wipe_workspace'>('preserve_workspace');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>删除 Runtime</DialogTitle>
          <DialogDescription>
            请选择删除策略，此操作不可撤销。
          </DialogDescription>
        </DialogHeader>

        <RadioGroup
          value={policy}
          onValueChange={(v) => setPolicy(v as typeof policy)}
          className="space-y-3 my-2"
        >
          <div className="flex items-start gap-3 p-3 rounded-lg border border-border hover:bg-white/3 cursor-pointer">
            <RadioGroupItem value="preserve_workspace" id="preserve" className="mt-0.5" />
            <Label htmlFor="preserve" className="cursor-pointer">
              <p className="text-sm font-medium">保留工作区数据</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                删除 Runtime 容器，但保留工作区文件和配置
              </p>
            </Label>
          </div>
          <div className="flex items-start gap-3 p-3 rounded-lg border border-destructive/30 hover:bg-destructive/5 cursor-pointer">
            <RadioGroupItem value="wipe_workspace" id="wipe" className="mt-0.5" />
            <Label htmlFor="wipe" className="cursor-pointer">
              <p className="text-sm font-medium text-destructive">清除工作区数据</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                删除 Runtime 容器并清除所有工作区文件（不可恢复）
              </p>
            </Label>
          </div>
        </RadioGroup>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            取消
          </Button>
          <Button
            variant="destructive"
            onClick={() => onConfirm(policy)}
            disabled={loading}
            className="gap-2"
          >
            {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            确认删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================
// Main Dashboard
// ============================================================

function DashboardContent() {
  const { user } = useAuth();
  const [, navigate] = useLocation();
  const search = useSearch();

  // Detect invitationApplied from post-login redirect query param
  const searchParams = new URLSearchParams(search);
  const [showInvitationBanner, setShowInvitationBanner] = useState(
    searchParams.get('invitationApplied') === 'true'
  );
  const invitationWorkspaceName = searchParams.get('workspaceName') || null;

  // Runtime state
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatusProjection | null>(null);
  const [runtimeLoading, setRuntimeLoading] = useState(true);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);

  // Models state
  const [models, setModels] = useState<Model[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);

  // Task state
  const [activeTask, setActiveTask] = useState<RuntimeTask | null>(null);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  // Delete dialog
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Polling ref for cleanup
  const pollingRef = useRef<boolean>(false);

  // ============================================================
  // Data loading
  // ============================================================

  const loadRuntimeStatus = useCallback(async () => {
    try {
      const status = await runtimeApi.status();
      setRuntimeStatus(status);
      setRuntimeError(null);
    } catch (e) {
      if (isAppError(e) && e.code === 'RUNTIME_NOT_FOUND') {
        setRuntimeStatus(null);
      } else {
        setRuntimeError(isAppError(e) ? e.message : '加载 Runtime 状态失败');
      }
    } finally {
      setRuntimeLoading(false);
    }
  }, []);

  const loadModels = useCallback(async () => {
    try {
      const res = await modelsApi.list();
      setModels(res.models || []);
    } catch {
      // Non-critical, silently fail
    } finally {
      setModelsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Per BFF编排.md §5.1: auth/me first, then parallel
    setRuntimeLoading(true);
    setModelsLoading(true);
    Promise.all([loadRuntimeStatus(), loadModels()]);
  }, [loadRuntimeStatus, loadModels]);

  // ============================================================
  // Task polling
  // ============================================================

  const startPolling = useCallback(async (taskId: string, action: string) => {
    setActionInProgress(action);
    pollingRef.current = true;

    await pollRuntimeTask(taskId, {
      onTick: (task) => {
        setActiveTask(task);
      },
      onTimeout: () => {
        toast.warning('任务超时，请手动刷新状态');
        setActionInProgress(null);
        setActiveTask(null);
      },
    });

    // Refresh runtime status after task completes
    await loadRuntimeStatus();
    setActionInProgress(null);
    setActiveTask(null);
    pollingRef.current = false;
  }, [loadRuntimeStatus]);

  // ============================================================
  // Actions
  // ============================================================

  const handleStart = async () => {
    setActionInProgress('start');
    try {
      const res = await runtimeApi.start();
      toast.success('启动任务已提交');
      startPolling(res.taskId, 'start');
    } catch (e) {
      if (isAppError(e)) {
        toast.error(`启动失败: ${e.message}`, { description: e.code });
      } else {
        toast.error('启动失败');
      }
      setActionInProgress(null);
    }
  };

  const handleStop = async () => {
    setActionInProgress('stop');
    try {
      const res = await runtimeApi.stop();
      toast.success('停止任务已提交');
      startPolling(res.taskId, 'stop');
    } catch (e) {
      if (isAppError(e)) {
        toast.error(`停止失败: ${e.message}`, { description: e.code });
      } else {
        toast.error('停止失败');
      }
      setActionInProgress(null);
    }
  };

  const handleDelete = async (policy: 'preserve_workspace' | 'wipe_workspace') => {
    setDeleteLoading(true);
    try {
      const res = await runtimeApi.delete(policy);
      setDeleteDialogOpen(false);
      toast.success('删除任务已提交');
      startPolling(res.taskId, 'delete');
    } catch (e) {
      if (isAppError(e)) {
        toast.error(`删除失败: ${e.message}`, { description: e.code });
      } else {
        toast.error('删除失败');
      }
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleOpenWorkspace = async () => {
    try {
      const entry = await workspaceApi.entry();
      if (entry.ready && entry.browserUrl) {
        // window.location.href = entry.browserUrl;
        window.location.href = '/api/v1/workspace-entry/redirect';
      } else {
        navigate('/workspace-entry');
      }
    } catch (e) {
      if (isAppError(e)) {
        toast.error(`无法进入工作区: ${e.message}`);
      } else {
        navigate('/workspace-entry');
      }
    }
  };

  return (
    <div className="page-enter">
      <PageHeader
        title="工作台"
        description={`欢迎回来，${(user as any)?.username || user?.userId || '用户'}`}
        actions={
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Activity className="w-3.5 h-3.5" />
              <span className="mono">{user?.role}</span>
            </div>
          </div>
        }
      />

      {/* Invitation applied confirmation banner */}
      {showInvitationBanner && (
        <InvitationAppliedBanner
          workspaceName={invitationWorkspaceName}
          onDismiss={() => setShowInvitationBanner(false)}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Runtime Card */}
        <RuntimeCard
          status={runtimeStatus}
          loading={runtimeLoading}
          error={runtimeError}
          activeTask={activeTask}
          onStart={handleStart}
          onStop={handleStop}
          onDelete={() => setDeleteDialogOpen(true)}
          onOpenWorkspace={handleOpenWorkspace}
          onRefresh={loadRuntimeStatus}
          actionInProgress={actionInProgress}
        />

        {/* Models Card */}
        <ModelsCard models={models} loading={modelsLoading} />

        {/* User Info Card */}
        <Card className="card-glow">
          <CardHeader className="pb-3">
            <CardTitle className="text-base" style={{ fontFamily: 'Space Grotesk' }}>
              账号信息
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-0">
              <InfoRow label="用户 ID" value={<MonoText>{user?.userId}</MonoText>} />
              <InfoRow label="Subject ID" value={<MonoText>{user?.subjectId}</MonoText>} />
              <InfoRow label="租户 ID" value={<MonoText>{user?.tenantId}</MonoText>} />
              <InfoRow label="角色" value={
                <StatusBadge variant={user?.isAdmin ? 'info' : 'neutral'}>
                  {user?.role}
                </StatusBadge>
              } />
              <InfoRow label="状态" value={
                <StatusBadge variant={user?.status === 'active' ? 'success' : 'error'}>
                  {user?.status}
                </StatusBadge>
              } />
              <InfoRow label="认证方式" value={<MonoText>{user?.auth?.method}</MonoText>} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Delete Dialog */}
      <DeleteDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleDelete}
        loading={deleteLoading}
      />
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <AppShell>
        <DashboardContent />
      </AppShell>
    </RequireAuth>
  );
}
