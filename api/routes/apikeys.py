"""
API Keys management routes
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from models import User, Exchange, APIKey
from api.deps import get_db, get_current_user
from src.crypto_utils import encrypt_api_key, decrypt_api_key

router = APIRouter()


class APIKeyCreate(BaseModel):
    exchange_name: str
    api_key: str
    secret_key: str
    is_testnet: bool = True
    name: Optional[str] = None  # Custom name for the account


class APIKeyUpdate(BaseModel):
    api_key: Optional[str] = None
    secret_key: Optional[str] = None
    name: Optional[str] = None


class APIKeyResponse(BaseModel):
    id: int
    name: Optional[str]
    exchange_name: str
    api_key_masked: str
    is_testnet: bool
    created_at: Optional[datetime]


@router.get("", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    keys = db.query(APIKey).filter(APIKey.user_id == current_user.id).all()
    result = []
    for key in keys:
        exchange = db.query(Exchange).filter(Exchange.id == key.exchange_id).first()
        result.append(APIKeyResponse(
            id=key.id,
            name=key.name,
            exchange_name=exchange.name if exchange else "unknown",
            api_key_masked=key.api_key[:8] + "..." + key.api_key[-4:] if len(key.api_key) > 12 else "***",
            is_testnet=key.is_testnet,
            created_at=key.created_at
        ))
    return result


@router.post("", response_model=APIKeyResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    exchange = db.query(Exchange).filter(Exchange.name == key_data.exchange_name).first()
    if not exchange:
        raise HTTPException(status_code=400, detail=f"Exchange '{key_data.exchange_name}' not found")
    
    # Check if already exists
    existing = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.exchange_id == exchange.id,
        APIKey.is_testnet == key_data.is_testnet
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"API key for {key_data.exchange_name} {'Testnet' if key_data.is_testnet else 'Mainnet'} already exists. Use PUT to update."
        )
    
    # Generate default name if not provided
    default_name = f"{key_data.exchange_name.title()} {'Testnet' if key_data.is_testnet else 'Mainnet'}"
    
    # Encrypt API keys before storing
    encrypted_api_key = encrypt_api_key(key_data.api_key, current_user.id)
    encrypted_secret = encrypt_api_key(key_data.secret_key, current_user.id)
    
    api_key = APIKey(
        user_id=current_user.id,
        exchange_id=exchange.id,
        name=key_data.name or default_name,
        api_key=encrypted_api_key,
        secret_key=encrypted_secret,
        is_testnet=key_data.is_testnet
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    # Mask original (unencrypted) key for response
    masked_key = key_data.api_key[:8] + "..." + key_data.api_key[-4:]
    
    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        exchange_name=key_data.exchange_name,
        api_key_masked=masked_key,
        is_testnet=api_key.is_testnet,
        created_at=api_key.created_at
    )


@router.put("/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: int,
    key_data: APIKeyUpdate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    if key_data.api_key:
        api_key.api_key = encrypt_api_key(key_data.api_key, current_user.id)
    if key_data.secret_key:
        api_key.secret_key = encrypt_api_key(key_data.secret_key, current_user.id)
    if key_data.name is not None:
        api_key.name = key_data.name
    
    db.commit()
    db.refresh(api_key)
    
    exchange = db.query(Exchange).filter(Exchange.id == api_key.exchange_id).first()
    
    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        exchange_name=exchange.name if exchange else "unknown",
        api_key_masked="***updated***" if key_data.api_key else api_key.api_key[:8] + "..." if len(api_key.api_key) > 12 else "***",
        is_testnet=api_key.is_testnet,
        created_at=api_key.created_at
    )


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    db.delete(api_key)
    db.commit()
    
    return {"message": f"API key {key_id} deleted"}
