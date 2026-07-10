import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDateTimeWib, jakartaDateToUtcRange } from "@/lib/datetime";
import { Link, useSearchParams } from "react-router-dom";
import { Eye, CheckCircle2, XCircle, Clock, History, X } from "lucide-react";

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

export function BackupLogs() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialDate = searchParams.get("date") || "";

  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<string>("ALL");
  const [nasId, setNasId] = useState("ALL");
  const [jobName, setJobName] = useState("");
  const [dateFilter, setDateFilter] = useState(initialDate);
  const pageSize = 10;
  const dateFromUrl = searchParams.get("date") || "";

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

  const { data, isLoading } = useQuery({
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
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "SUCCESS":
        return <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20"><CheckCircle2 className="w-3 h-3 mr-1"/> SUCCESS</Badge>;
      case "FAILED":
        return <Badge variant="outline" className="bg-rose-500/10 text-rose-500 border-rose-500/20"><XCircle className="w-3 h-3 mr-1"/> FAILED</Badge>;
      case "RUNNING":
        return <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20"><Clock className="w-3 h-3 mr-1"/> RUNNING</Badge>;
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
      </div>

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
                  <SelectItem value="RUNNING">Running</SelectItem>
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
