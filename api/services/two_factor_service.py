"""
Two-Factor Authentication Service
Implements TOTP (Time-based One-Time Password) for 2FA
"""
import json
import secrets
import pyotp
import qrcode
import io
import base64
from typing import Optional, Tuple, List

from src.crypto_utils import encrypt_api_key, decrypt_api_key


def generate_totp_secret() -> str:
    """Generate a new TOTP secret key"""
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str, issuer: str = "CryptoBot") -> str:
    """Generate the provisioning URI for QR code"""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=issuer)


def generate_qr_code_base64(uri: str) -> str:
    """Generate QR code as base64 encoded PNG"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def verify_totp(secret: str, code: str) -> bool:
    """
    Verify a TOTP code.
    Allows 1 window before/after for clock drift.
    """
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
    except Exception:
        return False


def generate_backup_codes(count: int = 8) -> List[str]:
    """
    Generate backup codes for account recovery.
    Each code is 8 characters of hex.
    """
    return [secrets.token_hex(4).upper() for _ in range(count)]


def encrypt_totp_secret(secret: str, user_id: int) -> str:
    """Encrypt TOTP secret for storage"""
    return encrypt_api_key(secret, user_id)


def decrypt_totp_secret(encrypted_secret: str, user_id: int) -> str:
    """Decrypt TOTP secret for verification"""
    return decrypt_api_key(encrypted_secret, user_id)


def encrypt_backup_codes(codes: List[str], user_id: int) -> str:
    """Encrypt backup codes as JSON for storage"""
    codes_json = json.dumps(codes)
    return encrypt_api_key(codes_json, user_id)


def decrypt_backup_codes(encrypted_codes: str, user_id: int) -> List[str]:
    """Decrypt backup codes from storage"""
    try:
        codes_json = decrypt_api_key(encrypted_codes, user_id)
        return json.loads(codes_json)
    except Exception:
        return []


def verify_backup_code(encrypted_codes: str, user_id: int, code: str) -> Tuple[bool, Optional[str]]:
    """
    Verify a backup code and return remaining codes.
    
    Returns:
        Tuple of (is_valid, new_encrypted_codes_or_none)
    """
    codes = decrypt_backup_codes(encrypted_codes, user_id)
    code_upper = code.upper().replace("-", "").replace(" ", "")
    
    if code_upper in codes:
        codes.remove(code_upper)
        new_encrypted = encrypt_backup_codes(codes, user_id) if codes else None
        return True, new_encrypted
    
    return False, None


def setup_2fa_for_user(user_id: int, username: str) -> dict:
    """
    Initialize 2FA setup for a user.
    
    Returns dict with:
    - secret: The raw TOTP secret (to be encrypted and stored)
    - encrypted_secret: Encrypted version for DB
    - qr_code_base64: QR code image as base64
    - backup_codes: List of backup codes
    - encrypted_backup_codes: Encrypted backup codes for DB
    """
    secret = generate_totp_secret()
    uri = get_totp_uri(secret, username)
    qr_code = generate_qr_code_base64(uri)
    backup_codes = generate_backup_codes()
    
    return {
        "secret": secret,
        "encrypted_secret": encrypt_totp_secret(secret, user_id),
        "qr_code_base64": qr_code,
        "manual_entry_key": secret,  # For manual entry if QR doesn't work
        "backup_codes": backup_codes,
        "encrypted_backup_codes": encrypt_backup_codes(backup_codes, user_id)
    }
