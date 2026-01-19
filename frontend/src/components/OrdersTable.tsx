"use client";

import { formatCurrency, formatDate, cn } from "@/lib/utils";
import { type Order } from "@/lib/api";
import { Loader2, Save, X, ArrowUpDown, Scissors } from "lucide-react";
import { useState } from "react";

interface OrdersTableProps {
    orders: Order[];
    type: "pending" | "executed" | "closed";
    onUpdate?: (id: number, data: Partial<Order>) => Promise<void>;
    onCancel?: (id: number) => Promise<void>;
    onClose?: (id: number) => Promise<void>;
    onSplit?: (id: number, data: { split_quantity: number; tp1: number; sl1: number; tp2: number; sl2: number }) => Promise<void>;
    isLoading?: boolean;
}

export function OrdersTable({
    orders,
    type,
    onUpdate,
    onCancel,
    onClose,
    onSplit,
    isLoading,
}: OrdersTableProps) {
    const [editingId, setEditingId] = useState<number | null>(null);
    const [editValues, setEditValues] = useState<Partial<Order>>({});
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Split modal state
    const [splitOrderId, setSplitOrderId] = useState<number | null>(null);
    const [splitOrder, setSplitOrder] = useState<Order | null>(null);
    const [splitValues, setSplitValues] = useState({
        split_quantity: 0,
        tp1: 0,
        sl1: 0,
        tp2: 0,
        sl2: 0,
    });
    const [splitting, setSplitting] = useState(false);

    const startEdit = (order: Order) => {
        setError(null);
        setEditingId(order.id);
        setEditValues({
            entry_price: order.entry_price,
            max_entry: order.max_entry,
            take_profit: order.take_profit,
            stop_loss: order.stop_loss,
            stop_interval: order.stop_interval,
            entry_interval: order.entry_interval,
        });
    };

    const cancelEdit = () => {
        setEditingId(null);
        setEditValues({});
        setError(null);
    };

    const saveEdit = async (id: number) => {
        if (!onUpdate) return;
        setSaving(true);
        setError(null);
        try {
            await onUpdate(id, editValues);
            setEditingId(null);
            setEditValues({});
        } catch (e: any) {
            // Extract error message from API response
            const errorMsg = e?.response?.data?.detail || e?.message || "Failed to update order";
            setError(errorMsg);
            console.error(e);
        } finally {
            setSaving(false);
        }
    };

    const openSplit = (order: Order) => {
        setSplitOrderId(order.id);
        setSplitOrder(order);
        const qty = order.quantity || 0;
        setSplitValues({
            split_quantity: qty / 2,
            tp1: order.take_profit || 0,
            sl1: order.stop_loss || 0,
            tp2: order.take_profit || 0,
            sl2: order.stop_loss || 0,
        });
    };

    const closeSplit = () => {
        setSplitOrderId(null);
        setSplitOrder(null);
    };

    const saveSplit = async () => {
        if (!onSplit || !splitOrderId) return;
        setSplitting(true);
        setError(null);
        try {
            await onSplit(splitOrderId, splitValues);
            closeSplit();
        } catch (e: any) {
            const errorMsg = e?.response?.data?.detail || e?.message || "Failed to split order";
            setError(errorMsg);
        } finally {
            setSplitting(false);
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (orders.length === 0) {
        return (
            <div className="text-center py-12 text-muted-foreground">
                No orders found
            </div>
        );
    }

    return (
        <div className="overflow-x-auto">
            {/* Split Modal */}
            {splitOrderId && splitOrder && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-card border border-border rounded-2xl p-6 max-w-md w-full mx-4">
                        <h3 className="text-lg font-semibold mb-4">Split Order #{splitOrderId}</h3>
                        <p className="text-sm text-muted-foreground mb-4">
                            Original: {splitOrder.quantity} {splitOrder.symbol}
                        </p>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium mb-1">Split Quantity (Part 1)</label>
                                <input
                                    type="number"
                                    value={splitValues.split_quantity}
                                    onChange={(e) => setSplitValues({ ...splitValues, split_quantity: parseFloat(e.target.value) })}
                                    className="w-full px-3 py-2 rounded-lg bg-muted border border-border"
                                    step="0.0001"
                                    max={splitOrder.quantity}
                                />
                                <p className="text-xs text-muted-foreground mt-1">
                                    Part 2: {((splitOrder.quantity || 0) - splitValues.split_quantity).toFixed(4)}
                                </p>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium mb-1 text-emerald-500">TP Part 1</label>
                                    <input
                                        type="number"
                                        value={splitValues.tp1}
                                        onChange={(e) => setSplitValues({ ...splitValues, tp1: parseFloat(e.target.value) })}
                                        className="w-full px-3 py-2 rounded-lg bg-muted border border-border"
                                        step="0.01"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-1 text-red-500">SL Part 1</label>
                                    <input
                                        type="number"
                                        value={splitValues.sl1}
                                        onChange={(e) => setSplitValues({ ...splitValues, sl1: parseFloat(e.target.value) })}
                                        className="w-full px-3 py-2 rounded-lg bg-muted border border-border"
                                        step="0.01"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-1 text-emerald-500">TP Part 2</label>
                                    <input
                                        type="number"
                                        value={splitValues.tp2}
                                        onChange={(e) => setSplitValues({ ...splitValues, tp2: parseFloat(e.target.value) })}
                                        className="w-full px-3 py-2 rounded-lg bg-muted border border-border"
                                        step="0.01"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-1 text-red-500">SL Part 2</label>
                                    <input
                                        type="number"
                                        value={splitValues.sl2}
                                        onChange={(e) => setSplitValues({ ...splitValues, sl2: parseFloat(e.target.value) })}
                                        className="w-full px-3 py-2 rounded-lg bg-muted border border-border"
                                        step="0.01"
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="flex gap-3 mt-6">
                            <button
                                onClick={closeSplit}
                                className="flex-1 py-2 px-4 rounded-lg bg-muted text-muted-foreground hover:bg-muted/80"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={saveSplit}
                                disabled={splitting}
                                className="flex-1 py-2 px-4 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center justify-center gap-2"
                            >
                                {splitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Scissors className="w-4 h-4" />}
                                Split
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {error && (
                <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-500 text-sm flex items-center justify-between">
                    <span>{error}</span>
                    <button
                        onClick={() => setError(null)}
                        className="p-1 hover:bg-red-500/20 rounded"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
            )}
            <table className="w-full">
                <thead>
                    <tr className="border-b border-border">
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                            ID
                        </th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                            Symbol
                        </th>
                        <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
                            Quantity
                        </th>
                        {type === "pending" && (
                            <>
                                <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
                                    Entry
                                </th>
                                <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
                                    Max Entry
                                </th>
                            </>
                        )}
                        {type === "executed" && (
                            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
                                Exec. Price
                            </th>
                        )}
                        <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
                            TP
                        </th>
                        <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
                            SL
                        </th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                            SL Interval
                        </th>
                        <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                            {type === "closed" ? "Closed" : "Created"}
                        </th>
                        {type === "closed" && (
                            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
                                Status
                            </th>
                        )}
                        {type !== "closed" && (
                            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
                                Actions
                            </th>
                        )}
                    </tr>
                </thead>
                <tbody>
                    {orders.map((order) => {
                        const isEditing = editingId === order.id;
                        return (
                            <tr
                                key={order.id}
                                className="border-b border-border/50 hover:bg-muted/30 transition-colors"
                            >
                                <td className="py-3 px-4 text-sm font-mono">#{order.id}</td>
                                <td className="py-3 px-4">
                                    <span className="font-medium">{order.symbol}</span>
                                </td>
                                <td className="py-3 px-4 text-right font-mono">
                                    {formatCurrency(order.quantity, 4)}
                                </td>

                                {type === "pending" && (
                                    <>
                                        <td className="py-3 px-4 text-right">
                                            {isEditing ? (
                                                <input
                                                    type="number"
                                                    value={editValues.entry_price || ""}
                                                    onChange={(e) =>
                                                        setEditValues({ ...editValues, entry_price: parseFloat(e.target.value) })
                                                    }
                                                    className="w-24 px-2 py-1 rounded bg-muted border border-border text-right text-sm"
                                                    step="0.0001"
                                                />
                                            ) : (
                                                <span className="font-mono">${formatCurrency(order.entry_price || 0, 4)}</span>
                                            )}
                                        </td>
                                        <td className="py-3 px-4 text-right">
                                            {isEditing ? (
                                                <input
                                                    type="number"
                                                    value={editValues.max_entry || ""}
                                                    onChange={(e) =>
                                                        setEditValues({ ...editValues, max_entry: parseFloat(e.target.value) })
                                                    }
                                                    className="w-24 px-2 py-1 rounded bg-muted border border-border text-right text-sm"
                                                    step="0.0001"
                                                />
                                            ) : (
                                                <span className="font-mono">${formatCurrency(order.max_entry || 0, 4)}</span>
                                            )}
                                        </td>
                                    </>
                                )}

                                {type === "executed" && (
                                    <td className="py-3 px-4 text-right font-mono">
                                        ${formatCurrency(order.executed_price || 0, 4)}
                                    </td>
                                )}

                                <td className="py-3 px-4 text-right">
                                    {isEditing ? (
                                        <input
                                            type="number"
                                            value={editValues.take_profit || ""}
                                            onChange={(e) =>
                                                setEditValues({ ...editValues, take_profit: parseFloat(e.target.value) })
                                            }
                                            className="w-24 px-2 py-1 rounded bg-muted border border-border text-right text-sm"
                                            step="0.01"
                                        />
                                    ) : (
                                        <span className="font-mono text-emerald-500">
                                            ${formatCurrency(order.take_profit || 0, 2)}
                                        </span>
                                    )}
                                </td>
                                <td className="py-3 px-4 text-right">
                                    {isEditing ? (
                                        <input
                                            type="number"
                                            value={editValues.stop_loss || ""}
                                            onChange={(e) =>
                                                setEditValues({ ...editValues, stop_loss: parseFloat(e.target.value) })
                                            }
                                            className="w-24 px-2 py-1 rounded bg-muted border border-border text-right text-sm"
                                            step="0.01"
                                        />
                                    ) : (
                                        <span className="font-mono text-red-500">
                                            ${formatCurrency(order.stop_loss || 0, 2)}
                                        </span>
                                    )}
                                </td>
                                <td className="py-3 px-4 text-sm text-muted-foreground">
                                    {isEditing ? (
                                        <select
                                            value={type === "pending" ? (editValues.entry_interval || "1m") : (editValues.stop_interval || "1h")}
                                            onChange={(e) =>
                                                type === "pending"
                                                    ? setEditValues({ ...editValues, entry_interval: e.target.value })
                                                    : setEditValues({ ...editValues, stop_interval: e.target.value })
                                            }
                                            className="w-20 px-2 py-1 rounded bg-muted border border-border text-sm"
                                        >
                                            <option value="1m">1m</option>
                                            <option value="5m">5m</option>
                                            <option value="15m">15m</option>
                                            <option value="1h">1h</option>
                                            <option value="4h">4h</option>
                                            <option value="1d">1d</option>
                                        </select>
                                    ) : (
                                        type === "pending" ? order.entry_interval : order.stop_interval || "-"
                                    )}
                                </td>
                                <td className="py-3 px-4 text-sm text-muted-foreground">
                                    {formatDate(type === "closed" ? order.closed_at : order.created_at)}
                                </td>

                                {type === "closed" && (
                                    <td className="py-3 px-4">
                                        <span
                                            className={cn(
                                                "inline-flex items-center px-2 py-1 rounded-full text-xs font-medium",
                                                order.status === "CLOSED_TP" && "bg-emerald-500/10 text-emerald-500",
                                                order.status === "CLOSED_SL" && "bg-red-500/10 text-red-500",
                                                order.status === "CLOSED_MANUAL" && "bg-blue-500/10 text-blue-500",
                                                order.status === "CANCELLED" && "bg-slate-500/10 text-slate-500"
                                            )}
                                        >
                                            {order.status}
                                        </span>
                                    </td>
                                )}

                                {type !== "closed" && (
                                    <td className="py-3 px-4 text-right">
                                        <div className="flex items-center justify-end gap-2">
                                            {isEditing ? (
                                                <>
                                                    <button
                                                        onClick={() => saveEdit(order.id)}
                                                        disabled={saving}
                                                        className="p-2 rounded-lg bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                                                    >
                                                        {saving ? (
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
                                                        onClick={() => startEdit(order)}
                                                        className="p-2 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                                                    >
                                                        <ArrowUpDown className="w-4 h-4" />
                                                    </button>
                                                    {type === "executed" && onSplit && (
                                                        <button
                                                            onClick={() => openSplit(order)}
                                                            className="p-2 rounded-lg bg-purple-500/10 text-purple-500 hover:bg-purple-500/20 transition-colors"
                                                            title="Split Order"
                                                        >
                                                            <Scissors className="w-4 h-4" />
                                                        </button>
                                                    )}
                                                    {type === "pending" && onCancel && (
                                                        <button
                                                            onClick={() => onCancel(order.id)}
                                                            className="p-2 rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 transition-colors"
                                                        >
                                                            <X className="w-4 h-4" />
                                                        </button>
                                                    )}
                                                    {type === "executed" && onClose && (
                                                        <button
                                                            onClick={() => onClose(order.id)}
                                                            className="p-2 rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 transition-colors"
                                                            title="Close Order"
                                                        >
                                                            <X className="w-4 h-4" />
                                                        </button>
                                                    )}
                                                </>
                                            )}
                                        </div>
                                    </td>
                                )}
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}
