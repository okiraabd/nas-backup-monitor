import { useState, useEffect } from "react";
import { useQuery, useQueryClient, useIsFetching } from "@tanstack/react-query";
import { Server, Activity, Cpu, MemoryStick, HardDrive, Clock } from "lucide-react";
import { api } from "@/lib/api";
import { formatDateTimeWib, formatTimeWib } from "@/lib/datetime";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatBytes } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TIMEFRAME_OPTIONS } from "@/lib/constants";
import { AutoRefreshControl } from "@/components/AutoRefreshControl";
import { PageHeader } from "@/components/PageHeader";
import { MetricAreaChart } from "@/components/MetricAreaChart";
import type { NasListResponse, SourceSnapshot, MetricHistory } from "@/lib/types";

const METRIC_LABELS: Record<string, string> = {
  cpu_usage: "CPU Usage",
  ram_used_pct: "Memory Usage",
  disk_used_pct: "Disk Usage",
};

function formatUptimeSeconds(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";

  const totalSeconds = Math.max(0, Math.floor(value));
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

export function MonitorNas() {
  const [selectedNas, setSelectedNas] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState<number>(10000);
  const queryClient = useQueryClient();

  const { data: nasList, isLoading: loadingList, dataUpdatedAt } = useQuery<NasListResponse>({
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
    if (nasList?.items?.length && !selectedNas) {
      setSelectedNas(nasList.items[0].source_id);
    }
  }, [nasList, selectedNas]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="NAS Monitoring"
        description="Real-time metrics and health status of all registered NAS endpoints."
        actions={
          <div className="flex items-center gap-2">
            <AutoRefreshControl
              className="mr-2"
              valueMs={autoRefresh}
              onChangeMs={setAutoRefresh}
              onRefresh={handleRefresh}
              isFetching={isFetching}
              lastUpdatedAt={dataUpdatedAt}
            />
            <Select
              value={selectedNas || ""}
              onValueChange={setSelectedNas}
              disabled={loadingList || nasList?.items?.length === 0}
            >
              <SelectTrigger className="w-full sm:w-64 bg-background">
                <Server className="w-4 h-4 mr-2 text-muted-foreground" />
                <SelectValue placeholder="Select NAS Device" />
              </SelectTrigger>
              <SelectContent>
                {nasList?.items?.map((nas) => (
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
        }
      />

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
  const [hours, setHours] = useState(1);

  const { data: snapshot, isLoading: loadingSnap } = useQuery<SourceSnapshot>({
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
    if (m.value != null) return `${m.value}${m.unit ? m.unit : ''}`;
    if (m.text != null) return m.text;
    return "N/A";
  };

  const getMetricNumber = (name: string) => {
    const value = snapshot?.metrics?.[name]?.value;
    return value === null || value === undefined ? null : Number(value);
  };

  return (
    <div className="space-y-6">
      {/* Key metric cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
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
            {snapshot?.metrics?.storage_used_bytes?.value != null && snapshot?.metrics?.storage_total_bytes?.value != null && (
              <p className="text-xs text-muted-foreground mt-2">
                {formatBytes(snapshot.metrics.storage_used_bytes.value)} / {formatBytes(snapshot.metrics.storage_total_bytes.value)}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">System Uptime</p>
              {loadingSnap ? (
                <div className="h-8 w-20 animate-pulse bg-muted rounded-md"></div>
              ) : (
                <h3 className="text-2xl font-bold">{formatUptimeSeconds(getMetricNumber("system_uptime"))}</h3>
              )}
            </div>
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
              <Clock className="h-5 w-5 text-primary" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Full-Width Charts */}
      <div className="grid grid-cols-1 gap-6">
        <MetricChart nasId={nasId} metric="cpu_usage" hours={hours} setHours={setHours} autoRefresh={autoRefresh} />
        <MetricChart nasId={nasId} metric="ram_used_pct" hours={hours} setHours={setHours} autoRefresh={autoRefresh} />
      </div>
    </div>
  );
}

function MetricChart({ nasId, metric, hours, setHours, autoRefresh }: { nasId: string, metric: string, hours: number, setHours: (h: number) => void, autoRefresh: number }) {
  const { data: history, isLoading: loadingHist } = useQuery<MetricHistory>({
    queryKey: ["nas", nasId, "history", metric, hours],
    queryFn: async () => {
      const res = await api.get(`/monitor/nas/${nasId}/history`, { params: { metric, hours } });
      return res.data;
    },
    refetchInterval: autoRefresh === 0 ? false : autoRefresh,
  });

  const chartData = history?.points?.map((p) => ({
    time: formatTimeWib(p.collected_at),
    fullDate: formatDateTimeWib(p.collected_at),
    value: p.value ?? null,
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
            <MetricAreaChart
              data={chartData}
              label={title}
              isPercentage={isPercentage}
              gradientId={`colorValue-${metric}`}
              marginLeft={-20}
              showActiveDot
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
