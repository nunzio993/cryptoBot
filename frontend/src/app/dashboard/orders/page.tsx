"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ordersApi, apiKeysApi, type Order, type APIKey, type Holding } from "@/lib/api";
import { OrdersTable } from "@/components/OrdersTable";
import { AccountSelector } from "@/components/AccountSelector";
import { NewOrderForm } from "@/components/NewOrderForm";
import { Clock, TrendingUp, History, Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";

type Tab = "pending" | "executed" | "closed";

export default function OrdersPage() {
    // Load saved API key ID from localStorage
    const [selectedKeyId, setSelectedKeyId] = useState<number | null>(() => {
        if (typeof window !== "undefined") {
            const saved = localStorage.getItem("cryptobot_api_key_id");
            return saved ? parseInt(saved, 10) : null;
        }
        return null;
    });
    const [selectedKey, setSelectedKey] = useState<APIKey | null>(null);
    const [activeTab, setActiveTab] = useState<Tab>("pending");
    const [showNewOrder, setShowNewOrder] = useState(false);

    // Fetch API keys
    const { data: apiKeys = [] } = useQuery({
        queryKey: ["apiKeys"],
        queryFn: () => apiKeysApi.list().then((res) => res.data),
    });

    // Auto-select first API key if none selected
    useEffect(() => {
        if (!selectedKeyId && apiKeys.length > 0) {
            setSelectedKeyId(apiKeys[0].id);
            setSelectedKey(apiKeys[0]);
        } else if (selectedKeyId && apiKeys.length > 0) {
            const key = apiKeys.find(k => k.id === selectedKeyId);
            if (key) setSelectedKey(key);
        }
    }, [apiKeys, selectedKeyId]);

    // Save selected key to localStorage
    useEffect(() => {
        if (selectedKeyId) {
            localStorage.setItem("cryptobot_api_key_id", selectedKeyId.toString());
        }
    }, [selectedKeyId]);

    const handleSelectKey = (key: APIKey) => {
        setSelectedKeyId(key.id);
        setSelectedKey(key);
    };

    // Get network mode from selected key
    const networkMode = selectedKey?.is_testnet ? "Testnet" : "Mainnet";

    const queryClient = useQueryClient();

    // Fetch orders
    const { data: pendingOrders = [], isLoading: pendingLoading } = useQuery({
        queryKey: ["orders", "PENDING", selectedKeyId],
        queryFn: () => ordersApi.list("PENDING", networkMode, selectedKeyId || undefined).then((res) => res.data),
        refetchInterval: 5000, // 5 seconds for faster updates
        enabled: !!selectedKeyId,
    });

    const { data: executedOrders = [], isLoading: executedLoading } = useQuery({
        queryKey: ["orders", "EXECUTED", selectedKeyId],
        queryFn: () => ordersApi.list("EXECUTED", networkMode, selectedKeyId || undefined).then((res) => res.data),
        refetchInterval: 5000, // 5 seconds for faster updates
        enabled: !!selectedKeyId,
    });

    const { data: closedOrders = [], isLoading: closedLoading } = useQuery({
        queryKey: ["orders", "CLOSED", selectedKeyId],
        queryFn: () => ordersApi.list("CLOSED", networkMode, selectedKeyId || undefined).then((res) => res.data),
        enabled: !!selectedKeyId,
    });

    // Mutations
    const updateMutation = useMutation({
        mutationFn: ({ id, data }: { id: number; data: Partial<Order> }) =>
            ordersApi.update(id, data, networkMode),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["orders"] });
            queryClient.invalidateQueries({ queryKey: ["portfolio"] });
        },
    });

    const cancelMutation = useMutation({
        mutationFn: (id: number) => ordersApi.cancel(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["orders"] });
            queryClient.invalidateQueries({ queryKey: ["portfolio"] });
        },
    });

    const closeMutation = useMutation({
        mutationFn: (id: number) => ordersApi.close(id, networkMode),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["orders"] });
            queryClient.invalidateQueries({ queryKey: ["portfolio"] });
        },
    });

    const splitMutation = useMutation({
        mutationFn: ({ id, data }: { id: number; data: { split_quantity: number; tp1: number; sl1: number; tp2: number; sl2: number } }) =>
            ordersApi.split(id, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["orders"] });
            queryClient.invalidateQueries({ queryKey: ["portfolio"] });
        },
    });

    const handleUpdate = async (id: number, data: Partial<Order>) => {
        await updateMutation.mutateAsync({ id, data });
    };

    const handleCancel = async (id: number) => {
        if (confirm("Are you sure you want to cancel this order?")) {
            await cancelMutation.mutateAsync(id);
        }
    };

    const handleClose = async (id: number) => {
        if (confirm("Are you sure you want to close this position?")) {
            await closeMutation.mutateAsync(id);
        }
    };

    const handleSplit = async (id: number, data: { split_quantity: number; tp1: number; sl1: number; tp2: number; sl2: number }) => {
        await splitMutation.mutateAsync({ id, data });
    };

    const tabs = [
        { id: "pending" as Tab, label: "Pending", icon: Clock, count: pendingOrders.length },
        { id: "executed" as Tab, label: "Executed", icon: TrendingUp, count: executedOrders.length },
        { id: "closed" as Tab, label: "Closed", icon: History, count: closedOrders.length },
    ];

    const currentOrders =
        activeTab === "pending" ? pendingOrders :
            activeTab === "executed" ? executedOrders : closedOrders;

    const currentLoading =
        activeTab === "pending" ? pendingLoading :
            activeTab === "executed" ? executedLoading : closedLoading;

    return (
        <div className="space-y-6 animate-fadeIn">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold">Orders</h1>
                    <p className="text-muted-foreground mt-1">
                        Manage your trades and positions
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <AccountSelector
                        selectedKeyId={selectedKeyId}
                        onSelect={handleSelectKey}
                    />
                    <button
                        onClick={() => setShowNewOrder(!showNewOrder)}
                        className={cn(
                            "flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium transition-all",
                            showNewOrder
                                ? "bg-slate-500/10 text-slate-500"
                                : "bg-primary text-primary-foreground hover:bg-primary/90"
                        )}
                    >
                        {showNewOrder ? <X className="w-5 h-5" /> : <Plus className="w-5 h-5" />}
                        {showNewOrder ? "Close" : "New Trade"}
                    </button>
                </div>
            </div>

            {/* New Order Form */}
            {showNewOrder && selectedKey && (
                <NewOrderForm
                    networkMode={networkMode}
                    apiKeyId={selectedKey.id}
                    onSuccess={() => {
                        setShowNewOrder(false);
                        queryClient.invalidateQueries({ queryKey: ["orders"] });
                    }}
                />
            )}

            {/* Tabs */}
            <div className="flex gap-2 p-1 bg-muted/50 rounded-xl w-fit">
                {tabs.map((tab) => {
                    const Icon = tab.icon;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={cn(
                                "flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all",
                                activeTab === tab.id
                                    ? "bg-background shadow-sm"
                                    : "text-muted-foreground hover:text-foreground"
                            )}
                        >
                            <Icon className="w-4 h-4" />
                            {tab.label}
                            <span
                                className={cn(
                                    "px-2 py-0.5 rounded-full text-xs",
                                    activeTab === tab.id
                                        ? "bg-primary text-primary-foreground"
                                        : "bg-muted text-muted-foreground"
                                )}
                            >
                                {tab.count}
                            </span>
                        </button>
                    );
                })}
            </div>

            {/* Table */}
            <div className="bg-card rounded-2xl border border-border overflow-hidden">
                <OrdersTable
                    orders={currentOrders}
                    type={activeTab}
                    onUpdate={handleUpdate}
                    onCancel={handleCancel}
                    onClose={handleClose}
                    onSplit={handleSplit}
                    isLoading={currentLoading}
                />
            </div>

            {/* External Holdings */}
            {selectedKeyId && (
                <HoldingsSection apiKeyId={selectedKeyId} />
            )}
        </div>
    );
}

