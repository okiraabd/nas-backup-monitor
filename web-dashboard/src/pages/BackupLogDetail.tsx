import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, Link, useNavigate } from "react-router-dom";
import { ArrowLeft, CheckCircle2, XCircle, AlertTriangle, Trash2 } from "lucide-react";
import { useState } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { api } from "@/lib/api";
import { formatBytes } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { formatDateTimeWib, formatLongDateTimeWib } from "@/lib/datetime";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";

const acknowledgeSchema = z.object({
  remark: z.string().min(1, "Remark is required").max(2000, "Remark is too long"),
});

export function BackupLogDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  const ackForm = useForm<z.infer<typeof acknowledgeSchema>>({
    resolver: zodResolver(acknowledgeSchema),
    defaultValues: {
      remark: "",
    },
  });

  const { data: log, isLoading } = useQuery({
    queryKey: ["log", id],
    queryFn: async () => {
      const res = await api.get(`/logs/${id}`);
      return res.data;
    },
  });

  const acknowledgeMutation = useMutation({
    mutationFn: async (values: z.infer<typeof acknowledgeSchema>) => {
      await api.patch(`/logs/${id}/acknowledge`, { remark: values.remark });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["log", id] });
      setDialogOpen(false);
      ackForm.reset();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const res = await api.delete("/logs/bulk", { data: { log_ids: [parseInt(id!)] } });
      return res.data;
    },
    onSuccess: (data) => {
      const deletedCount = data?.deleted_count ?? 0;
      queryClient.invalidateQueries({ queryKey: ["logs"] });
      setDeleteConfirmOpen(false);
      navigate("/dashboard/logs", {
        state: {
          deleteResult: `${deletedCount} backup log${deletedCount === 1 ? "" : "s"} deleted.`,
        },
      });
    },
  });

  if (isLoading) return <div className="p-10">Loading...</div>;
  if (!log) return <div className="p-10 text-destructive">Log not found</div>;

  const isFailed = log.status === "FAILED";
  const canAcknowledge = isFailed && !log.acknowledged && (user?.role === "admin" || user?.role === "operator");

  return (
    <div className="space-y-6 min-w-0">
      <div className="flex items-start sm:items-center gap-3 sm:gap-4">
        <Button variant="outline" size="icon" asChild className="shrink-0 mt-1 sm:mt-0">
          <Link to="/dashboard/logs"><ArrowLeft className="h-4 w-4" /></Link>
        </Button>
        <div className="min-w-0 flex-1">
          <h2 className="text-xl sm:text-2xl md:text-3xl font-bold tracking-tight break-words">Log Details: #{log.id}</h2>
          <div className="flex flex-wrap items-center gap-2 mt-1">
            <span className="text-muted-foreground text-sm sm:text-base break-all min-w-0">{log.nas_id} • {log.job_name}</span>
            {log.status === "SUCCESS" && <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20"><CheckCircle2 className="w-3 h-3 mr-1" /> SUCCESS</Badge>}
            {log.status === "FAILED" && <Badge variant="outline" className="bg-rose-500/10 text-rose-500 border-rose-500/20"><XCircle className="w-3 h-3 mr-1" /> FAILED</Badge>}
          </div>
        </div>
      </div>

      {isFailed && !log.acknowledged && (
        <div className="bg-rose-500/10 border border-rose-500/20 p-3 sm:p-4 rounded-md flex flex-col sm:flex-row sm:items-start gap-3">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <AlertTriangle className="h-5 w-5 text-rose-500 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <h4 className="text-rose-500 font-medium">Backup Failed</h4>
              <p className="text-sm text-rose-500/80 mt-1 break-words [overflow-wrap:anywhere]">{log.message || "No error message provided."}</p>
            </div>
          </div>
          {canAcknowledge && (
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button variant="destructive" size="sm" className="w-full sm:w-auto">Acknowledge</Button>
              </DialogTrigger>
              <DialogContent className="w-[calc(100vw-2rem)] max-h-[calc(100vh-2rem)] overflow-y-auto sm:max-w-lg">
                <DialogHeader>
                  <DialogTitle>Acknowledge Failure</DialogTitle>
                  <DialogDescription>
                    Mark this failure as reviewed. You must add a remark about how it was resolved.
                  </DialogDescription>
                </DialogHeader>
                <Form {...ackForm}>
                  <form onSubmit={ackForm.handleSubmit((v) => acknowledgeMutation.mutate(v))} className="space-y-4 py-4">
                    <FormField
                      control={ackForm.control}
                      name="remark"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Remark</FormLabel>
                          <FormControl>
                            <textarea
                              className="flex min-h-28 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                              placeholder="e.g., Network issue resolved, triggered manual backup"
                              {...field}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <DialogFooter className="gap-2 sm:gap-0">
                      <Button type="button" variant="outline" className="w-full sm:w-auto" onClick={() => setDialogOpen(false)}>Cancel</Button>
                      <Button type="submit" className="w-full sm:w-auto" disabled={acknowledgeMutation.isPending}>
                        {acknowledgeMutation.isPending ? "Saving..." : "Acknowledge"}
                      </Button>
                    </DialogFooter>
                  </form>
                </Form>
              </DialogContent>
            </Dialog>
          )}
        </div>
      )}

      {log.acknowledged && (
        <div className="bg-muted p-4 rounded-md flex items-start gap-3 border">
          <CheckCircle2 className="h-5 w-5 text-muted-foreground mt-0.5" />
          <div className="min-w-0">
            <h4 className="font-medium">Acknowledged</h4>
            <p className="text-sm text-muted-foreground mt-1 break-words [overflow-wrap:anywhere]">
              {log.remark ? `Remark: ${log.remark}` : "No remark provided."}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              At {log.acknowledged_at ? formatLongDateTimeWib(log.acknowledged_at) : "Unknown time"}
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2 min-w-0">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Execution Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div className="min-w-0">
                <div className="font-medium text-muted-foreground">Started At</div>
                <div className="break-words">{formatDateTimeWib(log.started_at)}</div>
              </div>
              <div className="min-w-0">
                <div className="font-medium text-muted-foreground">Ended At</div>
                <div className="break-words">{formatDateTimeWib(log.ended_at)}</div>
              </div>
              <div className="min-w-0">
                <div className="font-medium text-muted-foreground">Duration</div>
                <div className="break-words">{log.duration_seconds ? `${log.duration_seconds} seconds` : "-"}</div>
              </div>
              <div className="min-w-0">
                <div className="font-medium text-muted-foreground">Engine</div>
                <div className="capitalize break-words">{log.backup_engine}</div>
              </div>
              <div className="sm:col-span-2 min-w-0">
                <div className="font-medium text-muted-foreground">Source Path</div>
                <div className="font-mono text-xs mt-1 p-2 bg-muted rounded break-all [overflow-wrap:anywhere]">{log.source_path || "-"}</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Transfer Stats</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div className="min-w-0">
                <div className="font-medium text-muted-foreground">Total Size</div>
                <div className="break-words">{log.total_size_bytes ? formatBytes(log.total_size_bytes) : "-"}</div>
              </div>
              <div className="min-w-0">
                <div className="font-medium text-muted-foreground">Total Files</div>
                <div className="break-words">{log.total_files || "-"}</div>
              </div>
              <div className="min-w-0">
                <div className="font-medium text-muted-foreground">Changed Files</div>
                <div className="break-words">{log.changed_file_count != null ? log.changed_file_count : "-"}</div>
              </div>
              <div className="min-w-0">
                <div className="font-medium text-muted-foreground">Errors</div>
                <div className={log.error_count > 0 ? "text-destructive font-bold break-words" : "break-words"}>
                  {log.error_count != null ? log.error_count : "-"}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="md:col-span-2 min-w-0">
          <CardHeader>
            <CardTitle>Raw Payload</CardTitle>
            <CardDescription>Full JSON data received from the NAS</CardDescription>
          </CardHeader>
          <CardContent className="min-w-0">
            <pre className="max-h-[60vh] max-w-full overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-3 text-xs font-mono sm:p-4">{log.raw_payload ? JSON.stringify(log.raw_payload, null, 2) : "No raw payload stored."}</pre>
          </CardContent>
        </Card>
      </div>

      {user?.role === "admin" && (
        <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
          <div className="flex justify-end">
            <DialogTrigger asChild>
              <Button variant="outline" size="sm" className="w-full text-destructive border-destructive/30 hover:bg-destructive/10 sm:w-auto">
                <Trash2 className="mr-2 h-4 w-4" />
                Delete Log
              </Button>
            </DialogTrigger>
          </div>
          <DialogContent className="w-[calc(100vw-2rem)] sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>Confirm Delete</DialogTitle>
              <DialogDescription>
                Are you sure you want to permanently delete this backup log? This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2 sm:gap-0">
              <Button variant="outline" className="w-full sm:w-auto" onClick={() => setDeleteConfirmOpen(false)}>Cancel</Button>
              <Button variant="destructive" className="w-full sm:w-auto" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
