import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Server, Activity, Cpu, MemoryStick, HardDrive } from "lucide-react";
import { api } from "@/lib/api";
import { formatDateTimeWib, formatTimeWib } from "@/lib/datetime";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatBytes } from "@/lib/utils";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export function MonitorNas() {
  const [selectedNas, setSelectedNas] = useState<string | null>(null);

  const { data: nasList, isLoading: loadingList } = useQuery({
    queryKey: ["nas-list"],
    queryFn: async () => {
      const res = await api.get("/monitor/nas");
      return res.data;
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">NAS Monitoring</h2>
        <p className="text-muted-foreground mt-2">
          Real-time metrics and health status of all registered NAS endpoints.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-12">
        {/* Sidebar list of NAS */}
        <Card className="md:col-span-4 h-fit">
          <CardHeader>
            <CardTitle>NAS Devices</CardTitle>
            <CardDescription>Select a device to view detailed metrics</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {loadingList ? (
              <div className="p-4 space-y-2">
                {[1, 2, 3].map(i => <div key={i} className="h-14 animate-pulse bg-muted rounded-md" />)}
              </div>
            ) : nasList?.items?.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">No NAS devices found.</div>
            ) : (
              <div className="flex flex-col divide-y">
                {nasList?.items?.map((nas: any) => (
                  <button
                    key={nas.source_id}
                    onClick={() => setSelectedNas(nas.source_id)}
                    className={`flex items-center justify-between p-4 hover:bg-muted/50 transition-colors text-left ${selectedNas === nas.source_id ? 'bg-muted/80 border-l-4 border-l-primary' : ''}`}
                  >
                    <div>
                      <div className="font-medium flex items-center gap-2">
                        <Server className="h-4 w-4" />
                        {nas.source_id}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        Last seen: {formatTimeWib(nas.last_collected_at, { seconds: true, suffix: true })}
                      </div>
                    </div>
                    <div>
                      {nas.status === "fresh" && <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20">Fresh</Badge>}
                      {nas.status === "stale" && <Badge variant="outline" className="bg-amber-500/10 text-amber-500 border-amber-500/20">Stale</Badge>}
                      {nas.status === "offline" && <Badge variant="outline" className="bg-rose-500/10 text-rose-500 border-rose-500/20">Offline</Badge>}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Details and Charts */}
        <div className="md:col-span-8 space-y-6">
          {selectedNas ? (
            <NasDetailView nasId={selectedNas} />
          ) : (
            <Card className="h-full min-h-[400px] flex items-center justify-center border-dashed">
              <CardContent className="text-center text-muted-foreground pt-6">
                <Activity className="h-12 w-12 mx-auto mb-4 opacity-20" />
                <p>Select a NAS endpoint from the list to view its metrics history.</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function NasDetailView({ nasId }: { nasId: string }) {
  const [metric, setMetric] = useState("cpu_usage");
  const [hours, setHours] = useState(24);

  const TIMEFRAME_OPTIONS = [
    { label: "1h", value: 1 },
    { label: "6h", value: 6 },
    { label: "12h", value: 12 },
    { label: "24h", value: 24 },
    { label: "7d", value: 168 },
    { label: "30d", value: 720 },
  ];

  const { data: snapshot, isLoading: loadingSnap } = useQuery({
    queryKey: ["nas", nasId, "snapshot"],
    queryFn: async () => {
      const res = await api.get(`/monitor/nas/${nasId}`);
      return res.data;
    },
  });

  const { data: history, isLoading: loadingHist } = useQuery({
    queryKey: ["nas", nasId, "history", metric, hours],
    queryFn: async () => {
      const res = await api.get(`/monitor/nas/${nasId}/history`, { params: { metric, hours } });
      return res.data;
    },
  });

  // Transform history data for Recharts
  const chartData = history?.points?.map((p: any) => ({
    time: formatTimeWib(p.collected_at),
    fullDate: formatDateTimeWib(p.collected_at),
    value: p.value,
  })).reverse() || []; // Reverse so oldest is first, newest on right

  const getMetricValue = (name: string) => {
    if (!snapshot?.metrics || !snapshot.metrics[name]) return "N/A";
    const m = snapshot.metrics[name];
    if (m.value !== null) return `${m.value}${m.unit ? m.unit : ''}`;
    if (m.text !== null) return m.text;
    return "N/A";
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <Card className={`cursor-pointer transition-colors ${metric === 'cpu_usage' ? 'border-primary shadow-sm' : 'hover:border-primary/50'}`} onClick={() => setMetric("cpu_usage")}>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">CPU Usage</p>
              <h3 className="text-2xl font-bold">{loadingSnap ? "..." : getMetricValue("cpu_usage")}</h3>
            </div>
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
              <Cpu className="h-5 w-5 text-primary" />
            </div>
          </CardContent>
        </Card>
        
        <Card className={`cursor-pointer transition-colors ${metric === 'ram_used_pct' ? 'border-primary shadow-sm' : 'hover:border-primary/50'}`} onClick={() => setMetric("ram_used_pct")}>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">Memory</p>
              <h3 className="text-2xl font-bold">{loadingSnap ? "..." : getMetricValue("ram_used_pct")}</h3>
            </div>
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
              <MemoryStick className="h-5 w-5 text-primary" />
            </div>
          </CardContent>
        </Card>
        
        <Card className={`cursor-pointer transition-colors ${metric === 'disk_used_pct' ? 'border-primary shadow-sm' : 'hover:border-primary/50'}`} onClick={() => setMetric("disk_used_pct")}>
          <CardContent className="p-4 flex flex-col justify-between h-full min-h-[100px]">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">Disk Usage</p>
                <h3 className="text-2xl font-bold">{loadingSnap ? "..." : getMetricValue("disk_used_pct")}</h3>
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

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="capitalize">{metric.replace(/_/g, " ")} History</CardTitle>
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
            <div className="h-[300px] flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          ) : chartData.length === 0 ? (
            <div className="h-[300px] flex items-center justify-center text-muted-foreground border border-dashed rounded-md">
              No historical data for {metric}
            </div>
          ) : (
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
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
                    tickFormatter={(value) => `${value}`}
                  />
                  <Tooltip 
                    contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}
                    labelStyle={{ color: "hsl(var(--foreground))", fontWeight: "bold" }}
                    itemStyle={{ color: "hsl(var(--primary))" }}
                    labelFormatter={(label, entries) => entries[0]?.payload.fullDate || label}
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
    </div>
  );
}
