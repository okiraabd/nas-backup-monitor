import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { api } from "@/lib/api";
import { formatDateTimeWib } from "@/lib/datetime";
import { Users as UsersIcon, ShieldAlert, Key, PlusCircle, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth";

const formSchema = z.object({
  username: z.string().min(3, "Username must be at least 3 characters").max(64),
  display_name: z.string().min(3, "Display name is required").max(128),
  role: z.enum(["admin", "service", "collector", "operator"]),
  password: z.string().max(128).optional(),
}).superRefine((data, ctx) => {
  if ((data.role === "admin" || data.role === "operator") && (!data.password || data.password.length < 6)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Password must be at least 6 characters for human accounts",
      path: ["password"],
    });
  }
});

export function Users() {
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [tokenResult, setTokenResult] = useState<{username: string, token: string} | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("ALL");
  const [deleteConfirm, setDeleteConfirm] = useState<{id: number, username: string} | null>(null);
  const [rotateConfirm, setRotateConfirm] = useState<{id: number, username: string} | null>(null);

  const { data: users, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const res = await api.get("/users");
      return res.data;
    },
    enabled: currentUser?.role === "admin",
  });

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      username: "",
      display_name: "",
      role: "operator",
      password: "",
    },
  });

  const selectedRole = form.watch("role");

  const generateToken = () => {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*";
    let token = "";
    for (let i = 0; i < 32; i++) {
      token += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return token;
  };

  const createMutation = useMutation({
    mutationFn: async (values: any) => {
      const res = await api.post("/users", values);
      return { user: res.data, password: values.password };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setCreateOpen(false);
      form.reset();
      if (data.user.role === "service" || data.user.role === "collector") {
        setTokenResult({ username: data.user.username, token: data.password });
      }
    },
  });

  const onSubmit = (values: z.infer<typeof formSchema>) => {
    const payload = { ...values };
    if (payload.role === "service" || payload.role === "collector") {
      payload.password = generateToken();
    }
    createMutation.mutate(payload);
  };

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/users/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setDeleteConfirm(null);
    },
  });

  const rotateMutation = useMutation({
    mutationFn: async ({ id, username }: { id: number, username: string }) => {
      const res = await api.post(`/users/${id}/rotate-token`);
      return { username, password: res.data.new_password };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setRotateConfirm(null);
      setTokenResult({ username: data.username, token: data.password });
    },
  });

  if (currentUser?.role !== "admin") {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-4">
        <ShieldAlert className="h-16 w-16 text-destructive" />
        <h2 className="text-2xl font-bold">Access Denied</h2>
        <p className="text-muted-foreground">Only administrators can manage users.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">User Management</h2>
          <p className="text-muted-foreground mt-2">
            Manage admin accounts, NAS service accounts, and collectors.
          </p>
        </div>
        
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button>
              <PlusCircle className="mr-2 h-4 w-4" />
              Add User
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New User</DialogTitle>
              <DialogDescription>
                Service accounts are used by NAS scripts. Collector accounts are used by the metric agent.
              </DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="username"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Username</FormLabel>
                      <FormControl>
                        <Input 
                          placeholder={
                            selectedRole === "service" ? "nas-new" :
                            selectedRole === "collector" ? "metrics-agent" : "john_doe"
                          } 
                          {...field} 
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="display_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Display Name</FormLabel>
                      <FormControl>
                        <Input 
                          placeholder={
                            selectedRole === "service" ? "New NAS Device" :
                            selectedRole === "collector" ? "Metrics Collector" : "John Doe"
                          } 
                          {...field} 
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="role"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Role</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select a role" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="admin">Admin</SelectItem>
                          <SelectItem value="operator">Operator</SelectItem>
                          <SelectItem value="service">Service (NAS)</SelectItem>
                          <SelectItem value="collector">Collector</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-muted-foreground mt-2">
                        {field.value === "admin" && "Full administrative access."}
                        {field.value === "operator" && "Read-only access for monitoring backups and logs."}
                        {field.value === "service" && "Used by NAS scripts to upload backup logs."}
                        {field.value === "collector" && "Used by the metrics agent to push hardware metrics."}
                      </p>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                {selectedRole === "admin" || selectedRole === "operator" ? (
                  <FormField
                    control={form.control}
                    name="password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Initial Password</FormLabel>
                        <FormControl><Input type="password" {...field} value={field.value || ""} /></FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                ) : (
                  <div className="bg-muted p-3 rounded-md border text-sm text-muted-foreground flex items-center gap-2">
                    <Key className="h-4 w-4 shrink-0" />
                    A highly secure 32-character token will be automatically generated and displayed after creation.
                  </div>
                )}
                <DialogFooter className="pt-4">
                  <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
                  <Button type="submit" disabled={createMutation.isPending}>
                    {createMutation.isPending ? "Creating..." : "Create User"}
                  </Button>
                </DialogFooter>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      <Dialog open={!!tokenResult} onOpenChange={(open) => !open && setTokenResult(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Password Generated</DialogTitle>
            <DialogDescription>
              Please copy this new password for <strong>{tokenResult?.username}</strong>. It will not be shown again.
              All existing active sessions/tokens for this user have been instantly revoked.
            </DialogDescription>
          </DialogHeader>
          <div className="bg-muted p-4 rounded-md font-mono text-center text-lg select-all">
            {tokenResult?.token}
          </div>
          <DialogFooter>
            <Button onClick={() => setTokenResult(null)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleteConfirm} onOpenChange={(open) => !open && setDeleteConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Delete User</DialogTitle>
            <DialogDescription>
              Are you sure you want to disable the account <strong>{deleteConfirm?.username}</strong>? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Cancel</Button>
            <Button variant="destructive" disabled={deleteMutation.isPending} onClick={() => {
              if (deleteConfirm) {
                deleteMutation.mutate(deleteConfirm.id);
              }
            }}>
              {deleteMutation.isPending ? "Deleting..." : "Disable User"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!rotateConfirm} onOpenChange={(open) => !open && setRotateConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Rotate Token</DialogTitle>
            <DialogDescription>
              Are you sure you want to generate a new password/token for <strong>{rotateConfirm?.username}</strong>? 
              <br/><br/>
              <span className="text-destructive font-medium">Warning:</span> All existing active sessions and scripts using the current token will instantly be unauthorized and must be updated with the new token.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRotateConfirm(null)}>Cancel</Button>
            <Button disabled={rotateMutation.isPending} onClick={() => {
              if (rotateConfirm) {
                rotateMutation.mutate({ id: rotateConfirm.id, username: rotateConfirm.username });
              }
            }}>
              {rotateMutation.isPending ? "Generating..." : "Generate New Token"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Card>
        <CardHeader className="pb-3 flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <UsersIcon className="h-5 w-5" />
            Registered Accounts
          </CardTitle>
          <div className="flex gap-4">
            <div className="w-56">
              <Input
                placeholder="Search username or name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <div className="w-40">
              <Select value={roleFilter} onValueChange={setRoleFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="All Roles" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">All Roles</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="service">Service</SelectItem>
                  <SelectItem value="collector">Collector</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Username</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Login</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="h-24 text-center">Loading...</TableCell>
                  </TableRow>
                ) : users?.filter((u: any) => 
                    u.is_active &&
                    (roleFilter === "ALL" || u.role === roleFilter) &&
                    (!searchQuery || 
                     u.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
                     u.display_name.toLowerCase().includes(searchQuery.toLowerCase())
                    )
                  ).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="h-32 text-center">
                      <div className="flex flex-col items-center justify-center text-muted-foreground">
                        <UsersIcon className="h-8 w-8 mb-2 opacity-20" />
                        <p>No active users found matching criteria.</p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  users?.filter((u: any) => 
                    u.is_active &&
                    (roleFilter === "ALL" || u.role === roleFilter) &&
                    (!searchQuery || 
                     u.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
                     u.display_name.toLowerCase().includes(searchQuery.toLowerCase())
                    )
                  ).map((user: any) => (
                    <TableRow key={user.id}>
                      <TableCell className="font-medium font-mono">{user.username}</TableCell>
                      <TableCell>{user.display_name}</TableCell>
                      <TableCell>
                        <Badge variant={user.role === 'admin' ? 'default' : user.role === 'service' ? 'secondary' : 'outline'}>
                          {user.role}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {user.is_active ? (
                          <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20">Active</Badge>
                        ) : (
                          <Badge variant="outline" className="text-muted-foreground">Inactive</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {user.last_login_at ? formatDateTimeWib(user.last_login_at, { seconds: false }) : "Never"}
                      </TableCell>
                      <TableCell className="text-right space-x-2">
                        {user.role === "service" && user.is_active && (
                          <Button 
                            variant="outline" 
                            size="sm" 
                            title="Rotate Password/Token"
                            onClick={() => setRotateConfirm({ id: user.id, username: user.username })}
                            disabled={rotateMutation.isPending}
                          >
                            <Key className="h-4 w-4" />
                          </Button>
                        )}
                        <Button 
                          variant="destructive" 
                          size="sm"
                          disabled={user.username === "admin" || deleteMutation.isPending || !user.is_active}
                          onClick={() => setDeleteConfirm({ id: user.id, username: user.username })}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
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
