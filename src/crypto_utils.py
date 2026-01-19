"""
Cryptography utilities for secure API key storage
Uses Fernet (AES-128-CBC with HMAC) for symmetric encryption
"""
import os
import base64
import hashlib
from cryptography.fernet import Fernet

# Get master key from environment - REQUIRED
MASTER_KEY = os.getenv("SECRET_KEY")
if not MASTER_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required. Set it in .env file.")


def _derive_key(user_id: int) -> bytes:
    """
    Derive a unique encryption key for each user using PBKDF2.
    This ensures that even if one user's data is compromised,
    other users' data remains secure.
    """
    key = hashlib.pbkdf2_hmac(
        'sha256',
        MASTER_KEY.encode(),
        f"user:{user_id}:salt".encode(),
        100000  # iterations
    )
    # Fernet requires 32 bytes, base64 encoded
    return base64.urlsafe_b64encode(key[:32])


def encrypt_api_key(plaintext: str, user_id: int) -> str:
    """
    Encrypt an API key for storage in database.
    
    Args:
        plaintext: The raw API key to encrypt
        user_id: User ID for key derivation
        
    Returns:
        Encrypted string safe for database storage
    """
    if not plaintext:
        return ""
    
    fernet = Fernet(_derive_key(user_id))
    encrypted = fernet.encrypt(plaintext.encode())
    return encrypted.decode('utf-8')


def decrypt_api_key(ciphertext: str, user_id: int) -> str:
    """
    Decrypt an API key from database.
    
    Args:
        ciphertext: The encrypted API key from database
        user_id: User ID for key derivation
        
    Returns:
        Decrypted plaintext API key
    """
    if not ciphertext:
        return ""
    
    try:
        fernet = Fernet(_derive_key(user_id))
        decrypted = fernet.decrypt(ciphertext.encode())
        return decrypted.decode('utf-8')
    except Exception as e:
        # Don't silently return ciphertext - this would cause auth failures
        # and make debugging difficult. Fail explicitly instead.
        raise ValueError(
            f"Failed to decrypt API key for user {user_id}. "
            f"Check SECRET_KEY configuration. Error: {e}"
        )


def is_encrypted(value: str) -> bool:
    """Check if a value appears to be Fernet encrypted"""
    try:
        # Fernet tokens are base64 encoded and start with 'gAAAAA'
        return value.startswith('gAAAAA') and len(value) > 100
    except:
        return False
