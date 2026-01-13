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
    network_mode: str = Query("Testnet"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
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
    
    adapter = BinanceAdapter(key.api_key, key.secret_key, testnet=(network_mode == "Testnet"))
    
    try:
        balance = adapter.client.get_asset_balance(asset=asset)
        return BalanceResponse(
            asset=asset,
            free=float(balance['free']),
            locked=float(balance['locked']),
            total=float(balance['free']) + float(balance['locked'])
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
    network_mode: str = Query("Testnet"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    exchange = db.query(Exchange).filter_by(name="binance").first()
    key = db.query(APIKey).filter_by(
        user_id=current_user.id,
        exchange_id=exchange.id,
        is_testnet=(network_mode == "Testnet")
    ).first()
    
    if not key:
        raise HTTPException(status_code=400, detail="No API key configured")
    
    adapter = BinanceAdapter(key.api_key, key.secret_key, testnet=(network_mode == "Testnet"))
    
    try:
        price = adapter.get_symbol_price(symbol)
        return {"symbol": symbol, "price": price}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get price: {str(e)}")
