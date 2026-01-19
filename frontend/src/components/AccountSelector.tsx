"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiKeysApi, type APIKey } from "@/lib/api";
import { ChevronDown, Wallet, Layers } from "lucide-react";
import { cn } from "@/lib/utils";

interface AccountSelectorProps {
    selectedKeyId: number | null;  // null = All Exchanges
    onSelect: (key: APIKey | null) => void;  // null = All selected
    showAllOption?: boolean;  // Whether to show "All Exchanges" option
}

export function AccountSelector({ selectedKeyId, onSelect, showAllOption = true }: AccountSelectorProps) {
    const [isOpen, setIsOpen] = useState(false);

    const { data: apiKeys = [], isLoading } = useQuery({
        queryKey: ["apiKeys"],
        queryFn: () => apiKeysApi.list().then((res) => res.data),
    });

    const selectedKey = selectedKeyId ? apiKeys.find((k) => k.id === selectedKeyId) : null;
    const isAllSelected = selectedKeyId === null;

    if (isLoading) {
        return (
            <div className="h-10 w-48 bg-muted rounded-xl animate-pulse" />
        );
    }

    if (apiKeys.length === 0) {
        return (
            <div className="px-4 py-2 bg-yellow-500/10 text-yellow-500 rounded-xl text-sm">
                No accounts configured
            </div>
        );
    }

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-xl border transition-all",
                    "bg-card border-border hover:border-primary/50",
                    isOpen && "border-primary"
                )}
            >
                {isAllSelected ? (
                    <Layers className="w-4 h-4 text-primary" />
                ) : (
                    <Wallet className="w-4 h-4 text-primary" />
                )}
                <span className="font-medium">
                    {isAllSelected ? "All Exchanges" : (selectedKey?.name || "Select Account")}
                </span>
                {selectedKey && (
                    <span className={cn(
                        "text-xs px-2 py-0.5 rounded-full",
                        selectedKey.is_testnet
                            ? "bg-yellow-500/20 text-yellow-500"
                            : "bg-green-500/20 text-green-500"
                    )}>
                        {selectedKey.is_testnet ? "Test" : "Live"}
                    </span>
                )}
                <ChevronDown className={cn(
                    "w-4 h-4 transition-transform",
                    isOpen && "rotate-180"
                )} />
            </button>

            {isOpen && (
                <>
                    <div
                        className="fixed inset-0 z-10"
                        onClick={() => setIsOpen(false)}
                    />
                    <div className="absolute right-0 top-full mt-2 w-64 bg-card border border-border rounded-xl shadow-lg z-20 overflow-hidden">
                        {/* All Exchanges Option */}
                        {showAllOption && (
                            <button
                                onClick={() => {
                                    onSelect(null);
                                    setIsOpen(false);
                                }}
                                className={cn(
                                    "w-full flex items-center gap-3 px-4 py-3 text-left transition-colors",
                                    "hover:bg-muted border-b border-border",
                                    isAllSelected && "bg-primary/10"
                                )}
                            >
                                <Layers className="w-5 h-5 text-primary" />
                                <div className="flex-1">
                                    <div className="font-medium">All Exchanges</div>
                                    <div className="text-xs text-muted-foreground">
                                        Aggregated data from all accounts
                                    </div>
                                </div>
                            </button>
                        )}

                        {/* Individual API Keys */}
                        {apiKeys.map((key) => (
                            <button
                                key={key.id}
                                onClick={() => {
                                    onSelect(key);
                                    setIsOpen(false);
                                }}
                                className={cn(
                                    "w-full flex items-center gap-3 px-4 py-3 text-left transition-colors",
                                    "hover:bg-muted",
                                    selectedKeyId === key.id && "bg-primary/10"
                                )}
                            >
                                <div className="flex-1">
                                    <div className="font-medium">{key.name}</div>
                                    <div className="text-xs text-muted-foreground">
                                        {key.exchange_name.toUpperCase()} • {key.api_key_masked}
                                    </div>
                                </div>
                                <span className={cn(
                                    "text-xs px-2 py-0.5 rounded-full",
                                    key.is_testnet
                                        ? "bg-yellow-500/20 text-yellow-500"
                                        : "bg-green-500/20 text-green-500"
                                )}>
                                    {key.is_testnet ? "Test" : "Live"}
                                </span>
                            </button>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}
