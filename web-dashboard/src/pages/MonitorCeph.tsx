import { useState } from "react";
import { useQuery, useQueryClient, useIsFetching } from "@tanstack/react-query";
import { Database, CheckCircle2, XCircle, AlertCircle, HardDrive, Activity, Clock, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { formatDateTimeWib, formatTimeWib } from "@/lib/datetime";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatBytes } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export function MonitorCeph() {
  const [metric] = useState("storage_used_pct");
  const [hours, setHours] = useState(24);
  const [autoRefresh, setAutoRefresh] = useState<number>(0);
  const queryClient = useQueryClient();

  const TIMEFRAME_OPTIONS = [
    { label: "1h", value: 1 },
    { label: "6h", value: 6 },
    { label: "12h", value: 12 },
    { label: "24h", value: 24 },
    { label: "7d", value: 168 },
    { label: "30d", value: 720 },
  ];

  const { data: snapshot, isLoading: loadingSnap, dataUpdatedAt } = useQuery({
    queryKey: ["ceph", "snapshot"],
    queryFn: async () => {
      try {
        const res = await api.get("/monitor/ceph");
        return res.data;
      } catch (err: any) {
        if (err.response?.status === 404) return null;
        throw err;
      }
    },
    refetchInterval: autoRefresh === 0 ? false : autoRefresh,
  });

  const { data: history, isLoading: loadingHist } = useQuery({
    queryKey: ["ceph", "history", metric, hours],
    queryFn: async () => {
      try {
        const res = await api.get("/monitor/ceph/history", { params: { metric, hours } });
        return res.data;
      } catch (err: any) {
        if (err.response?.status === 404) return { points: [] };
        throw err;
      }
    },
    refetchInterval: autoRefresh === 0 ? false : autoRefresh,
  });

  const isFetching = useIsFetching({ queryKey: ["ceph"] }) > 0;

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["ceph"] });
  };

  const getMetric = (name: string) => {
    if (!snapshot?.metrics || !snapshot.metrics[name]) return null;
    return snapshot.metrics[name];
  };

  const healthStatus = getMetric("health_status")?.text;
  const healthDetail = getMetric("health_detail")?.text;
  const osdUp = getMetric("osd_up")?.value;
  const osdIn = getMetric("osd_in")?.value ?? getMetric("osd_total")?.value;
  const storageUsed = getMetric("storage_used_pct")?.value;
  const storageUsedBytes = getMetric("storage_used_bytes")?.value;
  const storageTotalBytes = getMetric("storage_total_bytes")?.value;

  const chartData = history?.points?.map((p: any) => ({
    time: formatTimeWib(p.collected_at),
    fullDate: formatDateTimeWib(p.collected_at),
    value: p.value,
  })).reverse() || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Ceph Storage</h2>
          <p className="text-muted-foreground mt-2">
            Monitor your object storage backend health and utilization.
          </p>
        </div>
        <div className="flex items-center gap-4 text-sm text-muted-foreground hidden lg:flex">
          {dataUpdatedAt > 0 && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" /> 
              Last updated: {new Date(dataUpdatedAt).toLocaleTimeString()}
            </span>
          )}
          <div className="flex items-center gap-2 border-l pl-4 border-border">
            <span className="text-xs">Auto Refresh:</span>
            <Select value={autoRefresh.toString()} onValueChange={(v) => setAutoRefresh(Number(v))}>
              <SelectTrigger className="h-8 w-[80px] text-xs bg-background">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="0">Off</SelectItem>
                <SelectItem value="10000">10s</SelectItem>
                <SelectItem value="30000">30s</SelectItem>
                <SelectItem value="60000">1m</SelectItem>
                <SelectItem value="300000">5m</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="icon" className="h-8 w-8 bg-background" onClick={handleRefresh} disabled={isFetching}>
              <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>
      </div>

      {!loadingSnap && !snapshot && (
        <Card className="border-dashed border-2 bg-muted/50">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <Database className="h-12 w-12 text-muted-foreground mb-4 opacity-50" />
            <h3 className="text-xl font-medium">No Ceph Data</h3>
            <p className="text-muted-foreground mt-2 max-w-md">
              There is currently no metric data for the Ceph cluster. Ensure the metric collector is running and pushing data to the API.
            </p>
          </CardContent>
        </Card>
      )}

      {(loadingSnap || snapshot) && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Cluster Health</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                {loadingSnap ? (
                  <div className="h-8 animate-pulse bg-muted rounded w-1/2" />
                ) : (
                  <div className="flex items-center gap-2">
                    {healthStatus === "HEALTH_OK" ? (
                      <><CheckCircle2 className="h-6 w-6 text-emerald-500" /> <span className="text-2xl font-bold text-emerald-500">HEALTH_OK</span></>
                    ) : healthStatus === "HEALTH_WARN" ? (
                      <><AlertCircle className="h-6 w-6 text-amber-500" /> <span className="text-2xl font-bold text-amber-500">HEALTH_WARN</span></>
                    ) : (
                      <><XCircle className="h-6 w-6 text-rose-500" /> <span className="text-2xl font-bold text-rose-500">{healthStatus || "UNKNOWN"}</span></>
                    )}
                  </div>
                )}
                {healthDetail && healthDetail !== "None" && (
                  <p className="text-xs text-rose-500 mt-2 font-medium bg-rose-500/10 p-2 rounded break-all">
                    Detail: {healthDetail}
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">OSD Status</CardTitle>
                <Database className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                {loadingSnap ? (
                  <div className="h-8 animate-pulse bg-muted rounded w-1/2" />
                ) : (
                  <>
                    <div className="text-2xl font-bold">
                      {osdUp !== undefined ? osdUp : "-"} <span className="text-lg font-normal text-muted-foreground">UP</span> / {osdIn !== undefined ? osdIn : "-"} <span className="text-lg font-normal text-muted-foreground">IN</span>
                    </div>
                    {osdUp !== osdIn && osdUp !== undefined && osdIn !== undefined && (
                      <p className="text-xs text-rose-500 mt-2 flex items-center">
                        <AlertCircle className="h-3 w-3 mr-1" /> Warning: OSDs down
                      </p>
                    )}
                  </>
                )}
              </CardContent>
            </Card>

            <Card className="flex flex-col justify-between">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Storage Used</CardTitle>
                <HardDrive className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                {loadingSnap ? (
                  <div className="h-8 animate-pulse bg-muted rounded w-1/2" />
                ) : (
                  <>
                    <div className="flex flex-col">
                      <div className="text-2xl font-bold">
                        {storageUsed !== undefined ? `${storageUsed}%` : "-"}
                      </div>
                      {storageUsedBytes !== undefined && storageTotalBytes !== undefined && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {formatBytes(storageUsedBytes)} / {formatBytes(storageTotalBytes)}
                        </p>
                      )}
                    </div>
                    <div className="w-full bg-muted rounded-full h-2 mt-3 overflow-hidden">
                      <div 
                        className={`h-full ${storageUsed && storageUsed > 80 ? 'bg-destructive' : 'bg-primary'}`} 
                        style={{ width: `${Math.min(100, Math.max(0, storageUsed || 0))}%` }}
                      />
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Storage Utilization History</CardTitle>
                  <CardDescription>Last {hours >= 24 ? `${hours / 24}d` : `${hours}h`} of data</CardDescription>
                </div>
                <div className="flex gap-1">
                  {TIMEFRAME_OPTIONS.map((opt) => (
                    <Button
                      key={opt.value}
                      variant={hours === opt.value ? "default" : "outline"}
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => setHours(opt.value)}
                    >
                      {opt.label}
                    </Button>
                  ))}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {loadingHist ? (
                <div className="h-[350px] w-full p-4">
                  <div className="h-full w-full animate-pulse bg-muted rounded-md"></div>
                </div>
              ) : chartData.length === 0 ? (
                <div className="h-[350px] flex items-center justify-center text-muted-foreground border border-dashed rounded-md">
                  No historical data available
                </div>
              ) : (
                <div className="h-[350px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                      <defs>
                        <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                      <XAxis 
                        dataKey="time" 
                        stroke="hsl(var(--muted-foreground))" 
                        fontSize={12} 
                        tickLine={false} 
                        axisLine={false} 
                      />
                      <YAxis 
                        stroke="hsl(var(--muted-foreground))" 
                        fontSize={12} 
                        tickLine={false} 
                        axisLine={false}
                        domain={[0, 100]}
                        tickFormatter={(value) => `${value}%`}
                      />
                      <Tooltip 
                        contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}
                        labelStyle={{ color: "hsl(var(--foreground))", fontWeight: "bold" }}
                        itemStyle={{ color: "hsl(var(--primary))" }}
                        labelFormatter={(label, entries) => entries[0]?.payload.fullDate || label}
                        formatter={(value: any) => [`${value}%`, "Storage Used"]}
                      />
                      <Area 
                        type="monotone" 
                        dataKey="value" 
                        stroke="hsl(var(--primary))" 
                        fillOpacity={1} 
                        fill="url(#colorValue)" 
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
