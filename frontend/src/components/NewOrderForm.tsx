"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { ordersApi, exchangeApi } from "@/lib/api";
import { formatCurrency, cn } from "@/lib/utils";
import { Loader2, TrendingUp, AlertTriangle, DollarSign } from "lucide-react";

interface NewOrderFormProps {
    networkMode: "Testnet" | "Mainnet";
    apiKeyId?: number;
    onSuccess: () => void;
}

const INTERVALS = ["Market", "M5", "H1", "H4", "Daily"];

export function NewOrderForm({ networkMode, apiKeyId, onSuccess }: NewOrderFormProps) {
    const [formData, setFormData] = useState({
        symbol: "",
        quantity: "",
        entry_price: "",
        max_entry: "",
        take_profit: "",
        stop_loss: "",
        entry_interval: "H1",
        stop_interval: "H1",
    });
    const [error, setError] = useState("");
    const [loadingPrice, setLoadingPrice] = useState(false);
    const [usdcPercent, setUsdcPercent] = useState(100);

    // Fetch symbols
    const { data: symbols = [] } = useQuery({
        queryKey: ["symbols"],
        queryFn: () => exchangeApi.symbols("USDC").then((res) => res.data),
    });

    // Fetch portfolio for USDC balance
    const { data: portfolio } = useQuery({
        queryKey: ["portfolio", apiKeyId, networkMode],
        queryFn: () => ordersApi.portfolio(apiKeyId, networkMode).then((res) => res.data),
        enabled: !!apiKeyId,
    });

    // Create order mutation
    const createMutation = useMutation({
        mutationFn: (data: {
            symbol: string;
            quantity: number;
            entry_price: number;
            max_entry: number;
            take_profit?: number;
            stop_loss?: number;
            entry_interval?: string;
            stop_interval?: string;
        }) => ordersApi.create(data, networkMode),
        onSuccess: () => {
            setError("");
            onSuccess();
        },
        onError: (err: any) => {
            setError(err.response?.data?.detail || "Failed to create order");
        },
    });

    // Fetch price when symbol changes
    const handleSymbolChange = async (symbol: string) => {
        setFormData({ ...formData, symbol });

        if (!symbol) return;

        setLoadingPrice(true);
        try {
            const response = await exchangeApi.price(symbol, networkMode);
            const currentPrice = response.data.price;
            const maxEntry = currentPrice * 1.01; // 1% higher

            setFormData(prev => ({
                ...prev,
                symbol,
                entry_price: currentPrice.toFixed(4),
                max_entry: maxEntry.toFixed(4),
            }));
        } catch (err) {
            console.error("Failed to fetch price:", err);
        } finally {
            setLoadingPrice(false);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        const quantity = parseFloat(formData.quantity);
        const entryPrice = parseFloat(formData.entry_price);
        const maxEntry = parseFloat(formData.max_entry);
        const takeProfit = formData.take_profit ? parseFloat(formData.take_profit) : undefined;
        const stopLoss = formData.stop_loss ? parseFloat(formData.stop_loss) : undefined;

        // Validation
        if (!formData.symbol) {
            setError("Please select a symbol");
            return;
        }
        if (isNaN(quantity) || quantity <= 0) {
            setError("Invalid quantity");
            return;
        }
        // Only validate TP/SL relationship if both are provided
        if (takeProfit !== undefined && stopLoss !== undefined) {
            if (!(stopLoss < entryPrice && entryPrice < takeProfit)) {
                setError("Must be: Stop Loss < Entry Price < Take Profit");
                return;
            }
        }
        if (maxEntry < entryPrice) {
            setError("Max Entry must be >= Entry Price");
            return;
        }

        createMutation.mutate({
            symbol: formData.symbol,
            quantity,
            entry_price: entryPrice,
            max_entry: maxEntry,
            take_profit: takeProfit,
            stop_loss: stopLoss,
            entry_interval: formData.entry_interval || undefined,
            stop_interval: formData.stop_interval || undefined,
        });
    };

    const quantity = parseFloat(formData.quantity || "0");
    const maxEntry = parseFloat(formData.max_entry || "0");
    const totalOrder = quantity * maxEntry;

    return (
        <div className="bg-card rounded-2xl border border-border p-6 animate-fadeIn">
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-r from-blue-500 to-purple-500 flex items-center justify-center">
                        <TrendingUp className="w-5 h-5 text-white" />
                    </div>
                    <h2 className="text-xl font-semibold">New Trade</h2>
                </div>
                {portfolio && (
                    <div className="flex items-center gap-2 px-4 py-2 bg-muted rounded-xl">
                        <DollarSign className="w-4 h-4 text-green-500" />
                        <span className="text-sm text-muted-foreground">Available:</span>
                        <span className="font-semibold text-green-500">
                            {formatCurrency(portfolio.usdc_available)} USDC
                        </span>
                    </div>
                )}
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {/* Symbol */}
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            Symbol
                        </label>
                        <div className="relative">
                            <select
                                value={formData.symbol}
                                onChange={(e) => handleSymbolChange(e.target.value)}
                                className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                                disabled={loadingPrice}
                            >
                                <option value="">Select symbol</option>
                                {symbols.map((s) => (
                                    <option key={s.symbol} value={s.symbol}>
                                        {s.symbol}
                                    </option>
                                ))}
                            </select>
                            {loadingPrice && (
                                <Loader2 className="absolute right-10 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-primary" />
                            )}
                        </div>
                    </div>

                    {/* Quantity */}
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            Quantity
                        </label>
                        <input
                            type="number"
                            value={formData.quantity}
                            onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
                            className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                            placeholder="0.00"
                            step="0.0001"
                        />
                        {/* USDC Percentage Slider */}
                        {portfolio && formData.max_entry && (
                            <div className="mt-3">
                                <div className="flex justify-between text-xs text-muted-foreground mb-1">
                                    <span>Use {usdcPercent}% of available USDC</span>
                                    <span>{formatCurrency((portfolio.usdc_available * usdcPercent / 100))} USDC</span>
                                </div>
                                <input
                                    type="range"
                                    min="10"
                                    max="100"
                                    step="10"
                                    value={usdcPercent}
                                    onChange={(e) => {
                                        const percent = parseInt(e.target.value);
                                        setUsdcPercent(percent);
                                        const maxEntryPrice = parseFloat(formData.max_entry);
                                        if (maxEntryPrice > 0) {
                                            const usdcToUse = portfolio.usdc_available * percent / 100;
                                            const newQuantity = (usdcToUse / maxEntryPrice).toFixed(4);
                                            setFormData(prev => ({ ...prev, quantity: newQuantity }));
                                        }
                                    }}
                                    className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                                />
                                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                                    <span>10%</span>
                                    <span>50%</span>
                                    <span>100%</span>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Entry Price */}
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            Entry Price
                        </label>
                        <input
                            type="number"
                            value={formData.entry_price}
                            onChange={(e) => setFormData({ ...formData, entry_price: e.target.value })}
                            className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                            placeholder="0.00"
                            step="0.0001"
                        />
                    </div>

                    {/* Max Entry */}
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            Max Entry (+1%)
                        </label>
                        <input
                            type="number"
                            value={formData.max_entry}
                            onChange={(e) => setFormData({ ...formData, max_entry: e.target.value })}
                            className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                            placeholder="0.00"
                            step="0.0001"
                        />
                    </div>

                    {/* Take Profit */}
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            Take Profit
                        </label>
                        <input
                            type="number"
                            value={formData.take_profit}
                            onChange={(e) => setFormData({ ...formData, take_profit: e.target.value })}
                            className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50 text-emerald-500"
                            placeholder="0.00"
                            step="0.01"
                        />
                    </div>

                    {/* Stop Loss */}
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            Stop Loss
                        </label>
                        <input
                            type="number"
                            value={formData.stop_loss}
                            onChange={(e) => setFormData({ ...formData, stop_loss: e.target.value })}
                            className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50 text-red-500"
                            placeholder="0.00"
                            step="0.01"
                        />
                    </div>

                    {/* Entry Interval */}
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            Entry Interval
                        </label>
                        <select
                            value={formData.entry_interval}
                            onChange={(e) => setFormData({ ...formData, entry_interval: e.target.value })}
                            className={cn(
                                "w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50",
                                formData.entry_interval === "Market" && "border-amber-500/50"
                            )}
                        >
                            <option value="Market">🚀 Market (Immediate)</option>
                            <option value="M5">M5 (5 minutes)</option>
                            <option value="H1">H1 (1 hour)</option>
                            <option value="H4">H4 (4 hours)</option>
                            <option value="Daily">Daily</option>
                        </select>
                    </div>

                    {/* Stop Interval */}
                    <div>
                        <label className="block text-sm font-medium text-muted-foreground mb-2">
                            Stop Interval
                        </label>
                        <select
                            value={formData.stop_interval}
                            onChange={(e) => setFormData({ ...formData, stop_interval: e.target.value })}
                            className="w-full px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                        >
                            {INTERVALS.map((i) => (
                                <option key={i} value={i}>
                                    {i}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* Order Total */}
                <div className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-primary/20">
                    <div className="flex items-center gap-3">
                        <DollarSign className="w-5 h-5 text-primary" />
                        <span className="text-sm font-medium">Total Order</span>
                    </div>
                    <span className="text-2xl font-bold text-primary">
                        ${formatCurrency(totalOrder)}
                    </span>
                </div>

                {/* Market Order Warning */}
                {formData.entry_interval === "Market" && (
                    <div className="flex items-center gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-500">
                        <AlertTriangle className="w-5 h-5 flex-shrink-0" />
                        <p className="text-sm">
                            <strong>Market Order:</strong> Will be executed immediately at current market price.
                        </p>
                    </div>
                )}

                {/* Error */}
                {error && (
                    <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-sm">
                        {error}
                    </div>
                )}

                {/* Submit */}
                <button
                    type="submit"
                    disabled={createMutation.isPending}
                    className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-blue-500 to-purple-500 text-white font-medium hover:from-blue-600 hover:to-purple-600 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                >
                    {createMutation.isPending ? (
                        <>
                            <Loader2 className="w-5 h-5 animate-spin" />
                            Creating...
                        </>
                    ) : (
                        "Add Trade"
                    )}
                </button>
            </form>
        </div>
    );
}
