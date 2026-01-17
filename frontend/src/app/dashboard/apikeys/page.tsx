"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiKeysApi, type APIKey } from "@/lib/api";
import { Key, Plus, Trash2, Eye, EyeOff, Loader2, TestTube, Wifi } from "lucide-react";
import { cn } from "@/lib/utils";

export default function APIKeysPage() {
    const queryClient = useQueryClient();
    const [showForm, setShowForm] = useState(false);
    const [formData, setFormData] = useState({
        name: "",
        exchange_name: "binance",
        api_key: "",
        secret_key: "",
        is_testnet: true,
    });
    const [showSecrets, setShowSecrets] = useState<Record<number, boolean>>({});
    const [error, setError] = useState("");

    // Fetch API keys
    const { data: apiKeys = [], isLoading } = useQuery({
        queryKey: ["apikeys"],
        queryFn: () => apiKeysApi.list().then((res) => res.data),
    });

    // Create
    const createMutation = useMutation({
        mutationFn: () => apiKeysApi.create(formData),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["apikeys"] });
            setShowForm(false);
            setFormData({ name: "", exchange_name: "binance", api_key: "", secret_key: "", is_testnet: true });
            setError("");
        },
        onError: (err: any) => {
            setError(err.response?.data?.detail || "Failed to create API key");
        },
    });

    // Delete
    const deleteMutation = useMutation({
        mutationFn: (id: number) => apiKeysApi.delete(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["apikeys"] });
        },
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!formData.api_key || !formData.secret_key) {
            setError("API Key and Secret are required");
            return;
        }
        createMutation.mutate();
    };

    const handleDelete = (id: number) => {
        if (confirm("Are you sure you want to delete this API key?")) {
            deleteMutation.mutate(id);
        }
    };

    const toggleSecret = (id: number) => {
        setShowSecrets((prev) => ({ ...prev, [id]: !prev[id] }));
    };

    return (
        <div className="space-y-6 animate-fadeIn max-w-3xl">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold">API Keys</h1>
                    <p className="text-muted-foreground mt-1">
                        Manage your exchange API credentials
                    </p>
                </div>
                <button
                    onClick={() => setShowForm(!showForm)}
                    className={cn(
                        "flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium transition-all",
                        showForm
                            ? "bg-slate-500/10 text-slate-500"
                            : "bg-primary text-primary-foreground hover:bg-primary/90"
                    )}
                >
                    <Plus className={cn("w-5 h-5 transition-transform", showForm && "rotate-45")} />
                    {showForm ? "Cancel" : "Add Key"}
                </button>
            </div>

            {/* Security Disclaimer */}
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-5">
                <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                        <Key className="w-5 h-5 text-amber-500" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-amber-500">⚠️ Important: API Key Security</h3>
                        <ul className="text-sm text-muted-foreground mt-2 space-y-1">
                            <li>• API keys must be enabled <strong>ONLY for trading</strong></li>
                            <li>• <strong>DO NOT enable</strong> deposit, withdrawal, or transfer permissions</li>
                            <li>• Enable <strong>IP whitelist</strong> if your exchange supports it</li>
                            <li>• Your keys are encrypted and stored securely</li>
                        </ul>
                        <p className="text-xs text-muted-foreground mt-3 italic">
                            CryptoBot is not responsible for losses resulting from incorrect API key configurations
                            or excessive permissions granted to them.
                        </p>
                    </div>
                </div>
            </div>

            {/* Add Form */}
            {showForm && (
                <div className="bg-card rounded-2xl border border-border p-6 animate-fadeIn">
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="md:col-span-2">
                                <label className="block text-sm font-medium text-muted-foreground mb-2">
                                    Account Name
                                </label>
                                <input
                                    type="text"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                                    placeholder="e.g. My Trading Account, Binance Main"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-muted-foreground mb-2">
                                    Exchange
                                </label>
                                <select
                                    value={formData.exchange_name}
                                    onChange={(e) => setFormData({ ...formData, exchange_name: e.target.value })}
                                    className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                                >
                                    <option value="binance">Binance</option>
                                    <option value="bybit">Bybit</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-muted-foreground mb-2">
                                    Network
                                </label>
                                <div className="flex gap-2">
                                    <button
                                        type="button"
                                        onClick={() => setFormData({ ...formData, is_testnet: true })}
                                        className={cn(
                                            "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all",
                                            formData.is_testnet
                                                ? "bg-amber-500 text-white"
                                                : "bg-muted text-muted-foreground hover:text-foreground"
                                        )}
                                    >
                                        <TestTube className="w-4 h-4" />
                                        Testnet
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setFormData({ ...formData, is_testnet: false })}
                                        className={cn(
                                            "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all",
                                            !formData.is_testnet
                                                ? "bg-emerald-500 text-white"
                                                : "bg-muted text-muted-foreground hover:text-foreground"
                                        )}
                                    >
                                        <Wifi className="w-4 h-4" />
                                        Mainnet
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-muted-foreground mb-2">
                                API Key
                            </label>
                            <input
                                type="text"
                                value={formData.api_key}
                                onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                                className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50 font-mono text-sm"
                                placeholder="Enter your API key"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-muted-foreground mb-2">
                                Secret Key
                            </label>
                            <input
                                type="password"
                                value={formData.secret_key}
                                onChange={(e) => setFormData({ ...formData, secret_key: e.target.value })}
                                className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50 font-mono text-sm"
                                placeholder="Enter your secret key"
                            />
                        </div>

                        {error && (
                            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-sm">
                                {error}
                            </div>
                        )}

                        <button
                            type="submit"
                            disabled={createMutation.isPending}
                            className="w-full py-3 px-4 rounded-xl bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                            {createMutation.isPending ? (
                                <>
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    Saving...
                                </>
                            ) : (
                                "Save API Key"
                            )}
                        </button>
                    </form>
                </div>
            )}

            {/* Keys List */}
            <div className="space-y-4">
                {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                    </div>
                ) : apiKeys.length === 0 ? (
                    <div className="bg-card rounded-2xl border border-border p-12 text-center">
                        <Key className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                        <h3 className="text-lg font-semibold mb-2">No API Keys</h3>
                        <p className="text-muted-foreground">
                            Add your exchange API keys to start trading
                        </p>
                    </div>
                ) : (
                    apiKeys.map((key) => (
                        <div
                            key={key.id}
                            className="bg-card rounded-2xl border border-border p-6 flex items-center justify-between"
                        >
                            <div className="flex items-center gap-4">
                                <div
                                    className={cn(
                                        "w-12 h-12 rounded-xl flex items-center justify-center",
                                        key.is_testnet ? "bg-amber-500/10" : "bg-emerald-500/10"
                                    )}
                                >
                                    {key.is_testnet ? (
                                        <TestTube className="w-6 h-6 text-amber-500" />
                                    ) : (
                                        <Wifi className="w-6 h-6 text-emerald-500" />
                                    )}
                                </div>
                                <div>
                                    <div className="flex items-center gap-2">
                                        <span className="font-semibold">{key.name || key.exchange_name}</span>
                                        <span
                                            className={cn(
                                                "px-2 py-0.5 rounded-full text-xs font-medium",
                                                key.is_testnet
                                                    ? "bg-amber-500/10 text-amber-500"
                                                    : "bg-emerald-500/10 text-emerald-500"
                                            )}
                                        >
                                            {key.is_testnet ? "Test" : "Live"}
                                        </span>
                                    </div>
                                    <p className="text-sm text-muted-foreground mt-1">
                                        {key.exchange_name.toUpperCase()} • {key.api_key_masked}
                                    </p>
                                </div>
                            </div>

                            <button
                                onClick={() => handleDelete(key.id)}
                                className="p-2 rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 transition-colors"
                            >
                                <Trash2 className="w-5 h-5" />
                            </button>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
