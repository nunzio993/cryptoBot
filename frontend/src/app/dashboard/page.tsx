"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { ordersApi, apiKeysApi, type Portfolio, type Position, type APIKey, type Order } from "@/lib/api";
import { formatCurrency, cn } from "@/lib/utils";
import { BalanceCard } from "@/components/BalanceCard";
import { AccountSelector } from "@/components/AccountSelector";
import {
    Wallet,
    TrendingUp,
    TrendingDown,
    DollarSign,
    Clock,
    PiggyBank,
    AlertTriangle,
    ArrowUpRight,
    ArrowDownRight
} from "lucide-react";

export default function DashboardPage() {
    // Load saved API key ID from localStorage
    const [selectedKeyId, setSelectedKeyId] = useState<number | null>(() => {
        if (typeof window !== "undefined") {
            const saved = localStorage.getItem("cryptobot_api_key_id");
            return saved ? parseInt(saved, 10) : null;
        }
        return null;
    });

    const [selectedKey, setSelectedKey] = useState<APIKey | null>(null);
    const [activeTab, setActiveTab] = useState<"executed" | "pending">("executed");

    // Fetch API keys to set default if none selected
    const { data: apiKeys = [], isLoading: isLoadingKeys } = useQuery({
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

    // Fetch portfolio
    const { data: portfolio, isLoading } = useQuery({
        queryKey: ["portfolio", selectedKeyId],
        queryFn: () => ordersApi.portfolio(selectedKeyId || undefined, networkMode).then((res) => res.data),
        refetchInterval: 5000, // 5 seconds for faster updates
        enabled: !!selectedKeyId,
    });

    // Fetch pending orders
    const { data: pendingOrders = [] } = useQuery({
        queryKey: ["orders", "PENDING", selectedKeyId],
        queryFn: () => ordersApi.list("PENDING", networkMode, selectedKeyId || undefined).then((res) => res.data),
        refetchInterval: 5000, // 5 seconds for faster updates
        enabled: !!selectedKeyId,
    });

    const totalPnl = portfolio?.positions.reduce((sum, p) => sum + p.pnl, 0) || 0;
    const totalPnlPercent = portfolio?.positions_value
        ? (totalPnl / (portfolio.positions_value - totalPnl)) * 100
        : 0;

    // Calculate total crypto value (positions value)
    const totalCryptoValue = portfolio?.positions_value || 0;

    // Calculate pending orders total value
    const pendingTotalValue = pendingOrders.reduce((sum, o) => sum + (o.quantity * (o.max_entry || 0)), 0);

    return (
        <div className="space-y-8 animate-fadeIn">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold">Dashboard</h1>
                    <p className="text-muted-foreground mt-1">
                        Monitor your portfolio and positions
                    </p>
                </div>
                <AccountSelector
                    selectedKeyId={selectedKeyId}
                    onSelect={handleSelectKey}
                />
            </div>

            {/* No API Keys Warning */}
            {!isLoadingKeys && apiKeys.length === 0 && (
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-6">
                    <div className="flex items-start gap-4">
                        <div className="w-12 h-12 rounded-xl bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                            <AlertTriangle className="w-6 h-6 text-amber-500" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-lg text-amber-500">API Keys Not Configured</h3>
                            <p className="text-muted-foreground mt-1">
                                To view your portfolio and start trading, you need to configure your API keys first.
                            </p>
                            <a
                                href="/dashboard/apikeys"
                                className="inline-flex items-center gap-2 mt-3 px-4 py-2 bg-amber-500 text-black font-medium rounded-xl hover:bg-amber-400 transition-colors"
                            >
                                Go to API Keys
                                <ArrowUpRight className="w-4 h-4" />
                            </a>
                        </div>
                    </div>
                </div>
            )}

            {/* Portfolio Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <BalanceCard
                    title="Total Portfolio"
                    value={formatCurrency(apiKeys.length > 0 ? (portfolio?.portfolio_total || 0) : 0)}
                    subtitle={`${formatCurrency(apiKeys.length > 0 ? totalCryptoValue : 0)} in crypto`}
                    icon={<Wallet className="w-5 h-5" />}
                    trend={totalPnl !== 0 ? { value: totalPnlPercent, isPositive: totalPnl > 0 } : undefined}
                    isLoading={isLoading && apiKeys.length > 0}
                />
                <BalanceCard
                    title="Available USDC"
                    value={formatCurrency(apiKeys.length > 0 ? (portfolio?.usdc_available || 0) : 0)}
                    subtitle={`${formatCurrency(apiKeys.length > 0 ? (portfolio?.usdc_blocked || 0) : 0)} in pending`}
                    icon={<DollarSign className="w-5 h-5" />}
                    isLoading={isLoading && apiKeys.length > 0}
                />
                <BalanceCard
                    title="Crypto Holdings"
                    value={formatCurrency(apiKeys.length > 0 ? totalCryptoValue : 0)}
                    subtitle={`${apiKeys.length > 0 ? (portfolio?.positions.length || 0) : 0} active positions`}
                    icon={<PiggyBank className="w-5 h-5" />}
                    isLoading={isLoading && apiKeys.length > 0}
                />
                <BalanceCard
                    title="Total P&L"
                    value={formatCurrency(apiKeys.length > 0 ? totalPnl : 0)}
                    icon={totalPnl >= 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                    trend={{ value: totalPnlPercent, isPositive: totalPnl >= 0 }}
                    className={cn(
                        totalPnl > 0 && "border-green-500/30 bg-green-500/5",
                        totalPnl < 0 && "border-red-500/30 bg-red-500/5"
                    )}
                    isLoading={isLoading && apiKeys.length > 0}
                />
            </div>

            {/* Positions Section */}
            <div className="bg-card rounded-2xl border border-border p-6">
                {/* Tab Headers */}
                <div className="flex items-center gap-4 mb-6">
                    <button
                        onClick={() => setActiveTab("executed")}
                        className={cn(
                            "flex items-center gap-2 px-4 py-2 rounded-xl transition-all",
                            activeTab === "executed"
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted text-muted-foreground hover:text-foreground"
                        )}
                    >
                        <TrendingUp className="w-4 h-4" />
                        Active Positions
                        <span className="px-2 py-0.5 rounded-full text-xs bg-white/20">
                            {portfolio?.positions.length || 0}
                        </span>
                    </button>
                    <button
                        onClick={() => setActiveTab("pending")}
                        className={cn(
                            "flex items-center gap-2 px-4 py-2 rounded-xl transition-all",
                            activeTab === "pending"
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted text-muted-foreground hover:text-foreground"
                        )}
                    >
                        <Clock className="w-4 h-4" />
                        Pending Orders
                        <span className="px-2 py-0.5 rounded-full text-xs bg-white/20">
                            {pendingOrders.length}
                        </span>
                    </button>
                </div>

                {/* Active Positions Tab */}
                {activeTab === "executed" && (
                    <>
                        {isLoading ? (
                            <div className="space-y-4">
                                {[1, 2, 3].map((i) => (
                                    <div key={i} className="h-20 bg-muted rounded-xl animate-pulse" />
                                ))}
                            </div>
                        ) : portfolio?.positions.length === 0 ? (
                            <div className="text-center py-12 text-muted-foreground">
                                <AlertTriangle className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                <p>No active positions</p>
                                <p className="text-sm mt-1">Create your first trade to get started</p>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {portfolio?.positions.map((position) => (
                                    <PositionCard key={position.order_id} position={position} />
                                ))}
                            </div>
                        )}
                    </>
                )}

                {/* Pending Orders Tab */}
                {activeTab === "pending" && (
                    <>
                        {pendingOrders.length === 0 ? (
                            <div className="text-center py-12 text-muted-foreground">
                                <Clock className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                <p>No pending orders</p>
                                <p className="text-sm mt-1">Orders waiting to be executed will appear here</p>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {pendingOrders.map((order) => (
                                    <PendingOrderCard key={order.id} order={order} />
                                ))}
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}

function PositionCard({ position }: { position: Position }) {
    const isProfit = position.pnl >= 0;
    const router = require("next/navigation").useRouter();

    return (
        <div
            onClick={() => router.push("/dashboard/orders")}
            className={cn(
                "p-4 rounded-xl border transition-all hover:scale-[1.01] cursor-pointer",
                isProfit
                    ? "bg-green-500/5 border-green-500/20 hover:border-green-500/40"
                    : "bg-red-500/5 border-red-500/20 hover:border-red-500/40"
            )}>
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <div className={cn(
                        "w-10 h-10 rounded-xl flex items-center justify-center",
                        isProfit ? "bg-green-500/20" : "bg-red-500/20"
                    )}>
                        {isProfit ? (
                            <ArrowUpRight className="w-5 h-5 text-green-500" />
                        ) : (
                            <ArrowDownRight className="w-5 h-5 text-red-500" />
                        )}
                    </div>
                    <div>
                        <div className="font-semibold">{position.symbol}</div>
                        <div className="text-sm text-muted-foreground">
                            {position.quantity} @ {formatCurrency(position.entry_price)}
                        </div>
                    </div>
                </div>

                <div className="text-right">
                    <div className="text-sm text-muted-foreground">
                        Current: {formatCurrency(position.current_price)}
                    </div>
                    <div className={cn(
                        "font-semibold",
                        isProfit ? "text-green-500" : "text-red-500"
                    )}>
                        {isProfit ? "+" : ""}{formatCurrency(position.pnl)} ({position.pnl_percent.toFixed(2)}%)
                    </div>
                </div>

                <div className="hidden lg:flex items-center gap-6 text-sm">
                    <div>
                        <span className="text-muted-foreground">TP:</span>
                        <span className="ml-1 text-green-500">{formatCurrency(position.take_profit || 0)}</span>
                    </div>
                    <div>
                        <span className="text-muted-foreground">SL:</span>
                        <span className="ml-1 text-red-500">{formatCurrency(position.stop_loss || 0)}</span>
                    </div>
                </div>
            </div>
        </div>
    );
}

function PendingOrderCard({ order }: { order: Order }) {
    const totalValue = order.quantity * (order.max_entry || 0);

    return (
        <div className="p-4 rounded-xl border border-amber-500/20 bg-amber-500/5 transition-all hover:scale-[1.01]">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-amber-500/20">
                        <Clock className="w-5 h-5 text-amber-500" />
                    </div>
                    <div>
                        <div className="font-semibold">{order.symbol}</div>
                        <div className="text-sm text-muted-foreground">
                            {order.quantity} @ max {formatCurrency(order.max_entry || 0)}
                        </div>
                    </div>
                </div>

                <div className="text-right">
                    <div className="text-sm text-muted-foreground">
                        Entry: {formatCurrency(order.entry_price || 0)} - {formatCurrency(order.max_entry || 0)}
                    </div>
                    <div className="font-semibold text-amber-500">
                        ~{formatCurrency(totalValue)}
                    </div>
                </div>

                <div className="hidden lg:flex items-center gap-6 text-sm">
                    <div>
                        <span className="text-muted-foreground">TP:</span>
                        <span className="ml-1 text-green-500">{formatCurrency(order.take_profit || 0)}</span>
                    </div>
                    <div>
                        <span className="text-muted-foreground">SL:</span>
                        <span className="ml-1 text-red-500">{formatCurrency(order.stop_loss || 0)}</span>
                    </div>
                    <div className="text-muted-foreground">
                        {order.entry_interval}
                    </div>
                </div>
            </div>
        </div>
    );
}