function HoldingsSection({ apiKeyId }: { apiKeyId: number }) {
    const [page, setPage] = useState(1);
    const [editingHolding, setEditingHolding] = useState<Holding | null>(null);
    const queryClient = useQueryClient();

    const { data: holdingsData, isLoading } = useQuery({
        queryKey: ["holdings", apiKeyId, page],
        queryFn: () => ordersApi.holdings(apiKeyId, page).then((res) => res.data),
        refetchInterval: 30000,
    });

    if (isLoading) {
        return (
            <div className="bg-card rounded-2xl border border-border p-6">
                <div className="h-40 flex items-center justify-center">
                    <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                </div>
            </div>
        );
    }

    if (!holdingsData || holdingsData.holdings.length === 0) {
        return null;
    }

    return (
        <div className="bg-card rounded-2xl border border-border overflow-hidden">
            <div className="p-4 border-b border-border flex items-center justify-between">
                <div>
                    <h3 className="font-semibold">External Holdings</h3>
                    <p className="text-sm text-muted-foreground">
                        Crypto bought outside this app • Total: ${holdingsData.total_value.toFixed(2)}
                    </p>
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full">
                    <thead className="bg-muted/50">
                        <tr>
                            <th className="text-left px-4 py-3 text-sm font-medium text-muted-foreground">Asset</th>
                            <th className="text-right px-4 py-3 text-sm font-medium text-muted-foreground">Quantity</th>
                            <th className="text-right px-4 py-3 text-sm font-medium text-muted-foreground">Price</th>
                            <th className="text-right px-4 py-3 text-sm font-medium text-muted-foreground">Value</th>
                            <th className="text-right px-4 py-3 text-sm font-medium text-muted-foreground">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {holdingsData.holdings.map((holding) => (
                            <tr key={holding.asset} className="border-t border-border hover:bg-muted/30">
                                <td className="px-4 py-3">
                                    <div className="font-semibold">{holding.asset}</div>
                                    <div className="text-xs text-muted-foreground">{holding.symbol}</div>
                                </td>
                                <td className="px-4 py-3 text-right font-mono">
                                    {holding.quantity.toFixed(6)}
                                </td>
                                <td className="px-4 py-3 text-right">
                                    ${holding.current_price.toFixed(4)}
                                </td>
                                <td className="px-4 py-3 text-right font-semibold">
                                    ${holding.current_value.toFixed(2)}
                                </td>
                                <td className="px-4 py-3 text-right">
                                    <button
                                        className="px-3 py-1 text-xs bg-primary/10 text-primary rounded-lg hover:bg-primary/20 transition-colors"
                                        onClick={() => setEditingHolding(holding)}
                                    >
                                        Set TP/SL
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            {holdingsData.total_pages > 1 && (
                <div className="p-4 border-t border-border flex items-center justify-center gap-2">
                    <button
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="px-3 py-1 rounded-lg bg-muted hover:bg-muted/80 disabled:opacity-50"
                    >
                        Previous
                    </button>
                    <span className="text-sm text-muted-foreground">
                        Page {holdingsData.page} of {holdingsData.total_pages}
                    </span>
                    <button
                        onClick={() => setPage(p => Math.min(holdingsData.total_pages, p + 1))}
                        disabled={page === holdingsData.total_pages}
                        className="px-3 py-1 rounded-lg bg-muted hover:bg-muted/80 disabled:opacity-50"
                    >
                        Next
                    </button>
                </div>
            )}

            {/* TP/SL Modal */}
            {editingHolding && (
                <SetTPSLModal
                    holding={editingHolding}
                    apiKeyId={apiKeyId}
                    onClose={() => setEditingHolding(null)}
                    onSuccess={() => {
                        setEditingHolding(null);
                        queryClient.invalidateQueries({ queryKey: ["orders"] });
                    }}
                />
            )}
        </div>
    );
}

interface SetTPSLModalProps {
    holding: Holding;
    apiKeyId: number;
    onClose: () => void;
    onSuccess: () => void;
}

function SetTPSLModal({ holding, apiKeyId, onClose, onSuccess }: SetTPSLModalProps) {
    const [quantity, setQuantity] = useState(holding.quantity.toString());
    const [takeProfit, setTakeProfit] = useState("");
    const [stopLoss, setStopLoss] = useState("");
    const [interval, setInterval] = useState("15m");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState("");

    const entryPrice = holding.current_price;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        const qty = parseFloat(quantity);
        const tp = takeProfit ? parseFloat(takeProfit) : undefined;
        const sl = stopLoss ? parseFloat(stopLoss) : undefined;

        if (qty <= 0 || qty > holding.quantity) {
            setError(`Quantity must be between 0 and ${holding.quantity}`);
            return;
        }
        // Only validate TP/SL if provided
        if (tp !== undefined && tp <= entryPrice) {
            setError("Take Profit must be higher than current price");
            return;
        }
        if (sl !== undefined && sl >= entryPrice) {
            setError("Stop Loss must be lower than current price");
            return;
        }

        setIsSubmitting(true);

        try {
            await ordersApi.createFromHolding({
                symbol: holding.symbol,
                quantity: qty,
                entry_price: entryPrice,
                take_profit: tp,
                stop_loss: sl,
                stop_interval: interval,
                api_key_id: apiKeyId,
            });
            onSuccess();
        } catch (err: any) {
            setError(err.response?.data?.detail || "Failed to create order");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
            <div
                className="bg-card rounded-2xl border border-border p-6 w-full max-w-md shadow-xl"
                onClick={e => e.stopPropagation()}
            >
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h3 className="text-lg font-semibold">Set TP/SL for {holding.asset}</h3>
                        <p className="text-sm text-muted-foreground">
                            Current price: ${entryPrice.toFixed(4)}
                        </p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-muted rounded-lg">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            Quantity (max: {holding.quantity.toFixed(6)})
                        </label>
                        <input
                            type="number"
                            step="any"
                            value={quantity}
                            onChange={e => setQuantity(e.target.value)}
                            className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-green-500 mb-2">
                                Take Profit
                            </label>
                            <input
                                type="number"
                                step="any"
                                value={takeProfit}
                                onChange={e => setTakeProfit(e.target.value)}
                                placeholder={`> ${entryPrice.toFixed(4)}`}
                                className="w-full px-4 py-2.5 rounded-xl bg-muted border border-green-500/30 focus:outline-none focus:ring-2 focus:ring-green-500/50"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-red-500 mb-2">
                                Stop Loss
                            </label>
                            <input
                                type="number"
                                step="any"
                                value={stopLoss}
                                onChange={e => setStopLoss(e.target.value)}
                                placeholder={`< ${entryPrice.toFixed(4)}`}
                                className="w-full px-4 py-2.5 rounded-xl bg-muted border border-red-500/30 focus:outline-none focus:ring-2 focus:ring-red-500/50"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            Check Interval
                        </label>
                        <select
                            value={interval}
                            onChange={e => setInterval(e.target.value)}
                            className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                        >
                            <option value="1m">1 minute</option>
                            <option value="5m">5 minutes</option>
                            <option value="15m">15 minutes</option>
                            <option value="1h">1 hour</option>
                            <option value="4h">4 hours</option>
                            <option value="1d">1 day</option>
                        </select>
                    </div>

                    {error && (
                        <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-sm">
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={isSubmitting}
                        className="w-full py-3 px-4 rounded-xl bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-all disabled:opacity-50"
                    >
                        {isSubmitting ? "Creating..." : "Create TP/SL Order"}
                    </button>
                </form>
            </div>
        </div>
    );
}
