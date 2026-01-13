"use client";

import { formatCurrency, formatDate, cn } from "@/lib/utils";
import { type Order } from "@/lib/api";
import { Loader2, Save, X, ArrowUpDown } from "lucide-react";
import { useState } from "react";

interface OrdersTableProps {
    orders: Order[];
    type: "pending" | "executed" | "closed";
    onUpdate?: (id: number, data: Partial<Order>) => Promise<void>;
    onCancel?: (id: number) => Promise<void>;
    onClose?: (id: number) => Promise<void>;
    isLoading?: boolean;
}

export function OrdersTable({
    orders,
    type,
    onUpdate,
    onCancel,
    onClose,
    isLoading,
}: OrdersTableProps) {
    const [editingId, setEditingId] = useState<number | null>(null);
    const [editValues, setEditValues] = useState<Partial<Order>>({});
    const [saving, setSaving] = useState(false);

    const startEdit = (order: Order) => {
        setEditingId(order.id);
        setEditValues({
            entry_price: order.entry_price,
            max_entry: order.max_entry,
            take_profit: order.take_profit,
            stop_loss: order.stop_loss,
        });
    };

    const cancelEdit = () => {
        setEditingId(null);
        setEditValues({});
    };

    const saveEdit = async (id: number) => {
        if (!onUpdate) return;
        setSaving(true);
        try {
            await onUpdate(id, editValues);
            setEditingId(null);
            setEditValues({});
        } catch (e) {
            console.error(e);
        } finally {
            setSaving(false);
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
                            Interval
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
                                    {type === "pending" ? order.entry_interval : order.stop_interval || "-"}
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
