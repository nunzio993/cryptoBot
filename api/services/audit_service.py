"""
Audit Logging Service - Track all sensitive operations
"""
import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import Request

from models import SessionLocal, AuditLog


# Audit action types
class AuditAction:
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGIN_2FA_REQUIRED = "login_2fa_required"
    LOGIN_2FA_SUCCESS = "login_2fa_success"
    LOGIN_2FA_FAILED = "login_2fa_failed"
    LOGOUT = "logout"
    REGISTER = "register"
    
    # Account Security
    PASSWORD_CHANGE = "password_change"
    TWO_FACTOR_ENABLE = "2fa_enable"
    TWO_FACTOR_DISABLE = "2fa_disable"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    
    # API Keys
    API_KEY_CREATE = "api_key_create"
    API_KEY_UPDATE = "api_key_update"
    API_KEY_DELETE = "api_key_delete"
    
    # Orders
    ORDER_CREATE = "order_create"
    ORDER_EXECUTE = "order_execute"
    ORDER_CLOSE_TP = "order_close_tp"
    ORDER_CLOSE_SL = "order_close_sl"
    ORDER_DELETE = "order_delete"
    
    # Suspicious Activity
    SUSPICIOUS_IP = "suspicious_ip"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Extract user agent from request"""
    return request.headers.get("User-Agent", "unknown")[:500]  # Limit length


def log_audit(
    action: str,
    user_id: Optional[int] = None,
    request: Optional[Request] = None,
    details: Optional[dict] = None,
    success: bool = True
) -> None:
    """
    Log an audit event to the database.
    
    Args:
        action: Type of action (use AuditAction constants)
        user_id: ID of user performing action (optional)
        request: FastAPI request object for IP/UA extraction
        details: Additional details as dict (will be JSON serialized)
        success: Whether the action was successful
    """
    try:
        ip_address = get_client_ip(request) if request else None
        user_agent = get_user_agent(request) if request else None
        
        with SessionLocal() as session:
            audit_entry = AuditLog(
                user_id=user_id,
                action=action,
                details=json.dumps(details) if details else None,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success
            )
            session.add(audit_entry)
            session.commit()
    except Exception as e:
        # Don't let audit logging failures break the application
        print(f"[AUDIT ERROR] Failed to log: {action} - {e}")


def log_login_attempt(
    username: str,
    request: Request,
    success: bool,
    user_id: Optional[int] = None,
    reason: Optional[str] = None
) -> None:
    """Log a login attempt with details"""
    details = {"username": username}
    if reason:
        details["reason"] = reason
    
    action = AuditAction.LOGIN_SUCCESS if success else AuditAction.LOGIN_FAILED
    log_audit(action, user_id=user_id, request=request, details=details, success=success)


def log_api_key_action(
    action: str,
    user_id: int,
    request: Request,
    api_key_id: int,
    exchange: str
) -> None:
    """Log API key create/update/delete"""
    log_audit(
        action,
        user_id=user_id,
        request=request,
        details={"api_key_id": api_key_id, "exchange": exchange}
    )


def log_order_action(
    action: str,
    user_id: int,
    order_id: int,
    symbol: str,
    request: Optional[Request] = None
) -> None:
    """Log order create/execute/close"""
    log_audit(
        action,
        user_id=user_id,
        request=request,
        details={"order_id": order_id, "symbol": symbol}
    )
