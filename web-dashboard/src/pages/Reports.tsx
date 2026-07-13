import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTimeWib } from "@/lib/datetime";
import { formatBytes } from "@/lib/utils";
import { FileText, Download, Trash2, PlusCircle, AlertCircle, Loader2, CheckCircle2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Checkbox } from "@/components/ui/checkbox";
import { PageHeader } from "@/components/PageHeader";
import { bulkPeriodSchema, type BulkPeriodValues } from "@/lib/schemas";
import type { NasListResponse, Report, BulkDeleteResponse } from "@/lib/types";

const generateReportSchema = z.object({
  date_from: z.string().min(1, "Start date is required"),
  date_to: z.string().min(1, "End date is required"),
  nas_id: z.string().optional(),
  custom_name: z.string().optional(),
}).refine(data => {
  return new Date(data.date_to) >= new Date(data.date_from);
}, {
  message: "End date must be on or after start date",
  path: ["date_to"],
});

export function Reports() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [searchFilter, setSearchFilter] = useState("");
  const [error, setError] = useState("");
  const [selectedReports, setSelectedReports] = useState<Set<number>>(new Set());
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<{ id?: number, bulk?: boolean, period?: { date_from: string, date_to: string } } | null>(null);
  const [bulkPeriodOpen, setBulkPeriodOpen] = useState(false);
  const [deleteResult, setDeleteResult] = useState("");

  const generateForm = useForm<z.infer<typeof generateReportSchema>>({
    resolver: zodResolver(generateReportSchema),
    defaultValues: {
      date_from: "",
      date_to: "",
      nas_id: "ALL",
      custom_name: "",
    },
  });

  const periodForm = useForm<BulkPeriodValues>({
    resolver: zodResolver(bulkPeriodSchema),
    defaultValues: {
      date_from: "",
      date_to: "",
    },
  });

  const { data: nasList } = useQuery<NasListResponse>({
    queryKey: ["nas-list"],
    queryFn: async () => {
      const res = await api.get("/monitor/nas");
      return res.data;
    },
  });

  const { data: reports, isLoading } = useQuery<Report[]>({
    queryKey: ["reports"],
    queryFn: async () => {
      const res = await api.get("/reports");
      return res.data;
    },
  });

  const generateMutation = useMutation({
    mutationFn: async (payload: {
      date_from: string;
      date_to: string;
      nas_id: string | null;
      custom_name?: string;
    }) => {
      const res = await api.post("/reports/generate", payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports"] });
      setDialogOpen(false);
      generateForm.reset();
      setError("");
    },
    onError: (err) => {
      const detail =
        err instanceof AxiosError ? err.response?.data?.detail : undefined;
      setError(detail || "Failed to generate report");
    },
  });

  const onGenerateSubmit = (values: z.infer<typeof generateReportSchema>) => {
    generateMutation.mutate({
      date_from: values.date_from,
      date_to: values.date_to,
      nas_id: values.nas_id === "ALL" ? null : values.nas_id ?? null,
      custom_name: values.custom_name?.trim() || undefined,
    });
  };

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/reports/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports"] });
      setDeleteConfirm(null);
      setDeleteResult("1 report deleted.");
    },
  });

  const bulkDeleteMutation = useMutation<BulkDeleteResponse, unknown, { report_ids?: number[], date_from?: string, date_to?: string }>({
    mutationFn: async (payload) => {
      const res = await api.delete(`/reports`, { data: payload });
      return res.data;
    },
    onSuccess: (data) => {
      const deletedCount = data?.deleted_count ?? 0;
      queryClient.invalidateQueries({ queryKey: ["reports"] });
      setDeleteConfirm(null);
      setSelectedReports(new Set());
      setBulkPeriodOpen(false);
      periodForm.reset();
      setDeleteResult(`${deletedCount} report${deletedCount === 1 ? "" : "s"} deleted.`);
    },
  });

  const onPeriodSubmit = (values: BulkPeriodValues) => {
    setBulkPeriodOpen(false);
    setDeleteConfirm({ period: { date_from: values.date_from, date_to: values.date_to } });
  };

  const downloadReport = (id: number) => {
    setDownloadingId(id);
    api.get(`/reports/${id}/download`, { responseType: 'blob' })
      .then((res) => {
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const link = document.createElement('a');
        link.href = url;
        const contentDisposition = res.headers['content-disposition'];
        let fileName = 'report.pdf';
        if (contentDisposition) {
          const fileNameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
          if (fileNameMatch && fileNameMatch.length === 2) fileName = fileNameMatch[1];
        }
        link.setAttribute('download', fileName);
        document.body.appendChild(link);
        link.click();
        link.remove();
      })
      .finally(() => {
        setDownloadingId(null);
      });
  };

  const isAdmin = user?.role === "admin";

  return (
    <div className="space-y-6">
      <PageHeader
        className="gap-3 sm:gap-4"
        title="Reports"
        description="Generate and download PDF reports of backup operations."
        actions={
        <Dialog open={dialogOpen} onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) {
            generateForm.reset();
            setError("");
          }
        }}>
          <DialogTrigger asChild>
            <Button>
              <PlusCircle className="mr-2 h-4 w-4" />
              Generate Report
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Generate New Report</DialogTitle>
              <DialogDescription>
                Create a comprehensive PDF report for a specific time period.
              </DialogDescription>
            </DialogHeader>
            <Form {...generateForm}>
              <form onSubmit={generateForm.handleSubmit(onGenerateSubmit)} className="grid gap-4 py-4">
                {error && (
                  <div className="bg-destructive/15 text-destructive p-3 rounded-md text-sm flex items-center gap-2">
                    <AlertCircle className="h-4 w-4" /> {error}
                  </div>
                )}
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={generateForm.control}
                    name="date_from"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Start Date *</FormLabel>
                        <FormControl>
                          <Input type="date" {...field} onClick={(e) => e.currentTarget.showPicker && e.currentTarget.showPicker()} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={generateForm.control}
                    name="date_to"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>End Date *</FormLabel>
                        <FormControl>
                          <Input type="date" {...field} onClick={(e) => e.currentTarget.showPicker && e.currentTarget.showPicker()} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={generateForm.control}
                  name="custom_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Report Name (Optional)</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. Q3_Monthly_Report" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={generateForm.control}
                  name="nas_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>NAS Source Filter (Optional)</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="All NAS Devices" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="ALL">All NAS Devices</SelectItem>
                          {nasList?.items?.map((n) => (
                            <SelectItem key={n.source_id} value={n.source_id}>
                              {n.source_id}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <DialogFooter className="pt-2">
                  <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                  <Button type="submit" disabled={generateMutation.isPending}>
                    {generateMutation.isPending ? "Generating..." : "Generate"}
                  </Button>
                </DialogFooter>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
        }
      />

      {deleteResult && (
        <div className="bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 p-3 rounded-md text-sm flex items-center justify-between gap-3">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            {deleteResult}
          </span>
          <button type="button" onClick={() => setDeleteResult("")} className="text-emerald-700/70 hover:text-emerald-700">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <Dialog open={!!deleteConfirm} onOpenChange={(open) => !open && setDeleteConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Delete</DialogTitle>
            <DialogDescription>
              {deleteConfirm?.period 
                ? `Are you sure you want to permanently delete all reports from ${deleteConfirm.period.date_from} to ${deleteConfirm.period.date_to}?`
                : deleteConfirm?.bulk 
                  ? `Are you sure you want to delete ${selectedReports.size} selected reports?` 
                  : 'Are you sure you want to delete this report?'
              }
              {" "}This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Cancel</Button>
            <Button variant="destructive" disabled={deleteMutation.isPending || bulkDeleteMutation.isPending} onClick={() => {
              if (deleteConfirm?.period) {
                bulkDeleteMutation.mutate(deleteConfirm.period);
              } else if (deleteConfirm?.bulk) {
                bulkDeleteMutation.mutate({ report_ids: Array.from(selectedReports) });
              } else if (deleteConfirm?.id) {
                deleteMutation.mutate(deleteConfirm.id);
              }
            }}>
              {(deleteMutation.isPending || bulkDeleteMutation.isPending) ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={bulkPeriodOpen} onOpenChange={(open) => {
        setBulkPeriodOpen(open);
        if (!open) periodForm.reset();
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Reports by Period</DialogTitle>
            <DialogDescription>
              Permanently delete all reports generated within a specific date range.
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
                <Button type="button" variant="outline" onClick={() => setBulkPeriodOpen(false)}>Cancel</Button>
                <Button type="submit" variant="destructive" disabled={bulkDeleteMutation.isPending}>
                  {bulkDeleteMutation.isPending ? "Deleting..." : "Delete Reports"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <Card>
        <CardHeader className="pb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <CardTitle>Generated Reports</CardTitle>
            <CardDescription>View and download previously generated reports</CardDescription>
          </div>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-4">
            {isAdmin && selectedReports.size > 0 && (
              <Button 
                variant="destructive" 
                size="sm"
                onClick={() => setDeleteConfirm({ bulk: true })}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete ({selectedReports.size})
              </Button>
            )}
            {isAdmin && (
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => setBulkPeriodOpen(true)}
              >
                <Trash2 className="mr-2 h-4 w-4 text-destructive" />
                <span className="hidden sm:inline">Delete by Period</span>
                <span className="sm:hidden">By Period</span>
              </Button>
            )}
            <div className="w-full sm:w-64">
              <Input
                placeholder="Search reports..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  {isAdmin && (
                    <TableHead className="w-[50px]">
                      <Checkbox 
                        checked={!!reports?.length && selectedReports.size === reports.length}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            setSelectedReports(new Set(reports?.map((r) => r.id)));
                          } else {
                            setSelectedReports(new Set());
                          }
                        }}
                      />
                    </TableHead>
                  )}
                  <TableHead>Filename</TableHead>
                  <TableHead className="hidden md:table-cell">Period</TableHead>
                  <TableHead className="hidden lg:table-cell">Filter</TableHead>
                  <TableHead className="hidden sm:table-cell">Generated At</TableHead>
                  <TableHead className="hidden md:table-cell">Size</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={isAdmin ? 7 : 6} className="h-24 text-center">Loading...</TableCell>
                  </TableRow>
                ) : reports?.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={isAdmin ? 7 : 6} className="h-32 text-center">
                      <div className="flex flex-col items-center justify-center text-muted-foreground">
                        <FileText className="h-8 w-8 mb-2 opacity-20" />
                        <p>No reports generated yet.</p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (() => {
                  const filteredReports = reports?.filter((r) => 
                    !searchFilter || r.filename.toLowerCase().includes(searchFilter.toLowerCase())
                  );

                  if (filteredReports?.length === 0) {
                    return (
                      <TableRow>
                        <TableCell colSpan={isAdmin ? 7 : 6} className="h-32 text-center">
                          <div className="flex flex-col items-center justify-center text-muted-foreground">
                            <FileText className="h-8 w-8 mb-2 opacity-20" />
                            <p>No reports found matching criteria.</p>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  }

                  return filteredReports?.map((report) => (
                    <TableRow key={report.id}>
                      {isAdmin && (
                        <TableCell>
                          <Checkbox 
                            checked={selectedReports.has(report.id)}
                            onCheckedChange={(checked) => {
                              const newSet = new Set(selectedReports);
                              if (checked) newSet.add(report.id);
                              else newSet.delete(report.id);
                              setSelectedReports(newSet);
                            }}
                          />
                        </TableCell>
                      )}
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                          <span className="truncate max-w-[150px] sm:max-w-none">{report.filename}</span>
                        </div>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">{report.date_from} to {report.date_to}</TableCell>
                      <TableCell className="hidden lg:table-cell">{report.nas_filter || <span className="text-muted-foreground">All NAS</span>}</TableCell>
                      <TableCell className="hidden sm:table-cell">{formatDateTimeWib(report.generated_at, { seconds: false })}</TableCell>
                      <TableCell className="hidden md:table-cell">{report.file_size_bytes ? formatBytes(report.file_size_bytes) : '-'}</TableCell>
                      <TableCell className="text-right space-x-2">
                        <Button 
                          variant="secondary" 
                          size="sm" 
                          onClick={() => downloadReport(report.id)}
                          disabled={downloadingId === report.id}
                        >
                          {downloadingId === report.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                        </Button>
                        {isAdmin && (
                          <Button 
                            variant="destructive" 
                            size="sm"
                            onClick={() => setDeleteConfirm({ id: report.id })}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ));
                })()}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
