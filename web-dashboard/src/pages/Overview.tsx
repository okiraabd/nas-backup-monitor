import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { Server, Database, AlertCircle, CheckCircle2, XCircle, RefreshCw, Clock } from "lucide-react";
import { api } from "@/lib/api";

import { formatDistanceToNow } from "date-fns";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

export function Overview() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [autoRefresh, setAutoRefresh] = useState("10");
  const refetchInterval = autoRefresh !== "0" ? parseInt(autoRefresh) * 1000 : false;

  const summaryQuery = useQuery({
    queryKey: ["monitor-summary"],
    queryFn: async () => {
      const res = await api.get("/monitor/summary");
      return res.data;
    },
    refetchInterval,
  });
  const { data: summary, isLoading: loadingSummary, isError: summaryError } = summaryQuery;

  const logsQuery = useQuery({
    queryKey: ["logs", "failed-recent"],
    queryFn: async () => {
      const res = await api.get("/logs", {
        params: { status: "FAILED", page_size: 5 },
      });
      return res.data;
    },
    refetchInterval,
  });
  const { data: logsData, isLoading: loadingLogs, isError: logsError } = logsQuery;

  const activityQuery = useQuery({
    queryKey: ["monitor-activity"],
    queryFn: async () => {
      const res = await api.get("/monitor/activity-trend");
      // Fallback dummy data if API returns empty list or not found yet during dev
      if (!res.data || !res.data.days || res.data.days.length === 0) {
        return {
          days: [
            { date: "Mon", success: 12, failed: 1 },
            { date: "Tue", success: 14, failed: 0 },
            { date: "Wed", success: 13, failed: 2 },
            { date: "Thu", success: 15, failed: 0 },
            { date: "Fri", success: 14, failed: 0 },
            { date: "Sat", success: 12, failed: 0 },
            { date: "Sun", success: 12, failed: 0 },
          ]
        };
      }
      return res.data;
    },
    refetchInterval,
  });
  const { data: activityData, isLoading: loadingActivity, isError: activityError } = activityQuery;

  const isRefetching =
    summaryQuery.isFetching || logsQuery.isFetching || activityQuery.isFetching;

  const handleManualRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["monitor-summary"] });
    queryClient.invalidateQueries({ queryKey: ["logs", "failed-recent"] });
    queryClient.invalidateQueries({ queryKey: ["monitor-activity"] });
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Dashboard Overview</h2>
          <p className="text-muted-foreground mt-2">
            Monitor your NAS backup fleet and Ceph storage cluster.
          </p>
        </div>
        <div className="flex items-center gap-4 text-sm text-muted-foreground hidden lg:flex">
          {summaryQuery.dataUpdatedAt > 0 && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Last updated: {new Date(summaryQuery.dataUpdatedAt).toLocaleTimeString()}
            </span>
          )}
          <div className="flex items-center gap-2 border-l pl-4 border-border">
            <span className="text-xs">Auto Refresh:</span>
            <Select value={autoRefresh} onValueChange={setAutoRefresh}>
              <SelectTrigger className="h-8 w-[80px] text-xs bg-background">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="0">Off</SelectItem>
                <SelectItem value="10">10s</SelectItem>
                <SelectItem value="30">30s</SelectItem>
                <SelectItem value="60">1m</SelectItem>
                <SelectItem value="300">5m</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8 bg-background"
              onClick={handleManualRefresh}
              disabled={isRefetching}
              title="Refresh Now"
            >
              <RefreshCw className={`h-3 w-3 ${isRefetching ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Total NAS */}
        <Card
          className="hover:border-primary/50 cursor-pointer transition-colors hover:bg-muted/10"
          onClick={() => navigate('/dashboard/monitor/nas')}
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">NAS Total</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {summaryError ? (
              <div className="flex items-center text-sm text-destructive gap-2 h-8"><AlertCircle className="h-4 w-4" /> Failed to load</div>
            ) : loadingSummary ? (
              <div className="h-8 animate-pulse bg-muted rounded" />
            ) : (
              <>
                <div className="text-2xl font-bold">{summary?.total_nas || 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  Monitored endpoints
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* NAS Freshness */}
        <Card
          className="hover:border-primary/50 cursor-pointer transition-colors hover:bg-muted/10"
          onClick={() => navigate('/dashboard/monitor/nas')}
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">NAS Sync Status</CardTitle>
            <ActivityIcon />
          </CardHeader>
          <CardContent>
            {summaryError ? (
              <div className="flex items-center text-sm text-destructive gap-2 h-8"><AlertCircle className="h-4 w-4" /> Failed to load</div>
            ) : loadingSummary ? (
              <div className="h-8 animate-pulse bg-muted rounded" />
            ) : (
              <div className="flex gap-2 text-sm mt-1">
                <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20">
                  {summary?.nas_fresh || 0} Fresh
                </Badge>
                <Badge variant="outline" className="bg-amber-500/10 text-amber-500 border-amber-500/20">
                  {summary?.nas_stale || 0} Stale
                </Badge>
                <Badge variant="outline" className="bg-rose-500/10 text-rose-500 border-rose-500/20">
                  {summary?.nas_offline || 0} Offline
                </Badge>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Ceph Status */}
        <Card
          className="hover:border-primary/50 cursor-pointer transition-colors hover:bg-muted/10"
          onClick={() => navigate('/dashboard/monitor/ceph')}
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Ceph Health</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {summaryError ? (
              <div className="flex items-center text-sm text-destructive gap-2 h-8"><AlertCircle className="h-4 w-4" /> Failed to load</div>
            ) : loadingSummary ? (
              <div className="h-8 animate-pulse bg-muted rounded" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {summary?.ceph_health === "HEALTH_OK" ? (
                    <span className="text-emerald-500 flex items-center gap-2">
                      <CheckCircle2 className="h-5 w-5" /> OK
                    </span>
                  ) : summary?.ceph_health === "HEALTH_WARN" ? (
                    <span className="text-amber-500 flex items-center gap-2">
                      <AlertCircle className="h-5 w-5" /> WARN
                    </span>
                  ) : (
                    <span className="text-rose-500 flex items-center gap-2">
                      <XCircle className="h-5 w-5" /> {summary?.ceph_health || "UNKNOWN"}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-1">
                  <span>Sync:</span>
                  <Badge
                    variant="outline"
                    className={`h-5 text-[10px] px-1.5 ${summary?.ceph_status === 'fresh' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' :
                      summary?.ceph_status === 'stale' ? 'bg-amber-500/10 text-amber-500 border-amber-500/20' :
                        'bg-rose-500/10 text-rose-500 border-rose-500/20'
                      }`}
                  >
                    {summary?.ceph_status ? summary.ceph_status.charAt(0).toUpperCase() + summary.ceph_status.slice(1) : 'Offline'}
                  </Badge>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Ceph Storage */}
        <Card
          className="hover:border-primary/50 cursor-pointer transition-colors hover:bg-muted/10"
          onClick={() => navigate('/dashboard/monitor/ceph')}
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Ceph Storage</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {summaryError ? (
              <div className="flex items-center text-sm text-destructive gap-2 h-8"><AlertCircle className="h-4 w-4" /> Failed to load</div>
            ) : loadingSummary ? (
              <div className="h-8 animate-pulse bg-muted rounded" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {summary?.storage_used_pct !== null && summary?.storage_used_pct !== undefined
                    ? `${summary.storage_used_pct}%`
                    : "N/A"}
                </div>
                {/* Visual progress bar representation */}
                {summary?.storage_used_pct !== null && summary?.storage_used_pct !== undefined && (
                  <div className="w-full bg-muted rounded-full h-2 mt-2 overflow-hidden">
                    <div
                      className={`h-full ${summary.storage_used_pct >= 85 ? 'bg-destructive' : summary.storage_used_pct >= 70 ? 'bg-amber-500' : 'bg-primary'}`}
                      style={{ width: `${Math.min(100, Math.max(0, summary.storage_used_pct))}%`, transition: 'width 0.5s ease-in-out' }}
                    />
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Failed Backups Section */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7 mt-4">
        {/* Recent Failed Backups */}
        <Card className="col-span-3">
          <CardHeader>
            <CardTitle>Recent Failed Backups</CardTitle>
          </CardHeader>
          <CardContent>
            {logsError ? (
              <div className="text-center p-6 text-destructive border rounded-md border-dashed flex flex-col items-center gap-2">
                <AlertCircle className="h-6 w-6 mb-1" />
                <p>Failed to load recent backups.</p>
              </div>
            ) : loadingLogs ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-12 animate-pulse bg-muted rounded" />
                ))}
              </div>
            ) : logsData?.items?.length === 0 ? (
              <div className="text-center p-6 text-muted-foreground border rounded-md border-dashed">
                No failed backups found! 🎉
              </div>
            ) : (
              <div className="space-y-4 max-h-[380px] overflow-y-auto pr-2 custom-scrollbar">
                {logsData?.items?.map((log: any) => (
                  <Link key={log.id} to={`/dashboard/logs/${log.id}`} className="block">
                    <div className="flex items-center justify-between p-4 border rounded-lg bg-card hover:bg-muted/50 cursor-pointer transition-colors">
                      <div>
                        <div className="font-medium flex items-center gap-2">
                          <XCircle className="h-4 w-4 text-destructive" />
                          {log.nas_id}
                          {log.acknowledged && (
                            <Badge variant="outline" className="text-[10px] h-5">Ack'd</Badge>
                          )}
                        </div>
                        <div className="text-sm text-muted-foreground mt-1">
                          Job: {log.job_name} • {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                        </div>
                        {log.message && (
                          <div className="text-sm text-destructive mt-1 font-mono break-all">
                            {log.message}
                          </div>
                        )}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* System Activity Chart */}
        <Card className="col-span-4">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-baseline gap-2">
              Backup Job Trends
              <span className="text-sm font-normal text-muted-foreground">(Last 7 Days)</span>
            </CardTitle>
            <CardDescription>Click on a bar to view detailed logs for that day</CardDescription>
          </CardHeader>
          <CardContent>
            {activityError ? (
              <div className="flex h-[380px] items-center justify-center border border-dashed rounded-md text-destructive">
                <div className="flex flex-col items-center gap-2"><AlertCircle className="h-6 w-6" /> <p>Failed to load chart data.</p></div>
              </div>
            ) : loadingActivity ? (
              <div className="flex h-[380px] items-center justify-center border border-dashed rounded-md text-muted-foreground">
                <div className="animate-pulse">Loading Chart...</div>
              </div>
            ) : (
              <div className="h-[380px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={activityData?.days || []}
                    margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                    onClick={(state: any) => {
                      if (state && state.activePayload && state.activePayload.length > 0) {
                        const clickedDate = state.activePayload[0].payload.date;
                        if (clickedDate) {
                          navigate(`/dashboard/logs?date=${clickedDate}`);
                        }
                      }
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="currentColor" className="opacity-10" />
                    <XAxis
                      dataKey="date"
                      tickLine={false}
                      axisLine={false}
                      fontSize={12}
                      stroke="currentColor"
                      className="opacity-50"
                      tickFormatter={(value) => {
                        // Simplify date to short format if it's YYYY-MM-DD
                        if (value.length === 10) return value.substring(5);
                        return value;
                      }}
                    />
                    <YAxis
                      tickLine={false}
                      axisLine={false}
                      fontSize={12}
                      stroke="currentColor"
                      className="opacity-50"
                      allowDecimals={false}
                    />
                    <Tooltip
                      cursor={{ fill: 'var(--muted)', opacity: 0.2 }}
                      contentStyle={{ backgroundColor: 'var(--card)', borderColor: 'var(--border)', borderRadius: 'var(--radius)' }}
                      itemStyle={{ color: 'var(--foreground)' }}
                    />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
                    <Bar
                      dataKey="success"
                      name="Success"
                      stackId="a"
                      fill="#10b981"
                      radius={[0, 0, 4, 4]}
                      onClick={(data: any) => {
                        if (data && data.date) {
                          navigate(`/dashboard/logs?date=${data.date}`);
                        }
                      }}
                      style={{ cursor: 'pointer' }}
                    />
                    <Bar
                      dataKey="failed"
                      name="Failed"
                      stackId="a"
                      fill="#f43f5e"
                      radius={[4, 4, 0, 0]}
                      onClick={(data: any) => {
                        if (data && data.date) {
                          navigate(`/dashboard/logs?date=${data.date}`);
                        }
                      }}
                      style={{ cursor: 'pointer' }}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ActivityIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      className="h-4 w-4 text-muted-foreground"
    >
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  )
}
