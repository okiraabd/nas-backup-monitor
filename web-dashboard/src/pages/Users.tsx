import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { api } from "@/lib/api";
import { formatDateTimeWib } from "@/lib/datetime";
import { Users as UsersIcon, ShieldAlert, Key, PlusCircle, Trash2, RotateCcw, Eye, EyeOff, LockKeyhole, Copy, Check } from "lucide-react";

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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";
import { AxiosError } from "axios";
import { PageHeader } from "@/components/PageHeader";
import type { UserOut } from "@/lib/types";

const formSchema = z.object({
  username: z.string().min(3, "Username must be at least 3 characters").max(64),
  display_name: z.string().min(3, "Display name is required").max(128),
  role: z.enum(["admin", "service", "collector", "operator"]),
  password_method: z.enum(["manual", "generate"]),
  password: z.string().max(128).optional(),
}).superRefine((data, ctx) => {
  if (data.password_method === "manual" && (!data.password || data.password.length < 6)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Password must be at least 6 characters",
      path: ["password"],
    });
  }
});

const resetPasswordSchema = z
  .object({
    password: z.string().min(6, "Password must be at least 6 characters").max(128),
    confirm_password: z.string().min(1, "Confirm the new password"),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

export function Users() {
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [passwordResult, setPasswordResult] = useState<{username: string, password: string, sessionsRevoked: boolean} | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("ALL");
  const [deleteConfirm, setDeleteConfirm] = useState<{id: number, username: string} | null>(null);
  const [resetPasswordTarget, setResetPasswordTarget] = useState<{id: number, username: string, role: string} | null>(null);
  const [passwordMethod, setPasswordMethod] = useState<"manual" | "generate">("manual");
  const [resetPasswordError, setResetPasswordError] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [reactivateConfirm, setReactivateConfirm] = useState<{id: number, username: string} | null>(null);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");

  const { data: users, isLoading } = useQuery<UserOut[]>({
    queryKey: ["users", showInactive],
    queryFn: async () => {
      const res = await api.get("/users", { params: { include_inactive: showInactive } });
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
      password_method: "manual",
      password: "",
    },
  });

  const resetForm = useForm<z.infer<typeof resetPasswordSchema>>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: {
      password: "",
      confirm_password: "",
    },
  });

  const selectedRole = form.watch("role");
  const createPasswordMethod = form.watch("password_method");
  const resettingSelf = resetPasswordTarget?.id === currentUser?.id;

  const generatePassword = () => {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    const values = crypto.getRandomValues(new Uint32Array(20));
    return Array.from(values, (value) => chars[value % chars.length]).join("");
  };

  const createMutation = useMutation({
    mutationFn: async (values: z.infer<typeof formSchema>) => {
      const { password_method, ...payload } = values;
      const res = await api.post("/users", payload);
      return {
        user: res.data as UserOut,
        password: payload.password,
        passwordMethod: password_method,
      };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setCreateOpen(false);
      form.reset();
      if (data.passwordMethod === "generate") {
        setPasswordResult({ username: data.user.username, password: data.password ?? "", sessionsRevoked: false });
      }
    },
  });

  const onSubmit = (values: z.infer<typeof formSchema>) => {
    const payload = { ...values };
    if (payload.password_method === "generate") {
      payload.password = generatePassword();
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

  const reactivateMutation = useMutation({
    mutationFn: async (id: number) => {
      // Reactivate by sending a PATCH to update is_active
      await api.patch(`/users/${id}`, { is_active: true });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  const generatePasswordMutation = useMutation({
    mutationFn: async ({ id, username }: { id: number, username: string }) => {
      const res = await api.post(`/users/${id}/password/generate`);
      return { username, password: res.data.new_password };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setResetPasswordTarget(null);
      setCopied(false);
      setCopyError("");
      setPasswordResult({ username: data.username, password: data.password, sessionsRevoked: true });
    },
    onError: (err) => {
      const detail = err instanceof AxiosError ? err.response?.data?.detail : undefined;
      setResetPasswordError(detail || "Failed to generate a password.");
    },
  });

  const resetPasswordMutation = useMutation({
    mutationFn: async ({ id, password }: { id: number, password: string }) => {
      await api.patch(`/users/${id}/password`, { new_password: password });
    },
    onSuccess: (_data, variables) => {
      setResetPasswordTarget(null);
      resetForm.reset();
      setResetPasswordError("");
      if (variables.id === currentUser?.id) {
        localStorage.removeItem("token");
        window.location.href = "/login?passwordChanged=1";
        return;
      }
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (err) => {
      const detail = err instanceof AxiosError ? err.response?.data?.detail : undefined;
      setResetPasswordError(detail || "Failed to reset password.");
    },
  });

  const onResetPasswordSubmit = (values: z.infer<typeof resetPasswordSchema>) => {
    if (resetPasswordTarget) {
      resetPasswordMutation.mutate({ id: resetPasswordTarget.id, password: values.password });
    }
  };

  const handleCopyPassword = async () => {
    if (passwordResult?.password) {
      try {
        await navigator.clipboard.writeText(passwordResult.password);
        setCopyError("");
        setCopied(true);
      } catch {
        setCopied(false);
        setCopyError("Clipboard access failed. Select the password and copy it manually.");
      }
    }
  };

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
      <PageHeader
        className="gap-3 sm:gap-4"
        title="User Management"
        description="Manage admin accounts, NAS service accounts, and collectors."
        actions={
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
                <FormField
                  control={form.control}
                  name="password_method"
                  render={({ field }) => (
                    <FormItem className="space-y-3">
                      <FormLabel>Initial Password Method</FormLabel>
                      <FormControl>
                        <RadioGroup
                          value={field.value}
                          onValueChange={field.onChange}
                          className="flex flex-col space-y-2"
                        >
                          <div className="flex items-center space-x-2">
                            <RadioGroupItem value="manual" id="create-manual" />
                            <Label htmlFor="create-manual" className="font-normal cursor-pointer">Input initial password</Label>
                          </div>
                          <div className="flex items-center space-x-2">
                            <RadioGroupItem value="generate" id="create-generate" />
                            <Label htmlFor="create-generate" className="font-normal cursor-pointer">Generate random password</Label>
                          </div>
                        </RadioGroup>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                {createPasswordMethod === "manual" ? (
                  <FormField
                    control={form.control}
                    name="password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Initial Password</FormLabel>
                        <FormControl>
                          <Input type="password" placeholder="Minimum 6 characters" {...field} value={field.value || ""} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                ) : (
                  <div className="bg-muted p-3 rounded-md border text-sm text-muted-foreground flex items-center gap-2">
                    <Key className="h-4 w-4 shrink-0" />
                    A secure 20-character password will be generated and shown once after creation.
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
        }
      />

      <Dialog open={!!passwordResult} onOpenChange={() => undefined}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Password Generated</DialogTitle>
            <DialogDescription>
              Please copy this new password for <strong>{passwordResult?.username}</strong>. It will not be shown again.
              {passwordResult?.sessionsRevoked && " All existing active sessions/tokens for this user have been instantly revoked."}
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center gap-2 mt-2">
            <div className="bg-muted p-4 rounded-md font-mono text-center text-lg select-all flex-1">
              {passwordResult?.password}
            </div>
            <Button
              variant="outline"
              size="icon"
              className="h-14 w-14 shrink-0"
              onClick={handleCopyPassword}
              title="Copy to clipboard"
            >
              {copied ? <Check className="h-6 w-6 text-emerald-500" /> : <Copy className="h-6 w-6" />}
            </Button>
          </div>
          {copyError && <p className="text-sm text-destructive">{copyError}</p>}
          <DialogFooter>
            <Button
              onClick={() => {
                setPasswordResult(null);
                setCopied(false);
                setCopyError("");
              }}
            >
              I've saved it
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleteConfirm} onOpenChange={(open) => !open && setDeleteConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Delete / Disable User</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete or disable the account <strong>{deleteConfirm?.username}</strong>? 
              If the user has related logs or metric data, the account will be safely disabled (marked inactive) instead of being fully deleted to preserve history.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Cancel</Button>
            <Button variant="destructive" disabled={deleteMutation.isPending} onClick={() => {
              if (deleteConfirm) {
                deleteMutation.mutate(deleteConfirm.id);
              }
            }}>
              {deleteMutation.isPending ? "Processing..." : "Delete / Disable"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!reactivateConfirm} onOpenChange={(open) => !open && setReactivateConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Reactivate User</DialogTitle>
            <DialogDescription>
              Are you sure you want to reactivate the account <strong>{reactivateConfirm?.username}</strong>? 
              They will be able to log in or authenticate again.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setReactivateConfirm(null)}>Cancel</Button>
            <Button disabled={reactivateMutation.isPending} onClick={() => {
              if (reactivateConfirm) {
                reactivateMutation.mutate(reactivateConfirm.id);
                setReactivateConfirm(null);
              }
            }} className="bg-emerald-600 hover:bg-emerald-700 text-white">
              {reactivateMutation.isPending ? "Reactivating..." : "Reactivate User"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reset Password Dialog */}
      <Dialog
        open={!!resetPasswordTarget}
        onOpenChange={(open) => {
          if (!open) {
            setResetPasswordTarget(null);
            resetForm.reset();
            setResetPasswordError("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset Password</DialogTitle>
            <DialogDescription>
              Set a new password for <strong>{resetPasswordTarget?.username}</strong>{" "}
              (<span className="capitalize">{resetPasswordTarget?.role}</span>).
              <br /><br />
              <span className="text-destructive font-medium">Warning:</span>{" "}
              {resettingSelf
                ? "Your active sessions will be revoked and you will be signed out after saving."
                : "All active sessions for this user will be immediately revoked and they must log in again."}
            </DialogDescription>
          </DialogHeader>
          
          <Form {...resetForm}>
            <form onSubmit={(e) => {
              e.preventDefault();
              if (passwordMethod === "manual") {
                resetForm.handleSubmit(onResetPasswordSubmit)(e);
              } else if (!resettingSelf) {
                if (resetPasswordTarget) {
                  generatePasswordMutation.mutate({ id: resetPasswordTarget.id, username: resetPasswordTarget.username });
                }
              }
            }} className="space-y-4 py-2">
              {resetPasswordError && (
                <div className="text-sm text-destructive bg-destructive/10 rounded-md p-3">{resetPasswordError}</div>
              )}

              {resettingSelf ? (
                <div className="bg-muted p-3 rounded-md border text-sm text-muted-foreground flex items-center gap-2">
                  <Key className="h-4 w-4 shrink-0" />
                  Enter your new password manually to avoid losing access to your account.
                </div>
              ) : (
                <div className="space-y-3">
                  <Label className="text-sm font-medium">Password Method</Label>
                  <RadioGroup
                    value={passwordMethod}
                    onValueChange={(val) => setPasswordMethod(val as "manual" | "generate")}
                    className="flex flex-col space-y-2"
                  >
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="manual" id="manual" />
                      <Label htmlFor="manual" className="font-normal cursor-pointer">Input new password</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="generate" id="generate" />
                      <Label htmlFor="generate" className="font-normal cursor-pointer">Generate random password</Label>
                    </div>
                  </RadioGroup>
                </div>
              )}
              
              {passwordMethod === "manual" ? (
                <>
                  <FormField
                    control={resetForm.control}
                    name="password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>New Password</FormLabel>
                        <FormControl>
                          <Input
                            type="password"
                            placeholder="Minimum 6 characters"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={resetForm.control}
                    name="confirm_password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Confirm New Password</FormLabel>
                        <FormControl>
                          <Input
                            type="password"
                            placeholder="Enter the new password again"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </>
              ) : (
                <div className="bg-muted p-3 rounded-md border text-sm text-muted-foreground flex items-center gap-2">
                  <Key className="h-4 w-4 shrink-0" />
                  A secure 20-character password will be generated and shown once after confirmation.
                </div>
              )}
              
              <DialogFooter className="pt-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setResetPasswordTarget(null);
                    resetForm.reset();
                    setResetPasswordError("");
                  }}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={resetPasswordMutation.isPending || generatePasswordMutation.isPending}>
                  {(resetPasswordMutation.isPending || generatePasswordMutation.isPending) ? "Processing..." : (passwordMethod === "manual" ? "Save Password" : "Generate Password")}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <Card>
        <CardHeader className="pb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2">
            <UsersIcon className="h-5 w-5" />
            Registered Accounts
          </CardTitle>
          <div className="flex flex-col sm:flex-row gap-2 sm:gap-4 sm:items-center">
            <div className="w-full sm:w-56">
              <Input
                placeholder="Search username or name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <div className="flex gap-2 items-center">
              <div className="flex-1 sm:w-40">
                <Select value={roleFilter} onValueChange={setRoleFilter}>
                  <SelectTrigger>
                    <SelectValue placeholder="All Roles" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ALL">All Roles</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                    <SelectItem value="operator">Operator</SelectItem>
                    <SelectItem value="service">Service</SelectItem>
                    <SelectItem value="collector">Collector</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button
                variant={showInactive ? "secondary" : "outline"}
                size="sm"
                onClick={() => setShowInactive((v) => !v)}
                title={showInactive ? "Hide Inactive Users" : "Show Inactive Users"}
                className="shrink-0"
              >
                {showInactive ? <EyeOff className="h-4 w-4 sm:mr-1" /> : <Eye className="h-4 w-4 sm:mr-1" />}
                <span className="hidden sm:inline">{showInactive ? "Hide Inactive" : "Show Inactive"}</span>
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Username</TableHead>
                  <TableHead className="hidden md:table-cell">Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="hidden sm:table-cell">Last Login</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="h-24 text-center">Loading...</TableCell>
                  </TableRow>
                ) : users?.filter((u) => 
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
                        <p>No users found matching criteria.</p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  users?.filter((u) => 
                    (roleFilter === "ALL" || u.role === roleFilter) &&
                    (!searchQuery || 
                     u.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
                     u.display_name.toLowerCase().includes(searchQuery.toLowerCase())
                    )
                  ).map((user) => (
                    <TableRow key={user.id}>
                      <TableCell className="font-medium font-mono text-xs sm:text-sm">{user.username}</TableCell>
                      <TableCell className="hidden md:table-cell">{user.display_name}</TableCell>
                      <TableCell>
                        <Badge variant={user.role === 'admin' ? 'default' : user.role === 'operator' ? 'secondary' : 'outline'}>
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
                      <TableCell className="hidden sm:table-cell">
                        {user.last_login_at ? formatDateTimeWib(user.last_login_at, { seconds: false }) : "Never"}
                      </TableCell>
                      <TableCell className="text-right space-x-2">
                        {user.is_active && (
                          <Button
                            variant="outline"
                            size="sm"
                            title="Reset Password"
                            onClick={() => {
                              setResetPasswordTarget({ id: user.id, username: user.username, role: user.role });
                              setPasswordMethod(
                                user.id === currentUser?.id
                                  ? "manual"
                                  : (user.role === "service" || user.role === "collector") ? "generate" : "manual"
                              );
                            }}
                            disabled={resetPasswordMutation.isPending || generatePasswordMutation.isPending}
                          >
                            <LockKeyhole className="h-4 w-4" />
                          </Button>
                        )}
                        {!user.is_active ? (
                          <Button
                            variant="outline"
                            size="sm"
                            title="Reactivate User"
                            onClick={() => setReactivateConfirm({ id: user.id, username: user.username })}
                            disabled={reactivateMutation.isPending}
                          >
                            <RotateCcw className="h-4 w-4" />
                          </Button>
                        ) : (
                          <Button
                            variant="destructive"
                            size="sm"
                            disabled={user.username === "admin" || deleteMutation.isPending}
                            onClick={() => setDeleteConfirm({ id: user.id, username: user.username })}
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
