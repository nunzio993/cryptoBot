"use client";

import { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

interface BalanceCardProps {
    title: string;
    value: string | number;
    subtitle?: string;
    icon: ReactNode;
    isLoading?: boolean;
    trend?: {
        value: number;
        isPositive: boolean;
    };
    className?: string;
}

export function BalanceCard({
    title,
    value,
    subtitle,
    icon,
    isLoading,
    trend,
    className,
}: BalanceCardProps) {
    return (
        <div className={cn(
            "relative overflow-hidden rounded-2xl bg-card border border-border p-6 transition-all hover:shadow-lg hover:border-primary/20",
            className
        )}>
            {/* Gradient background */}
            <div className="absolute top-0 right-0 w-32 h-32 rounded-full blur-3xl opacity-10 bg-gradient-to-r from-blue-500 to-purple-500" />

            <div className="relative">
                <div className="flex items-center justify-between mb-4">
                    <span className="text-sm font-medium text-muted-foreground">
                        {title}
                    </span>
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-gradient-to-r from-blue-500 to-purple-500 text-white">
                        {icon}
                    </div>
                </div>

                {isLoading ? (
                    <div className="flex items-center gap-2">
                        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                        <span className="text-muted-foreground">Loading...</span>
                    </div>
                ) : (
                    <>
                        <div className="flex items-baseline gap-2">
                            <p className="text-3xl font-bold tracking-tight">{value}</p>
                            {trend && (
                                <span className={cn(
                                    "text-sm font-medium",
                                    trend.isPositive ? "text-green-500" : "text-red-500"
                                )}>
                                    {trend.isPositive ? "+" : ""}{trend.value.toFixed(2)}%
                                </span>
                            )}
                        </div>
                        {subtitle && (
                            <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
