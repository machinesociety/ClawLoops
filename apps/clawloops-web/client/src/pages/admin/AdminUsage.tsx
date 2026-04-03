/**
 * Admin Usage Summary Page - /admin/usage
 * Design: Crafted Dark - ClawLoops Platform
 *
 * Per 页面调用流程_BFF编排.md §6.6
 * Shows usage stats: total requests, tokens, cost, by model, by user
 */

import { useCallback, useEffect, useState } from 'react';
import { adminApi, UsageSummary, isAppError } from '@/lib/api';
import { RequireAdmin } from '@/components/guards/RouteGuard';
import { AppShell } from '@/components/layout/AppShell';
import {
  PageHeader,
  LoadingCard,
  ErrorDisplay,
  MonoText,
} from '@/components/shared/PageComponents';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { RefreshCw, BarChart3, Zap, DollarSign, Activity } from 'lucide-react';

// ============================================================
// Stat Card
// ============================================================

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  sub?: string;
  color: string;
}) {
  return (
    <Card className="card-glow">
      <CardContent className="pt-5">
        <div className="flex items-start gap-3">
          <div className={`w-9 h-9 rounded-lg ${color} flex items-center justify-center flex-shrink-0`}>
            <Icon className="w-4.5 h-4.5" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
            <p className="text-2xl font-bold text-foreground" style={{ fontFamily: 'Space Grotesk' }}>
              {value}
            </p>
            {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================
// Custom Tooltip
// ============================================================

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-lg px-3 py-2 text-xs shadow-lg">
      <p className="text-muted-foreground mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: <span className="font-medium">{p.value?.toLocaleString()}</span>
        </p>
      ))}
    </div>
  );
}

// ============================================================
// Main Page
// ============================================================

function AdminUsageContent() {
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminApi.usage.summary();
      setSummary(data);
    } catch (e) {
      setError(isAppError(e) ? e.message : '加载 Usage 数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  // Fixed: Display 0 when value is undefined or null
  function formatNumber(n?: number) {
    if (n === undefined || n === null) return '0';
    return n.toLocaleString('zh-CN');
  }

  // Fixed: Display $0.0000 when value is undefined or null
  function formatCost(n?: number) {
    if (n === undefined || n === null) return '$0.0000';
    return `$${n.toFixed(4)}`;
  }

  const CHART_COLORS = [
    'oklch(0.65 0.18 240)',
    'oklch(0.70 0.15 200)',
    'oklch(0.60 0.20 280)',
    'oklch(0.72 0.12 160)',
    'oklch(0.68 0.18 320)',
  ];

  const modelChartData = summary?.byModel?.map((m) => ({
    name: m.modelName || m.modelId,
    requests: m.requests,
    tokens: m.tokens,
  })) || [];

  const userChartData = summary?.byUser?.slice(0, 10).map((u) => ({
    name: u.userId,
    requests: u.requests,
    tokens: u.tokens,
  })) || [];

  return (
    <div className="page-enter">
      <PageHeader
        title="Usage 汇总"
        description={
          summary?.period
            ? `统计周期：${summary.period.from} ~ ${summary.period.to}`
            : 'API 使用量统计'
        }
        actions={
          <Button variant="outline" size="sm" className="gap-2" onClick={loadSummary} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
        }
      />

      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
          {[1, 2, 3].map((i) => <LoadingCard key={i} />)}
        </div>
      )}

      {!loading && error && (
        <ErrorDisplay message={error} onRetry={loadSummary} className="py-12" />
      )}

      {!loading && !error && summary && (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            <StatCard
              icon={Activity}
              label="总请求数"
              value={formatNumber(summary.totalRequests)}
              color="bg-blue-500/10 text-blue-400"
            />
            <StatCard
              icon={Zap}
              label="总 Token 数"
              value={formatNumber(summary.totalTokens)}
              color="bg-purple-500/10 text-purple-400"
            />
            <StatCard
              icon={DollarSign}
              label="估算费用"
              value={formatCost(summary.totalCost)}
              color="bg-green-500/10 text-green-400"
            />
          </div>

          {/* By model chart */}
          {modelChartData.length > 0 && (
            <Card className="card-glow mb-5">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2" style={{ fontFamily: 'Space Grotesk' }}>
                  <BarChart3 className="w-4.5 h-4.5 text-primary" />
                  按模型分布
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={modelChartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="oklch(1 0 0 / 0.06)" />
                    <XAxis
                      dataKey="name"
                      tick={{ fill: 'oklch(0.55 0.012 264)', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fill: 'oklch(0.55 0.012 264)', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="requests" name="请求数" radius={[3, 3, 0, 0]}>
                      {modelChartData.map((_, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* By user table */}
          {userChartData.length > 0 && (
            <Card className="card-glow">
              <CardHeader className="pb-3">
                <CardTitle className="text-base" style={{ fontFamily: 'Space Grotesk' }}>
                  按用户分布（Top 10）
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {userChartData.map((u, i) => {
                    const maxRequests = Math.max(...userChartData.map((x) => x.requests));
                    const pct = maxRequests > 0 ? (u.requests / maxRequests) * 100 : 0;
                    return (
                      <div key={u.name} className="flex items-center gap-3">
                        <span className="text-xs text-muted-foreground w-4 text-right">{i + 1}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <MonoText className="truncate">{u.name}</MonoText>
                            <span className="text-xs text-muted-foreground ml-2 flex-shrink-0">
                              {u.requests.toLocaleString()} req
                            </span>
                          </div>
                          <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full bg-primary/60 transition-all"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {modelChartData.length === 0 && userChartData.length === 0 && (
            <Card className="card-glow">
              <CardContent className="py-12 text-center">
                <BarChart3 className="w-10 h-10 text-muted-foreground/30 mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">暂无详细使用数据</p>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

export default function AdminUsagePage() {
  return (
    <RequireAdmin>
      <AppShell>
        <AdminUsageContent />
      </AppShell>
    </RequireAdmin>
  );
}
