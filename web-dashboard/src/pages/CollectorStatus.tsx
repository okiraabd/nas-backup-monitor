import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatLongDateTimeWib } from "@/lib/datetime";
import { Activity, Clock, ShieldAlert, CheckCircle2, Play, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function CollectorStatus() {
  const queryClient = useQueryClient();
  const [isTriggering, setIsTriggering] = useState(false);

  const { data: status, isLoading } = useQuery({
    queryKey: ["collector-status"],
    queryFn: async () => {
      const res = await api.get("/monitor/collector/status");
      return res.data;
    },
    refetchInterval: 2000, // auto refresh every 2s
  });

  const runMutation = useMutation({
    mutationFn: async () => {
      setIsTriggering(true);
      const res = await api.post("/monitor/collector/run-once");
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collector-status"] });
    },
    onSettled: () => {
      setIsTriggering(false);
    }
  });

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Collector Status</h2>
          <p className="text-muted-foreground mt-2">
            Status of the background metrics collection agent.
          </p>
        </div>
        <Button 
          onClick={() => runMutation.mutate()} 
          disabled={runMutation.isPending || isTriggering || status?.last_status === "RUNNING"}
        >
          {runMutation.isPending || status?.last_status === "RUNNING" ? (
            <><RefreshCw className="mr-2 h-4 w-4 animate-spin" /> Running...</>
          ) : (
            <><Play className="mr-2 h-4 w-4" /> Run Collector Now</>
          )}
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Latest Run Summary
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {isLoading ? (
              <div className="space-y-4 animate-pulse">
                <div className="h-6 bg-muted rounded w-1/3" />
                <div className="h-4 bg-muted rounded w-1/2" />
              </div>
            ) : !status || !status.last_status ? (
              <div className="text-muted-foreground border-dashed border-2 rounded-md p-8 text-center">
                No collector runs recorded yet.
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between border-b pb-4">
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-muted-foreground">Status</p>
                    <div className="flex items-center gap-2">
                      {status.last_status === "SUCCESS" && <CheckCircle2 className="h-5 w-5 text-emerald-500" />}
                      {status.last_status === "FAILED" && <ShieldAlert className="h-5 w-5 text-rose-500" />}
                      {status.last_status === "RUNNING" && <RefreshCw className="h-5 w-5 text-blue-500 animate-spin" />}
                      <span className="font-semibold text-lg">{status.last_status}</span>
                    </div>
                  </div>
                  <div className="space-y-1 text-right">
                    <p className="text-sm font-medium text-muted-foreground">Mode</p>
                    <Badge variant="secondary" className="uppercase">{status.is_mock ? 'MOCK' : 'LIVE'}</Badge>
                  </div>
                </div>

                <div className="space-y-1">
                  <p className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                    <Clock className="h-4 w-4" /> Timestamp
                  </p>
                  <p>{formatLongDateTimeWib(status.last_run_at)}</p>
                </div>

                <div className="space-y-1 border-t pt-4">
                  <p className="text-sm font-medium text-muted-foreground">Message</p>
                  <p className={`text-sm ${status.last_status === 'FAILED' ? 'text-rose-500' : ''}`}>
                    {status.message || "No message provided."}
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Endpoint Stats</CardTitle>
            <CardDescription>Number of sources processed in the last run</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-muted p-4 rounded-lg">
                <p className="text-sm font-medium text-muted-foreground mb-1">Total Sources</p>
                <p className="text-3xl font-bold">{status?.total_sources || 0}</p>
              </div>
              <div className="bg-muted p-4 rounded-lg">
                <p className="text-sm font-medium text-muted-foreground mb-1">Success</p>
                <p className="text-3xl font-bold text-emerald-500">{status?.success_sources || 0}</p>
              </div>
              <div className="bg-muted p-4 rounded-lg col-span-2">
                <p className="text-sm font-medium text-muted-foreground mb-1">Failed</p>
                <p className={`text-3xl font-bold ${status?.failed_sources > 0 ? 'text-rose-500' : ''}`}>
                  {status?.failed_sources || 0}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
