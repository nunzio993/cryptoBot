"""
Authentication routes
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
from werkzeug.security import generate_password_hash, check_password_hash
from slowapi import Limiter
from slowapi.util import get_remote_address

from models import SessionLocal, User
from api.deps import create_access_token, get_db, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter()

# Rate limiter - uses the same instance from main app
limiter = Limiter(key_func=get_remote_address)


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True


class TwoFactorLoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str


class LoginResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[dict] = None
    requires_2fa: bool = False
    message: Optional[str] = None


# Account lockout settings
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def check_account_lockout(user, db) -> Optional[str]:
    """Check if account is locked. Returns error message or None if OK."""
    if not user.locked_until:
        return None
    
    now = datetime.now(timezone.utc)
    if user.locked_until > now:
        remaining = (user.locked_until - now).seconds // 60
        return f"Account locked. Try again in {remaining + 1} minutes."
    
    # Lockout expired, reset
    user.locked_until = None
    user.failed_login_attempts = 0
    db.commit()
    return None


def record_failed_login(user, db):
    """Record failed login attempt and lock if needed"""
    from api.services.audit_service import log_audit, AuditAction
    
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    user.last_failed_login = datetime.now(timezone.utc)
    
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        log_audit(AuditAction.ACCOUNT_LOCKED, user.id, details={
            "failed_attempts": user.failed_login_attempts
        })
    
    db.commit()


def reset_failed_login(user, db):
    """Reset failed login counter on successful login"""
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_failed_login = None
    db.commit()


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(request: Request, login_data: LoginRequest, db=Depends(get_db)):
    """
    Login endpoint with account lockout and 2FA support.
    If 2FA is enabled, returns requires_2fa=True and user must call /login/2fa
    """
    from api.services.audit_service import log_login_attempt, log_audit, AuditAction
    from sqlalchemy import func
    
    # Case-insensitive username lookup
    user = db.query(User).filter(func.lower(User.username) == login_data.username.lower()).first()
    
    if not user:
        log_login_attempt(login_data.username, request, False, reason="user_not_found")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Check lockout
    lockout_msg = check_account_lockout(user, db)
    if lockout_msg:
        log_login_attempt(login_data.username, request, False, user.id, "account_locked")
        raise HTTPException(status_code=423, detail=lockout_msg)
    
    # Verify password
    if not check_password_hash(user.password_hash, login_data.password):
        record_failed_login(user, db)
        log_login_attempt(login_data.username, request, False, user.id, "wrong_password")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Check if 2FA required
    if user.two_factor_enabled:
        log_audit(AuditAction.LOGIN_2FA_REQUIRED, user.id, request)
        return LoginResponse(
            requires_2fa=True,
            message="2FA verification required"
        )
    
    # No 2FA - complete login
    reset_failed_login(user, db)
    log_login_attempt(login_data.username, request, True, user.id)
    
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return LoginResponse(
        access_token=access_token,
        user={"id": user.id, "username": user.username, "email": user.email}
    )


@router.post("/login/2fa", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login_with_2fa(request: Request, login_data: TwoFactorLoginRequest, db=Depends(get_db)):
    """
    Complete login with 2FA code.
    """
    from api.services.audit_service import log_login_attempt, log_audit, AuditAction
    from api.services.two_factor_service import verify_totp, decrypt_totp_secret, verify_backup_code
    from sqlalchemy import func
    
    # Case-insensitive username lookup
    user = db.query(User).filter(func.lower(User.username) == login_data.username.lower()).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check lockout
    lockout_msg = check_account_lockout(user, db)
    if lockout_msg:
        raise HTTPException(status_code=423, detail=lockout_msg)
    
    # Verify password first
    if not check_password_hash(user.password_hash, login_data.password):
        record_failed_login(user, db)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.two_factor_enabled or not user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA not enabled for this account")
    
    # Verify TOTP code
    secret = decrypt_totp_secret(user.totp_secret, user.id)
    code_valid = verify_totp(secret, login_data.totp_code)
    
    # If TOTP fails, try backup code
    if not code_valid and user.backup_codes:
        code_valid, new_backup_codes = verify_backup_code(
            user.backup_codes, user.id, login_data.totp_code
        )
        if code_valid:
            user.backup_codes = new_backup_codes
            db.commit()
    
    if not code_valid:
        record_failed_login(user, db)
        log_audit(AuditAction.LOGIN_2FA_FAILED, user.id, request)
        raise HTTPException(status_code=401, detail="Invalid 2FA code")
    
    # Success!
    reset_failed_login(user, db)
    log_audit(AuditAction.LOGIN_2FA_SUCCESS, user.id, request)
    log_login_attempt(login_data.username, request, True, user.id)
    
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return LoginResponse(
        access_token=access_token,
        user={"id": user.id, "username": user.username, "email": user.email}
    )


@router.post("/register", response_model=TokenResponse)
@limiter.limit("3/minute")  # Max 3 registrations per minute per IP
async def register(request: Request, reg_data: RegisterRequest, db=Depends(get_db)):
    # Check if username exists
    if db.query(User).filter(User.username == reg_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Check if email exists
    if db.query(User).filter(User.email == reg_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    password_hash = generate_password_hash(reg_data.password)
    user = User(
        username=reg_data.username,
        email=reg_data.email,
        password_hash=password_hash
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Generate token
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return TokenResponse(
        access_token=access_token,
        user={"id": user.id, "username": user.username, "email": user.email}
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
