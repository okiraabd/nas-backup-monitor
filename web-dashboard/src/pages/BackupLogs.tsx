import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDateTimeWib, jakartaDateToUtcRange } from "@/lib/datetime";
import { Link, useSearchParams } from "react-router-dom";
import { Eye, CheckCircle2, XCircle, History, X, RefreshCw, Trash2 } from "lucide-react";

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
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export function BackupLogs() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialDate = searchParams.get("date") || "";

  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<string>("ALL");
  const [nasId, setNasId] = useState("ALL");
  const [jobName, setJobName] = useState("");
  const [dateFilter, setDateFilter] = useState(initialDate);
  const [autoRefresh, setAutoRefresh] = useState("0");
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [bulkDateFrom, setBulkDateFrom] = useState("");
  const [bulkDateTo, setBulkDateTo] = useState("");
  const pageSize = 10;
  const dateFromUrl = searchParams.get("date") || "";
  const refetchInterval = autoRefresh !== "0" ? parseInt(autoRefresh) * 1000 : false;
  const queryClient = useQueryClient();

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

  const { data, isLoading, isFetching } = useQuery({
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
    mutationFn: async ({ dateFrom, dateTo }: { dateFrom: string; dateTo: string }) => {
      const payload: any = {};
      if (dateFrom) {
        const from = jakartaDateToUtcRange(dateFrom);
        if (from) payload.date_from = from.date_from;
      }
      if (dateTo) {
        const to = jakartaDateToUtcRange(dateTo);
        if (to) payload.date_to = to.date_to;
      }
      const res = await api.delete("/logs/bulk", { data: payload });
      return res.data;
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["logs"] });
      setBulkDeleteOpen(false);
      setBulkDateFrom("");
      setBulkDateTo("");
      alert(`✅ ${result.deleted_count} log records deleted.`);
    },
  });

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
        <div className="flex items-center gap-2">
          <Select value={autoRefresh} onValueChange={setAutoRefresh}>
            <SelectTrigger className="w-36">
              <SelectValue placeholder="Auto Refresh" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="0">Auto Refresh: Off</SelectItem>
              <SelectItem value="10">Every 10s</SelectItem>
              <SelectItem value="30">Every 30s</SelectItem>
              <SelectItem value="60">Every 1m</SelectItem>
              <SelectItem value="300">Every 5m</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={handleManualRefresh}
            disabled={isFetching}
            title="Refresh Now"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setBulkDeleteOpen(true)}
            title="Delete Logs by Period"
            className="text-destructive border-destructive/30 hover:bg-destructive/10"
          >
            <Trash2 className="h-4 w-4 mr-1" />
            Delete by Period
          </Button>
        </div>
      </div>

      {/* Bulk Delete Dialog */}
      <Dialog open={bulkDeleteOpen} onOpenChange={(open) => {
        setBulkDeleteOpen(open);
        if (!open) { setBulkDateFrom(""); setBulkDateTo(""); }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Logs by Period</DialogTitle>
            <DialogDescription>
              Permanently delete all backup logs within the selected date range.
              <br /><br />
              <span className="text-destructive font-medium">⚠️ Warning:</span> This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-1.5">
              <label className="text-sm font-medium" htmlFor="bulk-date-from">From Date</label>
              <Input
                id="bulk-date-from"
                type="date"
                value={bulkDateFrom}
                onChange={(e) => setBulkDateFrom(e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <label className="text-sm font-medium" htmlFor="bulk-date-to">To Date</label>
              <Input
                id="bulk-date-to"
                type="date"
                value={bulkDateTo}
                onChange={(e) => setBulkDateTo(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkDeleteOpen(false)}>Cancel</Button>
            <Button
              variant="destructive"
              disabled={(!bulkDateFrom && !bulkDateTo) || bulkDeleteMutation.isPending}
              onClick={() => bulkDeleteMutation.mutate({ dateFrom: bulkDateFrom, dateTo: bulkDateTo })}
            >
              {bulkDeleteMutation.isPending ? "Deleting..." : "Delete Logs"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>


      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center gap-4">
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
                    <TableCell colSpan={6} className="h-24 text-center">
                      Loading...
                    </TableCell>
                  </TableRow>
                ) : data?.items?.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="h-32 text-center">
                      <div className="flex flex-col items-center justify-center text-muted-foreground">
                        <History className="h-8 w-8 mb-2 opacity-20" />
                        <p>No backup logs found.</p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  data?.items?.map((log: any) => (
                    <TableRow key={log.id}>
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
