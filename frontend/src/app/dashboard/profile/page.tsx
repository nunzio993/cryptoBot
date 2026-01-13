"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { profileApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { User, MessageCircle, Lock, Copy, Check, Loader2, ExternalLink, Shield } from "lucide-react";
import { TwoFactorSetup } from "@/components/TwoFactorSetup";

export default function ProfilePage() {
    const { user } = useAuth();
    const queryClient = useQueryClient();

    const [copied, setCopied] = useState(false);
    const [passwordForm, setPasswordForm] = useState({
        old: "",
        new: "",
        confirm: "",
    });
    const [passwordError, setPasswordError] = useState("");
    const [passwordSuccess, setPasswordSuccess] = useState("");

    // Telegram code
    const { data: telegramData } = useQuery({
        queryKey: ["telegram-code"],
        queryFn: () => profileApi.getTelegramCode().then((res) => res.data),
    });

    // Change password
    const passwordMutation = useMutation({
        mutationFn: () => profileApi.changePassword(passwordForm.old, passwordForm.new),
        onSuccess: () => {
            setPasswordSuccess("Password updated successfully!");
            setPasswordError("");
            setPasswordForm({ old: "", new: "", confirm: "" });
        },
        onError: (err: any) => {
            setPasswordError(err.response?.data?.detail || "Failed to update password");
            setPasswordSuccess("");
        },
    });

    const handlePasswordSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setPasswordError("");
        setPasswordSuccess("");

        if (passwordForm.new !== passwordForm.confirm) {
            setPasswordError("Passwords do not match");
            return;
        }
        if (passwordForm.new.length < 6) {
            setPasswordError("Password must be at least 6 characters");
            return;
        }

        passwordMutation.mutate();
    };

    const copyCode = () => {
        if (telegramData?.code) {
            navigator.clipboard.writeText(`/link ${telegramData.code}`);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    return (
        <div className="space-y-6 animate-fadeIn max-w-2xl">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold">Profile</h1>
                <p className="text-muted-foreground mt-1">
                    Manage your account settings
                </p>
            </div>

            {/* User Info */}
            <div className="bg-card rounded-2xl border border-border p-6">
                <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-r from-blue-500 to-purple-500 flex items-center justify-center">
                        <User className="w-8 h-8 text-white" />
                    </div>
                    <div>
                        <h2 className="text-xl font-semibold">{user?.username}</h2>
                        <p className="text-muted-foreground">{user?.email}</p>
                    </div>
                </div>
            </div>

            {/* Two-Factor Authentication */}
            <div className="bg-card rounded-2xl border border-border p-6">
                <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                        <Shield className="w-5 h-5 text-emerald-500" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold">Two-Factor Authentication</h3>
                        <p className="text-sm text-muted-foreground">Add an extra layer of security</p>
                    </div>
                </div>

                <TwoFactorSetup />
            </div>

            {/* Telegram Link */}
            <div className="bg-card rounded-2xl border border-border p-6">
                <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                        <MessageCircle className="w-5 h-5 text-blue-500" />
                    </div>
                    <h3 className="text-lg font-semibold">Connect Telegram</h3>
                </div>

                <p className="text-muted-foreground mb-4">
                    Link your Telegram account to receive notifications for your trades.
                </p>

                <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground mb-4">
                    <li>
                        Open the bot:{" "}
                        {telegramData?.bot_link && (
                            <a
                                href={telegramData.bot_link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-primary hover:underline inline-flex items-center gap-1"
                            >
                                Open Telegram Bot
                                <ExternalLink className="w-3 h-3" />
                            </a>
                        )}
                    </li>
                    <li>Send this command to the bot:</li>
                </ol>

                <div className="flex items-center gap-2">
                    <code className="flex-1 px-4 py-3 rounded-xl bg-muted font-mono text-sm">
                        /link {telegramData?.code || "..."}
                    </code>
                    <button
                        onClick={copyCode}
                        className="p-3 rounded-xl bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                    >
                        {copied ? <Check className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
                    </button>
                </div>
            </div>

            {/* Change Password */}
            <div className="bg-card rounded-2xl border border-border p-6">
                <div className="flex items-center gap-3 mb-6">
                    <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center">
                        <Lock className="w-5 h-5 text-amber-500" />
                    </div>
                    <h3 className="text-lg font-semibold">Change Password</h3>
                </div>

                <form onSubmit={handlePasswordSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            Current Password
                        </label>
                        <input
                            type="password"
                            value={passwordForm.old}
                            onChange={(e) => setPasswordForm({ ...passwordForm, old: e.target.value })}
                            className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                            required
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            New Password
                        </label>
                        <input
                            type="password"
                            value={passwordForm.new}
                            onChange={(e) => setPasswordForm({ ...passwordForm, new: e.target.value })}
                            className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                            required
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            Confirm New Password
                        </label>
                        <input
                            type="password"
                            value={passwordForm.confirm}
                            onChange={(e) => setPasswordForm({ ...passwordForm, confirm: e.target.value })}
                            className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                            required
                        />
                    </div>

                    {passwordError && (
                        <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-sm">
                            {passwordError}
                        </div>
                    )}

                    {passwordSuccess && (
                        <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 text-sm">
                            {passwordSuccess}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={passwordMutation.isPending}
                        className="w-full py-3 px-4 rounded-xl bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                        {passwordMutation.isPending ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                Updating...
                            </>
                        ) : (
                            "Update Password"
                        )}
                    </button>
                </form>
            </div>
        </div>
    );
}
