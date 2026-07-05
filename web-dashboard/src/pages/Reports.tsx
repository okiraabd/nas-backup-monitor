import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { format } from "date-fns";
import { FileText, Download, Trash2, PlusCircle, AlertCircle } from "lucide-react";

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
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function Reports() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [customName, setCustomName] = useState("");
  const [nasFilter, setNasFilter] = useState("ALL");
  const [searchFilter, setSearchFilter] = useState("");
  const [error, setError] = useState("");

  const { data: nasList } = useQuery({
    queryKey: ["nas-list"],
    queryFn: async () => {
      const res = await api.get("/monitor/nas");
      return res.data;
    },
  });

  const { data: reports, isLoading } = useQuery({
    queryKey: ["reports"],
    queryFn: async () => {
      const res = await api.get("/reports");
      return res.data;
    },
  });

  const generateMutation = useMutation({
    mutationFn: async (payload: any) => {
      const res = await api.post("/reports/generate", payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports"] });
      setDialogOpen(false);
      setDateFrom("");
      setDateTo("");
      setCustomName("");
      setNasFilter("ALL");
      setError("");
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "Failed to generate report");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/reports/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
  });

  const handleGenerate = () => {
    if (!dateFrom || !dateTo) {
      setError("Start date and End date are required");
      return;
    }
    generateMutation.mutate({
      date_from: dateFrom,
      date_to: dateTo,
      nas_id: nasFilter === "ALL" ? null : nasFilter,
      custom_name: customName.trim() || undefined,
    });
  };

  const downloadReport = (id: number) => {
    // We need to fetch it as blob to use the auth token, or open in new tab if token is in cookie.
    // Since we use Bearer token in header, we must fetch and create object URL.
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
      });
  };

  const isAdmin = user?.role === "admin";

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Reports</h2>
          <p className="text-muted-foreground mt-2">
            Generate and download PDF reports of backup operations.
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
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
            <div className="grid gap-4 py-4">
              {error && (
                <div className="bg-destructive/15 text-destructive p-3 rounded-md text-sm flex items-center gap-2">
                  <AlertCircle className="h-4 w-4" /> {error}
                </div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="dateFrom">Start Date *</Label>
                  <Input 
                    id="dateFrom" 
                    type="date" 
                    value={dateFrom} 
                    onChange={(e) => setDateFrom(e.target.value)} 
                    onClick={(e) => e.currentTarget.showPicker && e.currentTarget.showPicker()}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="dateTo">End Date *</Label>
                  <Input 
                    id="dateTo" 
                    type="date" 
                    value={dateTo} 
                    onChange={(e) => setDateTo(e.target.value)} 
                    onClick={(e) => e.currentTarget.showPicker && e.currentTarget.showPicker()}
                  />
                </div>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="customName">Report Name (Optional)</Label>
                <Input 
                  id="customName" 
                  placeholder="e.g. Q3_Monthly_Report" 
                  value={customName} 
                  onChange={(e) => setCustomName(e.target.value)} 
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="nasFilter">NAS Source Filter (Optional)</Label>
                <Select value={nasFilter} onValueChange={setNasFilter}>
                  <SelectTrigger id="nasFilter">
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
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleGenerate} disabled={generateMutation.isPending}>
                {generateMutation.isPending ? "Generating..." : "Generate"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader className="pb-3 flex flex-row items-center justify-between">
          <div>
            <CardTitle>Generated Reports</CardTitle>
            <CardDescription>View and download previously generated reports</CardDescription>
          </div>
          <div className="w-64">
            <Input
              placeholder="Search reports by filename..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
            />
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Filename</TableHead>
                  <TableHead>Period</TableHead>
                  <TableHead>Filter</TableHead>
                  <TableHead>Generated At</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="h-24 text-center">Loading...</TableCell>
                  </TableRow>
                ) : reports?.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="h-32 text-center">
                      <div className="flex flex-col items-center justify-center text-muted-foreground">
                        <FileText className="h-8 w-8 mb-2 opacity-20" />
                        <p>No reports generated yet.</p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  reports?.filter((r: any) => !searchFilter || r.filename.toLowerCase().includes(searchFilter.toLowerCase())).map((report: any) => (
                    <TableRow key={report.id}>
                      <TableCell className="font-medium flex items-center gap-2">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        {report.filename}
                      </TableCell>
                      <TableCell>{report.date_from} to {report.date_to}</TableCell>
                      <TableCell>{report.nas_filter || <span className="text-muted-foreground">All NAS</span>}</TableCell>
                      <TableCell>{format(new Date(report.generated_at), "yyyy-MM-dd HH:mm")}</TableCell>
                      <TableCell>{report.file_size_bytes ? `${(report.file_size_bytes / 1024).toFixed(1)} KB` : '-'}</TableCell>
                      <TableCell className="text-right space-x-2">
                        <Button 
                          variant="secondary" 
                          size="sm" 
                          onClick={() => downloadReport(report.id)}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                        {isAdmin && (
                          <Button 
                            variant="destructive" 
                            size="sm"
                            onClick={() => deleteMutation.mutate(report.id)}
                            disabled={deleteMutation.isPending}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
