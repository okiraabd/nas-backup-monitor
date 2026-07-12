import { useState, useEffect } from "react";
import { useQuery, useQueryClient, useIsFetching } from "@tanstack/react-query";
import { Server, Activity, Cpu, MemoryStick, HardDrive, Clock, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { formatDateTimeWib, formatTimeWib } from "@/lib/datetime";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatBytes } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const METRIC_LABELS: Record<string, string> = {
  cpu_usage: "CPU Usage",
  ram_used_pct: "Memory Usage",
  disk_used_pct: "Disk Usage",
};

const TIMEFRAME_OPTIONS = [
  { label: "1h", value: 1 },
  { label: "6h", value: 6 },
  { label: "12h", value: 12 },
  { label: "24h", value: 24 },
  { label: "7d", value: 168 },
  { label: "30d", value: 720 },
];

export function MonitorNas() {
  const [selectedNas, setSelectedNas] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState<number>(0);
  const queryClient = useQueryClient();

  const { data: nasList, isLoading: loadingList, dataUpdatedAt } = useQuery({
    queryKey: ["nas-list"],
    queryFn: async () => {
      const res = await api.get("/monitor/nas");
      return res.data;
    },
    refetchInterval: autoRefresh === 0 ? false : autoRefresh,
  });

  const fetchingNas = useIsFetching({ queryKey: ["nas"] });
  const fetchingList = useIsFetching({ queryKey: ["nas-list"] });
  const isFetching = fetchingNas > 0 || fetchingList > 0;

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["nas"] });
    queryClient.invalidateQueries({ queryKey: ["nas-list"] });
  };

  // Auto-select first NAS
  useEffect(() => {
    if (nasList?.items?.length > 0 && !selectedNas) {
      setSelectedNas(nasList.items[0].source_id);
    }
  }, [nasList, selectedNas]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">NAS Monitoring</h2>
          <p className="text-muted-foreground mt-2">
            Real-time metrics and health status of all registered NAS endpoints.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-4 mr-2 text-sm text-muted-foreground hidden lg:flex">
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
          <Select 
            value={selectedNas || ""} 
            onValueChange={setSelectedNas}
            disabled={loadingList || nasList?.items?.length === 0}
          >
            <SelectTrigger className="w-64 bg-background">
              <Server className="w-4 h-4 mr-2 text-muted-foreground" />
              <SelectValue placeholder="Select NAS Device" />
            </SelectTrigger>
            <SelectContent>
              {nasList?.items?.map((nas: any) => (
                <SelectItem key={nas.source_id} value={nas.source_id}>
                  <div className="flex items-center justify-between w-full pr-2">
                    <span>{nas.source_id}</span>
                    <div className="ml-4 flex items-center">
                      {nas.status === "fresh" && <div className="h-2 w-2 rounded-full bg-emerald-500" title="Fresh"></div>}
                      {nas.status === "stale" && <div className="h-2 w-2 rounded-full bg-amber-500" title="Stale"></div>}
                      {nas.status === "offline" && <div className="h-2 w-2 rounded-full bg-rose-500" title="Offline"></div>}
                    </div>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {!selectedNas ? (
        <Card className="h-full min-h-[400px] flex items-center justify-center border-dashed">
          <CardContent className="text-center text-muted-foreground pt-6">
            <Activity className="h-12 w-12 mx-auto mb-4 opacity-20" />
            <p>Select a NAS endpoint to view its metrics.</p>
          </CardContent>
        </Card>
      ) : (
        <NasDetailView nasId={selectedNas} autoRefresh={autoRefresh} />
      )}
    </div>
  );
}

function NasDetailView({ nasId, autoRefresh }: { nasId: string, autoRefresh: number }) {
  const [hours, setHours] = useState(24);

  const { data: snapshot, isLoading: loadingSnap } = useQuery({
    queryKey: ["nas", nasId, "snapshot"],
    queryFn: async () => {
      const res = await api.get(`/monitor/nas/${nasId}`);
      return res.data;
    },
    refetchInterval: autoRefresh === 0 ? false : autoRefresh,
  });

  const getMetricValue = (name: string) => {
    if (!snapshot?.metrics || !snapshot.metrics[name]) return "N/A";
    const m = snapshot.metrics[name];
    if (m.value !== null) return `${m.value}${m.unit ? m.unit : ''}`;
    if (m.text !== null) return m.text;
    return "N/A";
  };

  return (
    <div className="space-y-6">
      {/* 3 Full-Width Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">CPU Usage</p>
              {loadingSnap ? (
                <div className="h-8 w-20 animate-pulse bg-muted rounded-md"></div>
              ) : (
                <h3 className="text-2xl font-bold">{getMetricValue("cpu_usage")}</h3>
              )}
            </div>
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
              <Cpu className="h-5 w-5 text-primary" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">Memory Usage</p>
              {loadingSnap ? (
                <div className="h-8 w-20 animate-pulse bg-muted rounded-md"></div>
              ) : (
                <h3 className="text-2xl font-bold">{getMetricValue("ram_used_pct")}</h3>
              )}
            </div>
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
              <MemoryStick className="h-5 w-5 text-primary" />
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 flex flex-col justify-between h-full min-h-[100px]">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">Disk Usage</p>
                {loadingSnap ? (
                  <div className="h-8 w-20 animate-pulse bg-muted rounded-md mb-2"></div>
                ) : (
                  <h3 className="text-2xl font-bold">{getMetricValue("disk_used_pct")}</h3>
                )}
              </div>
              <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                <HardDrive className="h-5 w-5 text-primary" />
              </div>
            </div>
            {snapshot?.metrics?.storage_used_bytes && snapshot?.metrics?.storage_total_bytes && (
              <p className="text-xs text-muted-foreground mt-2">
                {formatBytes(snapshot.metrics.storage_used_bytes.value)} / {formatBytes(snapshot.metrics.storage_total_bytes.value)}
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Side-by-Side Charts */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <MetricChart nasId={nasId} metric="cpu_usage" hours={hours} setHours={setHours} autoRefresh={autoRefresh} />
        <MetricChart nasId={nasId} metric="ram_used_pct" hours={hours} setHours={setHours} autoRefresh={autoRefresh} />
      </div>
    </div>
  );
}

function MetricChart({ nasId, metric, hours, setHours, autoRefresh }: { nasId: string, metric: string, hours: number, setHours: (h: number) => void, autoRefresh: number }) {
  const { data: history, isLoading: loadingHist } = useQuery({
    queryKey: ["nas", nasId, "history", metric, hours],
    queryFn: async () => {
      const res = await api.get(`/monitor/nas/${nasId}/history`, { params: { metric, hours } });
      return res.data;
    },
    refetchInterval: autoRefresh === 0 ? false : autoRefresh,
  });

  const chartData = history?.points?.map((p: any) => ({
    time: formatTimeWib(p.collected_at),
    fullDate: formatDateTimeWib(p.collected_at),
    value: p.value,
  })).reverse() || [];

  const title = METRIC_LABELS[metric] || metric.replace(/_/g, " ");
  // Using % for percentages
  const isPercentage = metric.includes("pct") || metric === "cpu_usage";

  return (
    <Card className="flex flex-col h-full">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>{title}</CardTitle>
            <CardDescription>Last {hours >= 24 ? `${hours / 24}d` : `${hours}h`} of data</CardDescription>
          </div>
          <div className="flex flex-wrap gap-1 justify-end max-w-[200px]">
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
      <CardContent className="flex-1 min-h-[300px]">
        {loadingHist ? (
          <div className="h-full w-full flex items-center justify-center p-4">
            <div className="h-[250px] w-full animate-pulse bg-muted rounded-md mt-4"></div>
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-full min-h-[250px] flex items-center justify-center text-muted-foreground border border-dashed rounded-md mt-4">
            No historical data for {title.toLowerCase()}
          </div>
        ) : (
          <div className="h-[250px] w-full mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: -20 }}>
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
                  tickFormatter={(value) => `${value}${isPercentage ? '%' : ''}`}
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}
                  labelStyle={{ color: "hsl(var(--foreground))", fontWeight: "bold" }}
                  itemStyle={{ color: "hsl(var(--primary))" }}
                  labelFormatter={(label, entries) => entries[0]?.payload.fullDate || label}
                  formatter={(value: any) => [`${value}${isPercentage ? '%' : ''}`, title]}
                />
                <Line 
                  type="monotone" 
                  dataKey="value" 
                  stroke="hsl(var(--primary))" 
                  strokeWidth={2} 
                  dot={false}
                  activeDot={{ r: 6, fill: "hsl(var(--primary))", stroke: "hsl(var(--background))", strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
