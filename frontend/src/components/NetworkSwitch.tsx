"use client";

import { cn } from "@/lib/utils";
import { Wifi, TestTube } from "lucide-react";

interface NetworkSwitchProps {
    value: "Testnet" | "Mainnet";
    onChange: (value: "Testnet" | "Mainnet") => void;
}

export function NetworkSwitch({ value, onChange }: NetworkSwitchProps) {
    return (
        <div className="flex items-center p-1 rounded-xl bg-muted/50 border border-border">
            <button
                onClick={() => onChange("Testnet")}
                className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all",
                    value === "Testnet"
                        ? "bg-amber-500 text-white shadow-lg"
                        : "text-muted-foreground hover:text-foreground"
                )}
            >
                <TestTube className="w-4 h-4" />
                Testnet
            </button>
            <button
                onClick={() => onChange("Mainnet")}
                className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all",
                    value === "Mainnet"
                        ? "bg-emerald-500 text-white shadow-lg"
                        : "text-muted-foreground hover:text-foreground"
                )}
            >
                <Wifi className="w-4 h-4" />
                Mainnet
            </button>
        </div>
    );
}
