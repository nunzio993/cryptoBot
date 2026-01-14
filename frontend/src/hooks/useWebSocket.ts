"use client";

import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";

interface WebSocketMessage {
    type: "connected" | "order_update" | "portfolio_update" | "price_update";
    data: any;
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8001";

export function useWebSocket() {
    const { token } = useAuth();
    const queryClient = useQueryClient();
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const reconnectAttempts = useRef(0);

    const handleMessage = useCallback((event: MessageEvent) => {
        // Handle pong response (plain text, not JSON)
        if (event.data === "pong") {
            return;
        }

        try {
            const message: WebSocketMessage = JSON.parse(event.data);
            console.log("[WebSocket] Received:", message.type);

            switch (message.type) {
                case "connected":
                    console.log("[WebSocket] Connected successfully");
                    break;

                case "order_update":
                    // Invalidate order queries to refresh data
                    queryClient.invalidateQueries({ queryKey: ["orders"] });
                    queryClient.invalidateQueries({ queryKey: ["portfolio"] });
                    console.log("[WebSocket] Order updated:", message.data);
                    break;

                case "portfolio_update":
                    // Refresh portfolio data
                    queryClient.invalidateQueries({ queryKey: ["portfolio"] });
                    console.log("[WebSocket] Portfolio update requested");
                    break;

                case "price_update":
                    // Could be used for real-time price updates
                    // For now, just log it
                    console.log("[WebSocket] Price update:", message.data);
                    break;

                default:
                    console.log("[WebSocket] Unknown message type:", message);
            }
        } catch (error) {
            console.error("[WebSocket] Failed to parse message:", error);
        }
    }, [queryClient]);

    const connect = useCallback(() => {
        if (!token) {
            console.log("[WebSocket] No token, skipping connection");
            return;
        }

        // Don't connect if already connected
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            return;
        }

        try {
            const wsUrl = `${WS_URL}/ws?token=${token}`;
            console.log("[WebSocket] Connecting to:", WS_URL);

            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.onopen = () => {
                console.log("[WebSocket] Connection opened");
                reconnectAttempts.current = 0;
            };

            ws.onmessage = handleMessage;

            ws.onclose = (event) => {
                console.log("[WebSocket] Connection closed:", event.code, event.reason);
                wsRef.current = null;

                // Don't reconnect on auth error
                if (event.code === 4001) {
                    console.log("[WebSocket] Auth failed, not reconnecting");
                    return;
                }

                // Exponential backoff reconnection
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
                reconnectAttempts.current++;

                console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`);
                reconnectTimeoutRef.current = setTimeout(connect, delay);
            };

            ws.onerror = (error) => {
                console.error("[WebSocket] Error:", error);
            };

        } catch (error) {
            console.error("[WebSocket] Failed to connect:", error);
        }
    }, [token, handleMessage]);

    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }

        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
    }, []);

    // Ping to keep connection alive
    const sendPing = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send("ping");
        }
    }, []);

    useEffect(() => {
        connect();

        // Ping every 30 seconds to keep connection alive
        const pingInterval = setInterval(sendPing, 30000);

        return () => {
            clearInterval(pingInterval);
            disconnect();
        };
    }, [connect, disconnect, sendPing]);

    return {
        isConnected: wsRef.current?.readyState === WebSocket.OPEN,
        disconnect,
        reconnect: connect,
    };
}
