"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { twoFactorApi, TwoFactorSetupResponse } from "@/lib/api";
import { Shield, ShieldCheck, ShieldOff, Copy, Check, Loader2, AlertTriangle, Key } from "lucide-react";

interface TwoFactorSetupProps {
    onComplete?: () => void;
}

export function TwoFactorSetup({ onComplete }: TwoFactorSetupProps) {
    const queryClient = useQueryClient();
    const [step, setStep] = useState<"idle" | "setup" | "verify" | "backup">("idle");
    const [setupData, setSetupData] = useState<TwoFactorSetupResponse | null>(null);
    const [verifyCode, setVerifyCode] = useState("");
    const [error, setError] = useState("");
    const [copied, setCopied] = useState(false);

    // Get 2FA status
    const { data: status, isLoading: statusLoading } = useQuery({
        queryKey: ["2fa-status"],
        queryFn: () => twoFactorApi.getStatus().then((res) => res.data),
    });

    // Setup mutation
    const setupMutation = useMutation({
        mutationFn: () => twoFactorApi.setup(),
        onSuccess: (res) => {
            setSetupData(res.data);
            setStep("setup");
            setError("");
        },
        onError: (err: any) => {
            setError(err.response?.data?.detail || "Failed to setup 2FA");
        },
    });

    // Verify mutation
    const verifyMutation = useMutation({
        mutationFn: (code: string) => twoFactorApi.verify(code),
        onSuccess: () => {
            setStep("backup");
            queryClient.invalidateQueries({ queryKey: ["2fa-status"] });
        },
        onError: (err: any) => {
            setError(err.response?.data?.detail || "Invalid code");
        },
    });

    const handleStartSetup = () => {
        setError("");
        setupMutation.mutate();
    };

    const handleVerify = (e: React.FormEvent) => {
        e.preventDefault();
        if (verifyCode.length !== 6) {
            setError("Code must be 6 digits");
            return;
        }
        setError("");
        verifyMutation.mutate(verifyCode);
    };

    const copyBackupCodes = () => {
        if (setupData?.backup_codes) {
            navigator.clipboard.writeText(setupData.backup_codes.join("\n"));
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    const handleComplete = () => {
        setStep("idle");
        setSetupData(null);
        setVerifyCode("");
        onComplete?.();
    };

    if (statusLoading) {
        return (
            <div className="flex items-center justify-center p-6">
                <Loader2 className="w-6 h-6 animate-spin" />
            </div>
        );
    }

    // 2FA already enabled
    if (status?.enabled && step === "idle") {
        return (
            <div className="space-y-4">
                <div className="flex items-center gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                    <ShieldCheck className="w-6 h-6 text-emerald-500" />
                    <div>
                        <p className="font-medium text-emerald-500">2FA is enabled</p>
                        <p className="text-sm text-muted-foreground">Your account is protected</p>
                    </div>
                </div>
            </div>
        );
    }

    // Idle - show setup button
    if (step === "idle") {
        return (
            <div className="space-y-4">
                <div className="flex items-center gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
                    <ShieldOff className="w-6 h-6 text-amber-500" />
                    <div>
                        <p className="font-medium text-amber-500">2FA not enabled</p>
                        <p className="text-sm text-muted-foreground">Enable for extra security</p>
                    </div>
                </div>

                <button
                    onClick={handleStartSetup}
                    disabled={setupMutation.isPending}
                    className="w-full py-3 px-4 rounded-xl bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                >
                    {setupMutation.isPending ? (
                        <>
                            <Loader2 className="w-5 h-5 animate-spin" />
                            Setting up...
                        </>
                    ) : (
                        <>
                            <Shield className="w-5 h-5" />
                            Enable 2FA
                        </>
                    )}
                </button>

                {error && (
                    <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-sm">
                        {error}
                    </div>
                )}
            </div>
        );
    }

    // Setup step - show QR code
    if (step === "setup" && setupData) {
        return (
            <div className="space-y-4">
                <div className="text-center">
                    <h4 className="font-semibold mb-2">Scan QR Code</h4>
                    <p className="text-sm text-muted-foreground mb-4">
                        Use Google Authenticator or Authy to scan
                    </p>

                    <div className="inline-block p-4 bg-white rounded-xl mb-4">
                        <img
                            src={`data:image/png;base64,${setupData.qr_code_base64}`}
                            alt="2FA QR Code"
                            className="w-48 h-48"
                        />
                    </div>

                    <div className="text-xs text-muted-foreground mb-4">
                        Or enter manually: <code className="bg-muted px-2 py-1 rounded">{setupData.manual_entry_key}</code>
                    </div>
                </div>

                <form onSubmit={handleVerify} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            Enter 6-digit code from app
                        </label>
                        <input
                            type="text"
                            value={verifyCode}
                            onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                            className="w-full px-4 py-3 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50 text-center text-2xl tracking-widest font-mono"
                            placeholder="000000"
                            maxLength={6}
                            autoFocus
                        />
                    </div>

                    {error && (
                        <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-sm">
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={verifyCode.length !== 6 || verifyMutation.isPending}
                        className="w-full py-3 px-4 rounded-xl bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                        {verifyMutation.isPending ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                Verifying...
                            </>
                        ) : (
                            "Verify & Enable"
                        )}
                    </button>
                </form>
            </div>
        );
    }

    // Backup codes step
    if (step === "backup" && setupData) {
        return (
            <div className="space-y-4">
                <div className="flex items-center gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                    <ShieldCheck className="w-6 h-6 text-emerald-500" />
                    <div>
                        <p className="font-medium text-emerald-500">2FA Enabled!</p>
                        <p className="text-sm text-muted-foreground">Save your backup codes</p>
                    </div>
                </div>

                <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
                    <div className="flex items-start gap-2 mb-3">
                        <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                        <p className="text-sm text-amber-500">
                            Save these backup codes in a safe place. Each code can only be used once.
                        </p>
                    </div>

                    <div className="grid grid-cols-2 gap-2 mb-3">
                        {setupData.backup_codes.map((code, i) => (
                            <code key={i} className="px-3 py-2 bg-muted rounded-lg text-center text-sm font-mono">
                                {code}
                            </code>
                        ))}
                    </div>

                    <button
                        onClick={copyBackupCodes}
                        className="w-full py-2 px-4 rounded-lg bg-muted hover:bg-muted/80 transition-colors flex items-center justify-center gap-2 text-sm"
                    >
                        {copied ? (
                            <>
                                <Check className="w-4 h-4 text-emerald-500" />
                                Copied!
                            </>
                        ) : (
                            <>
                                <Copy className="w-4 h-4" />
                                Copy all codes
                            </>
                        )}
                    </button>
                </div>

                <button
                    onClick={handleComplete}
                    className="w-full py-3 px-4 rounded-xl bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-all"
                >
                    Done
                </button>
            </div>
        );
    }

    return null;
}
