"use client";

import { useQuery } from "@tanstack/react-query";
import { statisticsApi, apiKeysApi, type StatisticsResponse, type APIKey } from "@/lib/api";
import { Loader2, TrendingUp, TrendingDown, DollarSign, Target, Trophy, BarChart3 } from "lucide-react";
import { useState } from "react";

export default function StatisticsPage() {
    const [days, setDays] = useState(30);
    const [selectedApiKeyId, setSelectedApiKeyId] = useState<number | undefined>(undefined);

    // Fetch API keys for selector
    const { data: apiKeys = [] } = useQuery({
        queryKey: ["apikeys"],
        queryFn: () => apiKeysApi.list().then((res) => res.data),
    });

    const { data, isLoading } = useQuery({
        queryKey: ["statistics", days, selectedApiKeyId],
        queryFn: () => statisticsApi.get(days, selectedApiKeyId).then((res) => res.data),
    });

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-24">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    const metrics = data?.metrics;
    const history = data?.balance_history || [];

    // Calculate chart dimensions with padding for better visibility
    const dataMin = history.length > 0 ? Math.min(...history.map(h => h.total)) : 0;
    const dataMax = history.length > 0 ? Math.max(...history.map(h => h.total)) : 1;
    const padding = (dataMax - dataMin) * 0.1 || dataMax * 0.1 || 50; // 10% padding or $50 minimum
    const minBalance = Math.max(0, dataMin - padding);
    const maxBalance = dataMax + padding;
    const range = maxBalance - minBalance || 1;

    return (
        <div className="space-y-6 animate-fadeIn">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold">Statistics</h1>
                    <p className="text-muted-foreground mt-1">
                        Your trading performance
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    {/* Exchange selector */}
                    <select
                        value={selectedApiKeyId || ""}
                        onChange={(e) => setSelectedApiKeyId(e.target.value ? parseInt(e.target.value) : undefined)}
                        className="px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                    >
                        <option value="">All Exchanges</option>
                        {apiKeys.map((key: APIKey) => (
                            <option key={key.id} value={key.id}>
                                {key.exchange_name} {key.is_testnet ? "(Testnet)" : ""} {key.name ? `- ${key.name}` : ""}
                            </option>
                        ))}
                    </select>

                    {/* Days selector */}
                    <select
                        value={days}
                        onChange={(e) => setDays(parseInt(e.target.value))}
                        className="px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                    >
                        <option value={7}>7 days</option>
                        <option value={30}>30 days</option>
                        <option value={90}>90 days</option>
                        <option value={365}>1 year</option>
                    </select>
                </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Current Balance */}
                <div className="bg-card rounded-2xl border border-border p-6">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-primary/10">
                            <DollarSign className="w-5 h-5 text-primary" />
                        </div>
                        <span className="text-sm text-muted-foreground">Current Balance</span>
                    </div>
                    <p className="text-2xl font-bold">${metrics?.current_balance.toFixed(2)}</p>
                </div>

                {/* All-time Profit */}
                <div className="bg-card rounded-2xl border border-border p-6">
                    <div className="flex items-center gap-3 mb-2">
                        <div className={`p-2 rounded-lg ${(metrics?.all_time_profit || 0) >= 0 ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
                            {(metrics?.all_time_profit || 0) >= 0
                                ? <TrendingUp className="w-5 h-5 text-emerald-500" />
                                : <TrendingDown className="w-5 h-5 text-red-500" />
                            }
                        </div>
                        <span className="text-sm text-muted-foreground">All-time P/L</span>
                    </div>
                    <p className={`text-2xl font-bold ${(metrics?.all_time_profit || 0) >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                        {(metrics?.all_time_profit || 0) >= 0 ? '+' : ''}${metrics?.all_time_profit.toFixed(2)}
                    </p>
                </div>

                {/* Win Rate */}
                <div className="bg-card rounded-2xl border border-border p-6">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-amber-500/10">
                            <Trophy className="w-5 h-5 text-amber-500" />
                        </div>
                        <span className="text-sm text-muted-foreground">Win Rate</span>
                    </div>
                    <p className="text-2xl font-bold">{metrics?.win_rate.toFixed(1)}%</p>
                </div>

                {/* Total Trades */}
                <div className="bg-card rounded-2xl border border-border p-6">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-blue-500/10">
                            <BarChart3 className="w-5 h-5 text-blue-500" />
                        </div>
                        <span className="text-sm text-muted-foreground">Total Trades</span>
                    </div>
                    <p className="text-2xl font-bold">{metrics?.total_trades}</p>
                </div>

                {/* Winning Trades */}
                <div className="bg-card rounded-2xl border border-border p-6">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-emerald-500/10">
                            <Target className="w-5 h-5 text-emerald-500" />
                        </div>
                        <span className="text-sm text-muted-foreground">TP Hits</span>
                    </div>
                    <p className="text-2xl font-bold text-emerald-500">{metrics?.winning_trades}</p>
                </div>

                {/* Losing Trades */}
                <div className="bg-card rounded-2xl border border-border p-6">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-red-500/10">
                            <TrendingDown className="w-5 h-5 text-red-500" />
                        </div>
                        <span className="text-sm text-muted-foreground">SL Hits</span>
                    </div>
                    <p className="text-2xl font-bold text-red-500">{metrics?.losing_trades}</p>
                </div>
            </div>

            {/* Balance Chart */}
            <div className="bg-card rounded-2xl border border-border p-6">
                <h3 className="text-lg font-semibold mb-4">Balance History</h3>
                {history.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground">
                        No balance history yet. Data is recorded daily at midnight UTC.
                    </div>
                ) : (
                    <div className="relative h-64">
                        {/* Y-axis labels */}
                        <div className="absolute left-0 top-0 bottom-0 w-16 flex flex-col justify-between text-xs text-muted-foreground">
                            <span>${maxBalance.toFixed(0)}</span>
                            <span>${((maxBalance + minBalance) / 2).toFixed(0)}</span>
                            <span>${minBalance.toFixed(0)}</span>
                        </div>

                        {/* Chart area */}
                        <div className="ml-16 h-full relative">
                            <svg className="w-full h-full" preserveAspectRatio="none">
                                {/* Grid lines */}
                                <line x1="0" y1="50%" x2="100%" y2="50%" stroke="currentColor" strokeOpacity="0.1" />

                                {/* Area fill under line */}
                                <polygon
                                    fill="url(#areaGradient)"
                                    points={`0%,100% ${history.map((h, i) => {
                                        const x = history.length === 1 ? 50 : (i / (history.length - 1)) * 100;
                                        const y = 100 - ((h.total - minBalance) / range) * 100;
                                        return `${x}%,${y}%`;
                                    }).join(' ')} 100%,100%`}
                                />

                                {/* Line chart */}
                                <polyline
                                    fill="none"
                                    stroke="#10b981"
                                    strokeWidth="3"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    points={history.map((h, i) => {
                                        const x = history.length === 1 ? 50 : (i / (history.length - 1)) * 100;
                                        const y = 100 - ((h.total - minBalance) / range) * 100;
                                        return `${x}%,${y}%`;
                                    }).join(' ')}
                                />

                                {/* Gradient definitions */}
                                <defs>
                                    <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                        <stop offset="0%" stopColor="#10b981" />
                                        <stop offset="100%" stopColor="#3b82f6" />
                                    </linearGradient>
                                    <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                                        <stop offset="0%" stopColor="#10b981" stopOpacity="0.3" />
                                        <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
                                    </linearGradient>
                                </defs>
                            </svg>
                        </div>

                        {/* X-axis labels */}
                        <div className="ml-16 flex justify-between text-xs text-muted-foreground mt-2">
                            {history.length > 0 && <span>{history[0].date}</span>}
                            {history.length > 1 && <span>{history[history.length - 1].date}</span>}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
