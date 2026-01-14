"""
Exchange routes - Balance, symbols, etc.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from models import User, Exchange, APIKey
from api.deps import get_db, get_current_user
from src.adapters import BinanceAdapter
from symbols import SYMBOLS

router = APIRouter()


class BalanceResponse(BaseModel):
    asset: str
    free: float
    locked: float
    total: float


class SymbolResponse(BaseModel):
    symbol: str


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    asset: str = Query("USDC"),
    api_key_id: int = Query(None, description="API key ID to use"),
    network_mode: str = Query("Testnet"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    from src.exchange_factory import ExchangeFactory
    from src.crypto_utils import decrypt_api_key
    
    # Get API key
    if api_key_id:
        key = db.query(APIKey).filter(
            APIKey.id == api_key_id,
            APIKey.user_id == current_user.id
        ).first()
    else:
        # Fallback to binance for backward compatibility
        exchange = db.query(Exchange).filter_by(name="binance").first()
        if not exchange:
            raise HTTPException(status_code=400, detail="Exchange 'binance' not found")
        key = db.query(APIKey).filter_by(
            user_id=current_user.id,
            exchange_id=exchange.id,
            is_testnet=(network_mode == "Testnet")
        ).first()
    
    if not key:
        raise HTTPException(status_code=400, detail=f"No API key configured for {network_mode}")
    
    # Get exchange name
    exchange = db.query(Exchange).filter_by(id=key.exchange_id).first()
    
    # Decrypt keys
    decrypted_key = decrypt_api_key(key.api_key, current_user.id)
    decrypted_secret = decrypt_api_key(key.secret_key, current_user.id)
    
    adapter = ExchangeFactory.create(
        exchange.name, 
        decrypted_key, 
        decrypted_secret, 
        testnet=key.is_testnet
    )
    
    try:
        # Use adapter's get_balance method
        free_balance = adapter.get_balance(asset)
        return BalanceResponse(
            asset=asset,
            free=free_balance,
            locked=0.0,  # Most adapters don't separate locked
            total=free_balance
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get balance: {str(e)}")


@router.get("/symbols", response_model=List[SymbolResponse])
async def get_symbols(
    quote_asset: str = Query("USDC", description="Filter by quote asset")
):
    filtered = [s for s in SYMBOLS if s.endswith(quote_asset)]
    return [SymbolResponse(symbol=s) for s in filtered]


@router.get("/price")
async def get_price(
    symbol: str,
    api_key_id: int = Query(None, description="API key ID to use"),
    network_mode: str = Query("Testnet"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    from src.exchange_factory import ExchangeFactory
    from src.crypto_utils import decrypt_api_key
    
    # Get API key
    if api_key_id:
        key = db.query(APIKey).filter(
            APIKey.id == api_key_id,
            APIKey.user_id == current_user.id
        ).first()
    else:
        # Fallback to binance for backward compatibility
        exchange = db.query(Exchange).filter_by(name="binance").first()
        key = db.query(APIKey).filter_by(
            user_id=current_user.id,
            exchange_id=exchange.id,
            is_testnet=(network_mode == "Testnet")
        ).first()
    
    if not key:
        raise HTTPException(status_code=400, detail="No API key configured")
    
    # Get exchange name
    exchange = db.query(Exchange).filter_by(id=key.exchange_id).first()
    
    # Decrypt keys
    decrypted_key = decrypt_api_key(key.api_key, current_user.id)
    decrypted_secret = decrypt_api_key(key.secret_key, current_user.id)
    
    adapter = ExchangeFactory.create(
        exchange.name, 
        decrypted_key, 
        decrypted_secret, 
        testnet=key.is_testnet
    )
    
    try:
        price = adapter.get_symbol_price(symbol)
        return {"symbol": symbol, "price": price}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get price: {str(e)}")

