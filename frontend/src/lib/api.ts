import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api";

export const api = axios.create({
    baseURL: API_URL,
    headers: {
        "Content-Type": "application/json",
    },
});

export function setAuthToken(token: string) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
}

export function clearAuthToken() {
    delete api.defaults.headers.common["Authorization"];
}

// Initialize token from localStorage if available
if (typeof window !== "undefined") {
    const token = localStorage.getItem("cryptobot_token");
    if (token) {
        setAuthToken(token);
    }
}

// Types
export interface Order {
    id: number;
    symbol: string;
    side: string;
    quantity: number;
    status: string;
    entry_price: number | null;
    max_entry: number | null;
    take_profit: number | null;
    stop_loss: number | null;
    entry_interval: string | null;
    stop_interval: string | null;
    executed_price: number | null;
    executed_at: string | null;
    closed_at: string | null;
    created_at: string | null;
}

export interface Balance {
    asset: string;
    free: number;
    locked: number;
    total: number;
}

export interface APIKey {
    id: number;
    name: string | null;
    exchange_name: string;
    api_key_masked: string;
    is_testnet: boolean;
    created_at: string | null;
}

export interface Symbol {
    symbol: string;
}

export interface Position {
    order_id: number;
    symbol: string;
    quantity: number;
    entry_price: number;
    current_price: number;
    current_value: number;
    pnl: number;
    pnl_percent: number;
    take_profit: number | null;
    stop_loss: number | null;
}

export interface Portfolio {
    usdc_total: number;
    usdc_free: number;
    usdc_locked: number;
    usdc_blocked: number;
    usdc_available: number;
    positions_value: number;
    portfolio_total: number;
    positions: Position[];
}

export interface Holding {
    asset: string;
    symbol: string;
    quantity: number;
    avg_price: number;
    current_price: number;
    current_value: number;
    pnl: number;
    pnl_percent: number;
}

export interface HoldingsResponse {
    holdings: Holding[];
    total_value: number;
    page: number;
    total_pages: number;
}

// API functions
export const ordersApi = {
    list: (status?: string, networkMode?: string, apiKeyId?: number) =>
        api.get<Order[]>("/orders", { params: { status, network_mode: networkMode, api_key_id: apiKeyId } }),

    holdings: (apiKeyId: number, page: number = 1) =>
        api.get<HoldingsResponse>("/orders/holdings", { params: { api_key_id: apiKeyId, page, per_page: 10 } }),

    portfolio: (apiKeyId?: number, networkMode: string = "Mainnet") =>
        api.get<Portfolio>("/orders/portfolio", { params: { api_key_id: apiKeyId, network_mode: networkMode } }),

    create: (data: {
        symbol: string;
        quantity: number;
        entry_price: number;
        max_entry: number;
        take_profit: number;
        stop_loss: number;
        entry_interval: string;
        stop_interval: string;
    }, networkMode: string = "Testnet", exchangeName: string = "binance") =>
        api.post<Order>("/orders", data, { params: { network_mode: networkMode, exchange_name: exchangeName } }),

    createFromHolding: (data: {
        symbol: string;
        quantity: number;
        entry_price: number;
        take_profit: number;
        stop_loss: number;
        stop_interval: string;
        api_key_id: number;
    }) => api.post<Order>("/orders/from-holding", data),

    update: (id: number, data: Partial<Order>, networkMode: string = "Testnet") =>
        api.put<Order>(`/orders/${id}`, data, { params: { network_mode: networkMode } }),

    cancel: (id: number) => api.delete(`/orders/${id}`),

    close: (id: number, networkMode: string = "Testnet") =>
        api.post(`/orders/${id}/close`, null, { params: { network_mode: networkMode } }),
};

export const exchangeApi = {
    balance: (asset: string = "USDC", networkMode: string = "Testnet") =>
        api.get<Balance>("/exchange/balance", { params: { asset, network_mode: networkMode } }),

    symbols: (quoteAsset: string = "USDC") =>
        api.get<Symbol[]>("/exchange/symbols", { params: { quote_asset: quoteAsset } }),

    price: (symbol: string, networkMode: string = "Testnet") =>
        api.get<{ symbol: string; price: number }>("/exchange/price", {
            params: { symbol, network_mode: networkMode }
        }),
};

export const apiKeysApi = {
    list: () => api.get<APIKey[]>("/apikeys"),

    create: (data: {
        exchange_name: string;
        api_key: string;
        secret_key: string;
        is_testnet: boolean;
        name?: string;
    }) => api.post<APIKey>("/apikeys", data),

    update: (id: number, data: { api_key?: string; secret_key?: string; name?: string }) =>
        api.put<APIKey>(`/apikeys/${id}`, data),

    delete: (id: number) => api.delete(`/apikeys/${id}`),
};

export const profileApi = {
    get: () => api.get("/profile"),

    changePassword: (oldPassword: string, newPassword: string) =>
        api.put("/profile/password", { old_password: oldPassword, new_password: newPassword }),

    getTelegramCode: () => api.get<{ code: string; bot_link: string }>("/profile/telegram-code"),
};

export const logsApi = {
    get: (lines: number = 100) => api.get<string[]>("/logs", { params: { lines } }),
};

// Two-Factor Authentication API
export interface TwoFactorSetupResponse {
    qr_code_base64: string;
    manual_entry_key: string;
    backup_codes: string[];
}

export interface TwoFactorStatus {
    enabled: boolean;
    has_backup_codes: boolean;
}

export const twoFactorApi = {
    // Get 2FA status
    getStatus: () => api.get<TwoFactorStatus>("/2fa/status"),

    // Initialize 2FA setup - returns QR code and backup codes
    setup: () => api.post<TwoFactorSetupResponse>("/2fa/setup"),

    // Verify TOTP code and enable 2FA
    verify: (code: string) => api.post("/2fa/verify", { code }),

    // Disable 2FA (requires password and current code)
    disable: (password: string, code: string) =>
        api.post("/2fa/disable", { password, code }),
};

// Login with 2FA
export const authApi = {
    loginWith2FA: (username: string, password: string, totpCode: string) =>
        api.post("/auth/login/2fa", { username, password, totp_code: totpCode }),
};
