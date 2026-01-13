"""
Two-Factor Authentication API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List

from models import User
from api.deps import get_db, get_current_user
from api.services.two_factor_service import (
    setup_2fa_for_user,
    verify_totp,
    decrypt_totp_secret,
    verify_backup_code
)
from api.services.audit_service import log_audit, AuditAction

router = APIRouter()


class Enable2FAResponse(BaseModel):
    qr_code_base64: str
    manual_entry_key: str
    backup_codes: List[str]


class Verify2FARequest(BaseModel):
    code: str


class Disable2FARequest(BaseModel):
    password: str
    code: str  # Require 2FA code to disable


@router.post("/setup", response_model=Enable2FAResponse)
async def setup_2fa(
    request: Request,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Initialize 2FA setup. Returns QR code and backup codes.
    User must verify with a code before 2FA is enabled.
    """
    if current_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    
    # Generate 2FA setup
    setup = setup_2fa_for_user(current_user.id, current_user.username)
    
    # Store encrypted secret temporarily (not enabled yet)
    current_user.totp_secret = setup["encrypted_secret"]
    current_user.backup_codes = setup["encrypted_backup_codes"]
    db.commit()
    
    return Enable2FAResponse(
        qr_code_base64=setup["qr_code_base64"],
        manual_entry_key=setup["manual_entry_key"],
        backup_codes=setup["backup_codes"]
    )


@router.post("/verify")
async def verify_and_enable_2fa(
    request: Request,
    verify_request: Verify2FARequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Verify TOTP code and enable 2FA for the user.
    Must be called after /setup with a valid code from authenticator app.
    """
    if current_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="Call /setup first")
    
    # Decrypt and verify
    secret = decrypt_totp_secret(current_user.totp_secret, current_user.id)
    
    if not verify_totp(secret, verify_request.code):
        log_audit(AuditAction.TWO_FACTOR_ENABLE, current_user.id, request, 
                  {"reason": "invalid_code"}, success=False)
        raise HTTPException(status_code=400, detail="Invalid verification code")
    
    # Enable 2FA
    current_user.two_factor_enabled = True
    db.commit()
    
    log_audit(AuditAction.TWO_FACTOR_ENABLE, current_user.id, request)
    
    return {"message": "2FA enabled successfully", "enabled": True}


@router.post("/disable")
async def disable_2fa(
    request: Request,
    disable_request: Disable2FARequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Disable 2FA. Requires password and current 2FA code.
    """
    from werkzeug.security import check_password_hash
    
    if not current_user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    
    # Verify password
    if not check_password_hash(current_user.password_hash, disable_request.password):
        raise HTTPException(status_code=400, detail="Invalid password")
    
    # Verify 2FA code
    secret = decrypt_totp_secret(current_user.totp_secret, current_user.id)
    if not verify_totp(secret, disable_request.code):
        log_audit(AuditAction.TWO_FACTOR_DISABLE, current_user.id, request,
                  {"reason": "invalid_code"}, success=False)
        raise HTTPException(status_code=400, detail="Invalid 2FA code")
    
    # Disable 2FA
    current_user.two_factor_enabled = False
    current_user.totp_secret = None
    current_user.backup_codes = None
    db.commit()
    
    log_audit(AuditAction.TWO_FACTOR_DISABLE, current_user.id, request)
    
    return {"message": "2FA disabled successfully", "enabled": False}


@router.get("/status")
async def get_2fa_status(current_user: User = Depends(get_current_user)):
    """Get current 2FA status for user"""
    return {
        "enabled": current_user.two_factor_enabled,
        "has_backup_codes": bool(current_user.backup_codes)
    }
