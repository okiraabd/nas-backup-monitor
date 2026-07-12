import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDateTimeWib, jakartaDateToUtcRange } from "@/lib/datetime";
import { Link, useSearchParams } from "react-router-dom";
import { Eye, CheckCircle2, XCircle, History, X, RefreshCw, Trash2, Clock } from "lucide-react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useAuth } from "@/lib/auth";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Checkbox } from "@/components/ui/checkbox";

const bulkPeriodSchema = z.object({
  date_from: z.string().min(1, "Start date is required"),
  date_to: z.string().min(1, "End date is required"),
}).refine((data) => data.date_from <= data.date_to, {
  message: "Start date must be on or before end date",
  path: ["date_from"],
});

export function BackupLogs() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [searchParams, setSearchParams] = useSearchParams();
  const initialDate = searchParams.get("date") || "";

  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<string>("ALL");
  const [nasId, setNasId] = useState("ALL");
  const [jobName, setJobName] = useState("");
  const [dateFilter, setDateFilter] = useState(initialDate);
  const [autoRefresh, setAutoRefresh] = useState("10");
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [selectedLogs, setSelectedLogs] = useState<Set<number>>(new Set());
  const [deleteConfirm, setDeleteConfirm] = useState<{ id?: number, bulk?: boolean, period?: { date_from: string, date_to: string } } | null>(null);
  
  const pageSize = 10;
  const dateFromUrl = searchParams.get("date") || "";
  const refetchInterval = autoRefresh !== "0" ? parseInt(autoRefresh) * 1000 : false;
  const queryClient = useQueryClient();

  const periodForm = useForm<z.infer<typeof bulkPeriodSchema>>({
    resolver: zodResolver(bulkPeriodSchema),
    defaultValues: {
      date_from: "",
      date_to: "",
    },
  });

  const { data: nasList } = useQuery({
    queryKey: ["nas-list"],
    queryFn: async () => {
      const res = await api.get("/monitor/nas");
      return res.data;
    },
  });

  useEffect(() => {
    // If URL changes from outside, update state
    setDateFilter(dateFromUrl);
  }, [dateFromUrl]);

  const clearDateFilter = () => {
    setDateFilter("");
    searchParams.delete("date");
    setSearchParams(searchParams);
    setPage(1);
  };

  const { data, isLoading, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ["logs", page, status, nasId, jobName, dateFilter],
    queryFn: async () => {
      const params: any = { page, page_size: pageSize };
      if (status !== "ALL") params.status = status;
      if (nasId !== "ALL") params.nas_id = nasId;
      if (jobName) params.job_name = jobName;
      if (dateFilter) {
        // Date input is a local Jakarta day; API still receives UTC bounds.
        const range = jakartaDateToUtcRange(dateFilter);
        if (range) {
          params.date_from = range.date_from;
          params.date_to = range.date_to;
        }
      }
      
      const res = await api.get("/logs", { params });
      return res.data;
    },
    refetchInterval,
  });

  const handleManualRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["logs", page, status, nasId, jobName, dateFilter] });
  };

  const bulkDeleteMutation = useMutation({
    mutationFn: async (payload: { log_ids?: number[]; date_from?: string; date_to?: string }) => {
      const apiPayload: any = {};
      if (payload.log_ids) apiPayload.log_ids = payload.log_ids;
      if (payload.date_from) {
        const from = jakartaDateToUtcRange(payload.date_from);
        if (from) apiPayload.date_from = from.date_from;
      }
      if (payload.date_to) {
        const to = jakartaDateToUtcRange(payload.date_to);
        if (to) apiPayload.date_to = to.date_to;
      }
      const res = await api.delete("/logs/bulk", { data: apiPayload });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["logs"] });
      setSelectedLogs(new Set());
      setDeleteConfirm(null);
    },
  });

  const onPeriodSubmit = (values: z.infer<typeof bulkPeriodSchema>) => {
    setBulkDeleteOpen(false);
    setDeleteConfirm({ period: { date_from: values.date_from, date_to: values.date_to } });
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "SUCCESS":
        return <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20"><CheckCircle2 className="w-3 h-3 mr-1"/> SUCCESS</Badge>;
      case "FAILED":
        return <Badge variant="outline" className="bg-rose-500/10 text-rose-500 border-rose-500/20"><XCircle className="w-3 h-3 mr-1"/> FAILED</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Backup Logs</h2>
          <p className="text-muted-foreground mt-2">
            History of all backup jobs from your NAS devices.
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
              disabled={isFetching}
              title="Refresh Now"
            >
              <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>
      </div>

      {/* Confirm Delete Dialog */}
      <Dialog open={!!deleteConfirm} onOpenChange={(open) => !open && setDeleteConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Delete</DialogTitle>
            <DialogDescription>
              {deleteConfirm?.period 
                ? `Are you sure you want to permanently delete all logs from ${deleteConfirm.period.date_from} to ${deleteConfirm.period.date_to}?`
                : deleteConfirm?.bulk 
                  ? `Are you sure you want to delete ${selectedLogs.size} selected logs?` 
                  : 'Are you sure you want to delete this log?'
              }
              {" "}This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Cancel</Button>
            <Button variant="destructive" disabled={bulkDeleteMutation.isPending} onClick={() => {
              if (deleteConfirm?.period) {
                bulkDeleteMutation.mutate(deleteConfirm.period);
              } else if (deleteConfirm?.bulk) {
                bulkDeleteMutation.mutate({ log_ids: Array.from(selectedLogs) });
              } else if (deleteConfirm?.id) {
                bulkDeleteMutation.mutate({ log_ids: [deleteConfirm.id] });
              }
            }}>
              {bulkDeleteMutation.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Delete Period Dialog */}
      <Dialog open={bulkDeleteOpen} onOpenChange={(open) => {
        setBulkDeleteOpen(open);
        if (!open) periodForm.reset();
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Logs by Period</DialogTitle>
            <DialogDescription>
              Permanently delete all backup logs within the selected date range.
            </DialogDescription>
          </DialogHeader>
          <Form {...periodForm}>
            <form onSubmit={periodForm.handleSubmit(onPeriodSubmit)} className="space-y-4 py-2">
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={periodForm.control}
                  name="date_from"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Start Date</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} onClick={(e) => e.currentTarget.showPicker && e.currentTarget.showPicker()} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={periodForm.control}
                  name="date_to"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>End Date</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} onClick={(e) => e.currentTarget.showPicker && e.currentTarget.showPicker()} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <DialogFooter className="pt-4">
                <Button type="button" variant="outline" onClick={() => setBulkDeleteOpen(false)}>Cancel</Button>
                <Button type="submit" variant="destructive" disabled={bulkDeleteMutation.isPending}>
                  {bulkDeleteMutation.isPending ? "Deleting..." : "Delete Logs"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
            <div>
              <CardTitle>Backup Log Records</CardTitle>
              <CardDescription>View all backup history, statuses, and performance metrics</CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {isAdmin && selectedLogs.size > 0 && (
                <Button 
                  variant="destructive" 
                  size="sm"
                  onClick={() => setDeleteConfirm({ bulk: true })}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete Selected ({selectedLogs.size})
                </Button>
              )}
              {isAdmin && (
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => setBulkDeleteOpen(true)}
                >
                  <Trash2 className="mr-2 h-4 w-4 text-destructive" />
                  Delete by Period
                </Button>
              )}
            </div>
          </div>
          
          <div className="flex flex-wrap items-center gap-3">
            <div className="w-56">
              <Select value={nasId} onValueChange={(val) => { setNasId(val); setPage(1); }}>
                <SelectTrigger>
                  <SelectValue placeholder="All NAS Devices" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">All NAS Devices</SelectItem>
                  {nasList?.items?.map((n: any) => (
                    <SelectItem key={n.source_id} value={n.source_id}>
                      {n.source_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="w-48">
              <Input 
                placeholder="Search Job Name..." 
                value={jobName}
                onChange={(e) => {
                  setJobName(e.target.value);
                  setPage(1);
                }}
              />
            </div>
            <div className="w-48">
              <Select value={status} onValueChange={(val) => { setStatus(val); setPage(1); }}>
                <SelectTrigger>
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">All Statuses</SelectItem>
                  <SelectItem value="SUCCESS">Success</SelectItem>
                  <SelectItem value="FAILED">Failed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="w-48 relative">
              <Input
                type="date"
                value={dateFilter}
                onChange={(e) => {
                  setDateFilter(e.target.value);
                  if (e.target.value) {
                    searchParams.set("date", e.target.value);
                  } else {
                    searchParams.delete("date");
                  }
                  setSearchParams(searchParams);
                  setPage(1);
                }}
                onClick={(e) => e.currentTarget.showPicker && e.currentTarget.showPicker()}
                className="pr-8 text-sm"
              />
              {dateFilter && (
                <button 
                  onClick={clearDateFilter}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  {isAdmin && (
                    <TableHead className="w-[50px]">
                      <Checkbox 
                        checked={data?.items?.length > 0 && selectedLogs.size === data.items.length}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            setSelectedLogs(new Set(data.items.map((l: any) => l.id)));
                          } else {
                            setSelectedLogs(new Set());
                          }
                        }}
                      />
                    </TableHead>
                  )}
                  <TableHead>Time</TableHead>
                  <TableHead>NAS ID</TableHead>
                  <TableHead>Job Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={isAdmin ? 7 : 6} className="h-24 text-center">
                      Loading...
                    </TableCell>
                  </TableRow>
                ) : data?.items?.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={isAdmin ? 7 : 6} className="h-32 text-center">
                      <div className="flex flex-col items-center justify-center text-muted-foreground">
                        <History className="h-8 w-8 mb-2 opacity-20" />
                        <p>{(nasId !== "ALL" || status !== "ALL" || jobName !== "" || dateFilter !== "") 
                          ? "No backup logs found matching criteria." 
                          : "No backup logs generated yet."}
                        </p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  data?.items?.map((log: any) => (
                    <TableRow key={log.id}>
                      {isAdmin && (
                        <TableCell>
                          <Checkbox 
                            checked={selectedLogs.has(log.id)}
                            onCheckedChange={(checked) => {
                              const newSet = new Set(selectedLogs);
                              if (checked) newSet.add(log.id);
                              else newSet.delete(log.id);
                              setSelectedLogs(newSet);
                            }}
                          />
                        </TableCell>
                      )}
                      <TableCell className="font-medium whitespace-nowrap">
                        {formatDateTimeWib(log.created_at)}
                      </TableCell>
                      <TableCell>{log.nas_id}</TableCell>
                      <TableCell>{log.job_name}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getStatusBadge(log.status)}
                          {log.status === "FAILED" && log.acknowledged && (
                            <Badge variant="secondary" className="text-xs">Ack'd</Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {log.duration_seconds ? `${log.duration_seconds}s` : "-"}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="icon" asChild>
                          <Link to={`/dashboard/logs/${log.id}`}>
                            <Eye className="h-4 w-4" />
                          </Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
          
          {/* Pagination */}
          {data && data.total > 0 && (
            <div className="flex items-center justify-between space-x-2 py-4">
              <div className="text-sm text-muted-foreground">
                Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, data.total)} of {data.total} entries
              </div>
              <div className="flex space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page * pageSize >= data.total}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
