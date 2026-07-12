import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, Link, useNavigate } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Clock, XCircle, AlertTriangle, Trash2 } from "lucide-react";
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
import { Input } from "@/components/ui/input";
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
      await api.delete("/logs/bulk", { data: { log_ids: [parseInt(id!)] } });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["logs"] });
      setDeleteConfirmOpen(false);
      navigate("/dashboard/logs");
    },
  });

  if (isLoading) return <div className="p-10">Loading...</div>;
  if (!log) return <div className="p-10 text-destructive">Log not found</div>;

  const isFailed = log.status === "FAILED";
  const canAcknowledge = isFailed && !log.acknowledged && (user?.role === "admin" || user?.role === "operator");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="outline" size="icon" asChild>
          <Link to="/dashboard/logs"><ArrowLeft className="h-4 w-4" /></Link>
        </Button>
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Log Details: #{log.id}</h2>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-muted-foreground">{log.nas_id} • {log.job_name}</span>
            {log.status === "SUCCESS" && <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20"><CheckCircle2 className="w-3 h-3 mr-1" /> SUCCESS</Badge>}
            {log.status === "FAILED" && <Badge variant="outline" className="bg-rose-500/10 text-rose-500 border-rose-500/20"><XCircle className="w-3 h-3 mr-1" /> FAILED</Badge>}
            {log.status === "RUNNING" && <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20"><Clock className="w-3 h-3 mr-1" /> RUNNING</Badge>}
          </div>
        </div>
      </div>

      {isFailed && !log.acknowledged && (
        <div className="bg-rose-500/10 border border-rose-500/20 p-4 rounded-md flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-rose-500 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-rose-500 font-medium">Backup Failed</h4>
            <p className="text-sm text-rose-500/80 mt-1">{log.message || "No error message provided."}</p>
          </div>
          {canAcknowledge && (
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button variant="destructive" size="sm">Acknowledge</Button>
              </DialogTrigger>
              <DialogContent>
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
                            <Input placeholder="e.g., Network issue resolved, triggered manual backup" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <DialogFooter>
                      <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                      <Button type="submit" disabled={acknowledgeMutation.isPending}>
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
          <div>
            <h4 className="font-medium">Acknowledged</h4>
            <p className="text-sm text-muted-foreground mt-1">
              {log.remark ? `Remark: ${log.remark}` : "No remark provided."}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              At {log.acknowledged_at ? formatLongDateTimeWib(log.acknowledged_at) : "Unknown time"}
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Execution Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="font-medium text-muted-foreground">Started At</div>
                <div>{formatDateTimeWib(log.started_at)}</div>
              </div>
              <div>
                <div className="font-medium text-muted-foreground">Ended At</div>
                <div>{formatDateTimeWib(log.ended_at)}</div>
              </div>
              <div>
                <div className="font-medium text-muted-foreground">Duration</div>
                <div>{log.duration_seconds ? `${log.duration_seconds} seconds` : "-"}</div>
              </div>
              <div>
                <div className="font-medium text-muted-foreground">Engine</div>
                <div className="capitalize">{log.backup_engine}</div>
              </div>
              <div className="col-span-2">
                <div className="font-medium text-muted-foreground">Source Path</div>
                <div className="font-mono text-xs mt-1 p-1 bg-muted rounded">{log.source_path || "-"}</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Transfer Stats</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="font-medium text-muted-foreground">Total Size</div>
                <div>{log.total_size_bytes ? formatBytes(log.total_size_bytes) : "-"}</div>
              </div>
              <div>
                <div className="font-medium text-muted-foreground">Total Files</div>
                <div>{log.total_files || "-"}</div>
              </div>
              <div>
                <div className="font-medium text-muted-foreground">Changed Files</div>
                <div>{log.changed_file_count !== null ? log.changed_file_count : "-"}</div>
              </div>
              <div>
                <div className="font-medium text-muted-foreground">Errors</div>
                <div className={log.error_count > 0 ? "text-destructive font-bold" : ""}>
                  {log.error_count !== null ? log.error_count : "-"}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Raw Payload</CardTitle>
            <CardDescription>Full JSON data received from the NAS</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="p-4 rounded-md bg-muted text-xs font-mono overflow-x-auto">
              {log.raw_payload ? JSON.stringify(log.raw_payload, null, 2) : "No raw payload stored."}
            </pre>
          </CardContent>
        </Card>
      </div>

      {user?.role === "admin" && (
        <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm" className="text-destructive border-destructive/30 hover:bg-destructive/10 ml-auto self-start">
              <Trash2 className="mr-2 h-4 w-4" />
              Delete Log
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Confirm Delete</DialogTitle>
              <DialogDescription>
                Are you sure you want to permanently delete this backup log? This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteConfirmOpen(false)}>Cancel</Button>
              <Button variant="destructive" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
