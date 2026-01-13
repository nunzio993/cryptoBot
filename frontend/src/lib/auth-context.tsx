"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, setAuthToken, clearAuthToken } from "./api";

interface User {
    id: number;
    username: string;
    email: string;
}

interface LoginResult {
    success: boolean;
    requires2FA: boolean;
    message?: string;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    isLoading: boolean;
    login: (username: string, password: string) => Promise<LoginResult>;
    loginWith2FA: (username: string, password: string, totpCode: string) => Promise<void>;
    register: (username: string, email: string, password: string) => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        // Check for stored token on mount
        const storedToken = localStorage.getItem("cryptobot_token");
        const storedUser = localStorage.getItem("cryptobot_user");

        if (storedToken && storedUser) {
            setToken(storedToken);
            setUser(JSON.parse(storedUser));
            setAuthToken(storedToken);
        }
        setIsLoading(false);
    }, []);

    const completeLogin = (access_token: string, userData: User) => {
        setToken(access_token);
        setUser(userData);
        setAuthToken(access_token);
        localStorage.setItem("cryptobot_token", access_token);
        localStorage.setItem("cryptobot_user", JSON.stringify(userData));
    };

    const login = async (username: string, password: string): Promise<LoginResult> => {
        const response = await api.post("/auth/login", { username, password });
        const data = response.data;

        // Check if 2FA is required
        if (data.requires_2fa) {
            return {
                success: false,
                requires2FA: true,
                message: data.message || "2FA verification required"
            };
        }

        // No 2FA - complete login
        const { access_token, user: userData } = data;
        completeLogin(access_token, userData);

        return { success: true, requires2FA: false };
    };

    const loginWith2FA = async (username: string, password: string, totpCode: string) => {
        const response = await api.post("/auth/login/2fa", {
            username,
            password,
            totp_code: totpCode
        });
        const { access_token, user: userData } = response.data;
        completeLogin(access_token, userData);
    };

    const register = async (username: string, email: string, password: string) => {
        const response = await api.post("/auth/register", { username, email, password });
        const { access_token, user: userData } = response.data;
        completeLogin(access_token, userData);
    };

    const logout = () => {
        setToken(null);
        setUser(null);
        clearAuthToken();

        localStorage.removeItem("cryptobot_token");
        localStorage.removeItem("cryptobot_user");
    };

    return (
        <AuthContext.Provider value={{ user, token, isLoading, login, loginWith2FA, register, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
}
