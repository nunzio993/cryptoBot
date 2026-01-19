"use client";

import { useQuery } from "@tanstack/react-query";
import { logsApi } from "@/lib/api";
import { FileText, RefreshCw, Loader2 } from "lucide-react";
import { useState } from "react";

export default function SystemLogsPage() {
    const [lines, setLines] = useState(100);

    const { data: logs = [], isLoading, refetch, isFetching } = useQuery({
        queryKey: ["logs", lines],
        queryFn: () => logsApi.get(lines).then((res) => res.data),
        refetchInterval: 30000,
    });

    return (
        <div className="space-y-6 animate-fadeIn">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold">Activity Log</h1>
                    <p className="text-muted-foreground mt-1">
                        Your trading activity history
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <select
                        value={lines}
                        onChange={(e) => setLines(parseInt(e.target.value))}
                        className="px-4 py-2.5 rounded-xl bg-muted border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                    >
                        <option value={50}>50 lines</option>
                        <option value={100}>100 lines</option>
                        <option value={250}>250 lines</option>
                        <option value={500}>500 lines</option>
                    </select>
                    <button
                        onClick={() => refetch()}
                        disabled={isFetching}
                        className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-all disabled:opacity-50"
                    >
                        {isFetching ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <RefreshCw className="w-4 h-4" />
                        )}
                        Refresh
                    </button>
                </div>
            </div>

            {/* Log viewer */}
            <div className="bg-card rounded-2xl border border-border overflow-hidden">
                <div className="flex items-center gap-3 px-6 py-4 border-b border-border">
                    <FileText className="w-5 h-5 text-muted-foreground" />
                    <span className="font-medium">Activity Log</span>
                    <span className="text-sm text-muted-foreground">
                        ({logs.length} events)
                    </span>
                </div>

                <div className="max-h-[600px] overflow-auto">
                    {isLoading ? (
                        <div className="flex items-center justify-center py-12">
                            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                        </div>
                    ) : logs.length === 0 ? (
                        <div className="text-center py-12 text-muted-foreground">
                            No logs available
                        </div>
                    ) : (
                        <pre className="p-6 font-mono text-xs leading-relaxed whitespace-pre-wrap break-all">
                            {logs.map((line, i) => (
                                <div
                                    key={i}
                                    className="py-0.5 hover:bg-muted/30 transition-colors"
                                >
                                    <span className="text-muted-foreground mr-4 select-none">
                                        {String(i + 1).padStart(4, " ")}
                                    </span>
                                    <span
                                        className={
                                            line.includes("ERROR") || line.includes("error")
                                                ? "text-red-500"
                                                : line.includes("CLOSED_SL")
                                                    ? "text-amber-500"
                                                    : line.includes("CLOSED_TP") || line.includes("EXECUTED")
                                                        ? "text-emerald-500"
                                                        : ""
                                        }
                                    >
                                        {line}
                                    </span>
                                </div>
                            ))}
                        </pre>
                    )}
                </div>
            </div>
        </div>
    );
}
