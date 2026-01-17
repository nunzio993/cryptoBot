"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi, type AdminUser } from "@/lib/api";
import { formatDate, cn } from "@/lib/utils";
import { Users, Trash2, Edit2, Save, X, Loader2, Shield, ShieldOff } from "lucide-react";

export default function AdminPage() {
    const queryClient = useQueryClient();
    const [editingId, setEditingId] = useState<number | null>(null);
    const [editEmail, setEditEmail] = useState("");
    const [error, setError] = useState("");

    // Fetch users
    const { data: users = [], isLoading, error: fetchError } = useQuery({
        queryKey: ["admin-users"],
        queryFn: () => adminApi.listUsers().then((res) => res.data),
    });

    // Update mutation
    const updateMutation = useMutation({
        mutationFn: ({ id, email }: { id: number; email: string }) =>
            adminApi.updateUser(id, { email }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin-users"] });
            setEditingId(null);
            setEditEmail("");
        },
        onError: (err: any) => {
            setError(err.response?.data?.detail || "Failed to update user");
        },
    });

    // Delete mutation
    const deleteMutation = useMutation({
        mutationFn: (id: number) => adminApi.deleteUser(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin-users"] });
        },
        onError: (err: any) => {
            setError(err.response?.data?.detail || "Failed to delete user");
        },
    });

    const startEdit = (user: AdminUser) => {
        setEditingId(user.id);
        setEditEmail(user.email);
        setError("");
    };

    const cancelEdit = () => {
        setEditingId(null);
        setEditEmail("");
    };

    const saveEdit = (id: number) => {
        updateMutation.mutate({ id, email: editEmail });
    };

    const handleDelete = (user: AdminUser) => {
        if (confirm(`Are you sure you want to delete user "${user.username}"? This will delete all their orders, API keys, and data.`)) {
            deleteMutation.mutate(user.id);
        }
    };

    // Handle 403 error (not admin)
    if (fetchError) {
        const errorMsg = (fetchError as any)?.response?.data?.detail || "Access denied";
        return (
            <div className="flex flex-col items-center justify-center py-20">
                <Shield className="w-16 h-16 text-red-500 mb-4" />
                <h1 className="text-2xl font-bold text-red-500">Access Denied</h1>
                <p className="text-muted-foreground mt-2">{errorMsg}</p>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-fadeIn">
            {/* Header */}
            <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center">
                    <Users className="w-6 h-6 text-white" />
                </div>
                <div>
                    <h1 className="text-3xl font-bold">User Management</h1>
                    <p className="text-muted-foreground mt-1">
                        Manage all registered users
                    </p>
                </div>
            </div>

            {/* Error */}
            {error && (
                <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 flex items-center justify-between">
                    <span>{error}</span>
                    <button onClick={() => setError("")} className="p-1 hover:bg-red-500/20 rounded">
                        <X className="w-4 h-4" />
                    </button>
                </div>
            )}

            {/* Users Table */}
            <div className="bg-card rounded-2xl border border-border overflow-hidden">
                {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                    </div>
                ) : users.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground">
                        No users found
                    </div>
                ) : (
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-border bg-muted/50">
                                <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">ID</th>
                                <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Username</th>
                                <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Email</th>
                                <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">2FA</th>
                                <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Created</th>
                                <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {users.map((user) => {
                                const isEditing = editingId === user.id;
                                return (
                                    <tr key={user.id} className="border-b border-border/50 hover:bg-muted/30">
                                        <td className="py-3 px-4 text-sm font-mono">#{user.id}</td>
                                        <td className="py-3 px-4">
                                            <span className={cn(
                                                "font-medium",
                                                user.username === "admin" && "text-purple-500"
                                            )}>
                                                {user.username}
                                                {user.username === "admin" && (
                                                    <span className="ml-2 px-2 py-0.5 bg-purple-500/10 text-purple-500 text-xs rounded-full">
                                                        Admin
                                                    </span>
                                                )}
                                            </span>
                                        </td>
                                        <td className="py-3 px-4">
                                            {isEditing ? (
                                                <input
                                                    type="email"
                                                    value={editEmail}
                                                    onChange={(e) => setEditEmail(e.target.value)}
                                                    className="px-3 py-1.5 rounded-lg bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50 w-full max-w-xs"
                                                />
                                            ) : (
                                                <span className="text-sm">{user.email}</span>
                                            )}
                                        </td>
                                        <td className="py-3 px-4">
                                            {user.two_factor_enabled ? (
                                                <span className="flex items-center gap-1 text-emerald-500">
                                                    <Shield className="w-4 h-4" />
                                                    <span className="text-xs">Enabled</span>
                                                </span>
                                            ) : (
                                                <span className="flex items-center gap-1 text-muted-foreground">
                                                    <ShieldOff className="w-4 h-4" />
                                                    <span className="text-xs">Off</span>
                                                </span>
                                            )}
                                        </td>
                                        <td className="py-3 px-4 text-sm text-muted-foreground">
                                            {formatDate(user.created_at)}
                                        </td>
                                        <td className="py-3 px-4 text-right">
                                            <div className="flex items-center justify-end gap-2">
                                                {isEditing ? (
                                                    <>
                                                        <button
                                                            onClick={() => saveEdit(user.id)}
                                                            disabled={updateMutation.isPending}
                                                            className="p-2 rounded-lg bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 transition-colors"
                                                        >
                                                            {updateMutation.isPending ? (
                                                                <Loader2 className="w-4 h-4 animate-spin" />
                                                            ) : (
                                                                <Save className="w-4 h-4" />
                                                            )}
                                                        </button>
                                                        <button
                                                            onClick={cancelEdit}
                                                            className="p-2 rounded-lg bg-slate-500/10 text-slate-500 hover:bg-slate-500/20 transition-colors"
                                                        >
                                                            <X className="w-4 h-4" />
                                                        </button>
                                                    </>
                                                ) : (
                                                    <>
                                                        <button
                                                            onClick={() => startEdit(user)}
                                                            className="p-2 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                                                            title="Edit email"
                                                        >
                                                            <Edit2 className="w-4 h-4" />
                                                        </button>
                                                        {user.username !== "admin" && (
                                                            <button
                                                                onClick={() => handleDelete(user)}
                                                                className="p-2 rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 transition-colors"
                                                                title="Delete user"
                                                            >
                                                                <Trash2 className="w-4 h-4" />
                                                            </button>
                                                        )}
                                                    </>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}
