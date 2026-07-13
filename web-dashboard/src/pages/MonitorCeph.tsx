import { useState } from "react";
import { useQuery, useQueryClient, useIsFetching } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { Database, CheckCircle2, XCircle, AlertCircle, HardDrive, Activity } from "lucide-react";
import { api } from "@/lib/api";
import { formatDateTimeWib, formatTimeWib } from "@/lib/datetime";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatBytes } from "@/lib/utils";
import { TIMEFRAME_OPTIONS } from "@/lib/constants";
import { AutoRefreshControl } from "@/components/AutoRefreshControl";
import { PageHeader } from "@/components/PageHeader";
import { MetricAreaChart } from "@/components/MetricAreaChart";
import type { SourceSnapshot, MetricHistory } from "@/lib/types";

export function MonitorCeph() {
  const metric = "storage_used_pct";
  const [hours, setHours] = useState(1);
  const [autoRefresh, setAutoRefresh] = useState<number>(10000);
  const queryClient = useQueryClient();

  const { data: snapshot, isLoading: loadingSnap, dataUpdatedAt } = useQuery<SourceSnapshot | null>({
    queryKey: ["ceph", "snapshot"],
    queryFn: async () => {
      try {
        const res = await api.get("/monitor/ceph");
        return res.data;
      } catch (err) {
        if (err instanceof AxiosError && err.response?.status === 404) return null;
        throw err;
      }
    },
    refetchInterval: autoRefresh === 0 ? false : autoRefresh,
  });

  const { data: history, isLoading: loadingHist } = useQuery<MetricHistory | { points: [] }>({
    queryKey: ["ceph", "history", metric, hours],
    queryFn: async () => {
      try {
        const res = await api.get("/monitor/ceph/history", { params: { metric, hours } });
        return res.data;
      } catch (err) {
        if (err instanceof AxiosError && err.response?.status === 404) return { points: [] };
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
  const osdIn = getMetric("osd_in")?.value;
  const osdTotal = getMetric("osd_total")?.value;
  const storageUsed = getMetric("storage_used_pct")?.value;
  const storageUsedBytes = getMetric("storage_used_bytes")?.value;
  const storageTotalBytes = getMetric("storage_total_bytes")?.value;

  const chartData = history?.points?.map((p) => ({
    time: formatTimeWib(p.collected_at),
    fullDate: formatDateTimeWib(p.collected_at),
    value: p.value ?? null,
  })) || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Ceph Storage"
        description="Monitor your object storage backend health and utilization."
        actions={
          <AutoRefreshControl
            valueMs={autoRefresh}
            onChangeMs={setAutoRefresh}
            onRefresh={handleRefresh}
            isFetching={isFetching}
            lastUpdatedAt={dataUpdatedAt}
          />
        }
      />

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
                      {osdUp !== undefined ? osdUp : "-"} <span className="text-lg font-normal text-muted-foreground">UP</span> / {osdIn !== undefined ? osdIn : "-"} <span className="text-lg font-normal text-muted-foreground">IN</span> / {osdTotal !== undefined ? osdTotal : "-"} <span className="text-lg font-normal text-muted-foreground">TOTAL</span>
                    </div>
                    {osdTotal !== undefined && ((osdUp !== undefined && osdUp !== osdTotal) || (osdIn !== undefined && osdIn !== osdTotal)) && (
                      <p className="text-xs text-rose-500 mt-2 flex items-center">
                        <AlertCircle className="h-3 w-3 mr-1" /> Warning: OSDs down or out
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
                      {storageUsedBytes != null && storageTotalBytes != null && (
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
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                  <CardTitle>Storage Utilization History</CardTitle>
                  <CardDescription>Last {hours >= 24 ? `${hours / 24}d` : `${hours}h`} of data</CardDescription>
                </div>
                <div className="flex flex-wrap gap-1">
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
                <div className="h-[250px] sm:h-[350px] w-full">
                  <MetricAreaChart
                    data={chartData}
                    label="Storage Used"
                    isPercentage
                    yDomain={[0, 100]}
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
