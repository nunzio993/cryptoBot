"""
CryptoBot API - FastAPI Backend
"""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

load_dotenv()

from api.routes import auth, orders, exchange, apikeys, profile, logs, telegram

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="CryptoBot API",
    description="Trading bot API for cryptocurrency management",
    version="1.0.0"
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev
        "http://localhost:3001",
        os.getenv("FRONTEND_URL", "http://localhost:3000")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Include routers
from api.routes import two_factor
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(two_factor.router, prefix="/api/2fa", tags=["Two-Factor Auth"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(exchange.router, prefix="/api/exchange", tags=["Exchange"])
app.include_router(apikeys.router, prefix="/api/apikeys", tags=["API Keys"])
app.include_router(profile.router, prefix="/api/profile", tags=["Profile"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
app.include_router(telegram.router, prefix="/api/telegram", tags=["Telegram"])


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "cryptobot-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
