"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { TrendingUp, Eye, EyeOff, Loader2, Shield } from "lucide-react";

export default function LoginPage() {
    const [isLogin, setIsLogin] = useState(true);
    const [username, setUsername] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState("");
    const [isLoading, setIsLoading] = useState(false);

    // 2FA state
    const [requires2FA, setRequires2FA] = useState(false);
    const [totpCode, setTotpCode] = useState("");

    const { login, loginWith2FA, register } = useAuth();
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setIsLoading(true);

        try {
            if (isLogin) {
                const result = await login(username, password);

                if (result.requires2FA) {
                    setRequires2FA(true);
                    setIsLoading(false);
                    return;
                }
            } else {
                if (password !== confirmPassword) {
                    setError("Passwords do not match");
                    setIsLoading(false);
                    return;
                }
                await register(username, email, password);
            }
            router.push("/dashboard");
        } catch (err: any) {
            setError(err.response?.data?.detail || "An error occurred");
        } finally {
            setIsLoading(false);
        }
    };

    const handle2FASubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setIsLoading(true);

        try {
            await loginWith2FA(username, password, totpCode);
            router.push("/dashboard");
        } catch (err: any) {
            setError(err.response?.data?.detail || "Invalid 2FA code");
        } finally {
            setIsLoading(false);
        }
    };

    const cancelTwoFactor = () => {
        setRequires2FA(false);
        setTotpCode("");
        setPassword("");
        setError("");
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
            {/* Background decoration */}
            <div className="absolute inset-0 overflow-hidden">
                <div className="absolute -top-1/2 -left-1/2 w-full h-full bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-full blur-3xl" />
                <div className="absolute -bottom-1/2 -right-1/2 w-full h-full bg-gradient-to-r from-purple-500/20 to-pink-500/20 rounded-full blur-3xl" />
            </div>

            <div className="relative z-10 w-full max-w-md p-8">
                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-r from-blue-500 to-purple-500 mb-4">
                        <TrendingUp className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-3xl font-bold text-white">CryptoBot</h1>
                    <p className="text-slate-400 mt-2">Professional Trading Dashboard</p>
                </div>

                {/* Card */}
                <div className="glass rounded-2xl p-8 shadow-2xl border border-white/10">
                    {/* 2FA Step */}
                    {requires2FA ? (
                        <div className="animate-fadeIn">
                            <div className="flex items-center justify-center gap-3 mb-6">
                                <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center">
                                    <Shield className="w-6 h-6 text-emerald-500" />
                                </div>
                            </div>
                            <h2 className="text-xl font-semibold text-white text-center mb-2">
                                Two-Factor Authentication
                            </h2>
                            <p className="text-slate-400 text-sm text-center mb-6">
                                Enter the code from your authenticator app
                            </p>

                            <form onSubmit={handle2FASubmit} className="space-y-4">
                                <div>
                                    <input
                                        type="text"
                                        value={totpCode}
                                        onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                                        className="w-full px-4 py-4 rounded-xl bg-slate-800/50 border border-slate-700 text-white text-center text-2xl tracking-widest font-mono placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all"
                                        placeholder="000000"
                                        maxLength={6}
                                        autoFocus
                                        required
                                    />
                                </div>

                                {error && (
                                    <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm animate-fadeIn">
                                        {error}
                                    </div>
                                )}

                                <button
                                    type="submit"
                                    disabled={isLoading || totpCode.length !== 6}
                                    className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-medium hover:from-emerald-600 hover:to-teal-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                >
                                    {isLoading ? (
                                        <>
                                            <Loader2 className="w-5 h-5 animate-spin" />
                                            Verifying...
                                        </>
                                    ) : (
                                        "Verify & Sign In"
                                    )}
                                </button>

                                <button
                                    type="button"
                                    onClick={cancelTwoFactor}
                                    className="w-full py-2 text-slate-400 hover:text-white text-sm transition-colors"
                                >
                                    ← Back to login
                                </button>
                            </form>
                        </div>
                    ) : (
                        <>
                            {/* Tab switcher */}
                            <div className="flex mb-6 bg-slate-800/50 rounded-xl p-1">
                                <button
                                    onClick={() => setIsLogin(true)}
                                    className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-medium transition-all ${isLogin
                                        ? "bg-gradient-to-r from-blue-500 to-purple-500 text-white shadow-lg"
                                        : "text-slate-400 hover:text-white"
                                        }`}
                                >
                                    Login
                                </button>
                                <button
                                    onClick={() => setIsLogin(false)}
                                    className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-medium transition-all ${!isLogin
                                        ? "bg-gradient-to-r from-blue-500 to-purple-500 text-white shadow-lg"
                                        : "text-slate-400 hover:text-white"
                                        }`}
                                >
                                    Register
                                </button>
                            </div>

                            {/* Form */}
                            <form onSubmit={handleSubmit} className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-2">
                                        Username
                                    </label>
                                    <input
                                        type="text"
                                        value={username}
                                        onChange={(e) => setUsername(e.target.value)}
                                        className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                                        placeholder="Enter your username"
                                        required
                                    />
                                </div>

                                {!isLogin && (
                                    <div className="animate-fadeIn">
                                        <label className="block text-sm font-medium text-slate-300 mb-2">
                                            Email
                                        </label>
                                        <input
                                            type="email"
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                                            placeholder="Enter your email"
                                            required={!isLogin}
                                        />
                                    </div>
                                )}

                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-2">
                                        Password
                                    </label>
                                    <div className="relative">
                                        <input
                                            type={showPassword ? "text" : "password"}
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            className="w-full px-4 py-3 pr-12 rounded-xl bg-slate-800/50 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                                            placeholder="Enter your password"
                                            required
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowPassword(!showPassword)}
                                            className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors"
                                        >
                                            {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                                        </button>
                                    </div>
                                </div>

                                {!isLogin && (
                                    <div className="animate-fadeIn">
                                        <label className="block text-sm font-medium text-slate-300 mb-2">
                                            Confirm Password
                                        </label>
                                        <input
                                            type="password"
                                            value={confirmPassword}
                                            onChange={(e) => setConfirmPassword(e.target.value)}
                                            className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                                            placeholder="Confirm your password"
                                            required={!isLogin}
                                        />
                                    </div>
                                )}

                                {error && (
                                    <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm animate-fadeIn">
                                        {error}
                                    </div>
                                )}

                                <button
                                    type="submit"
                                    disabled={isLoading}
                                    className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-blue-500 to-purple-500 text-white font-medium hover:from-blue-600 hover:to-purple-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                >
                                    {isLoading ? (
                                        <>
                                            <Loader2 className="w-5 h-5 animate-spin" />
                                            {isLogin ? "Signing in..." : "Creating account..."}
                                        </>
                                    ) : isLogin ? (
                                        "Sign In"
                                    ) : (
                                        "Create Account"
                                    )}
                                </button>
                            </form>
                        </>
                    )}
                </div>

                {/* Footer */}
                <p className="text-center text-slate-500 text-sm mt-6">
                    Secure cryptocurrency trading platform
                </p>
            </div>
        </div>
    );
}
