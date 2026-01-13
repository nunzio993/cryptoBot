"""
Orders routes - CRUD per ordini trading
"""
from datetime import datetime, timezone
from typing import Optional, List
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from models import Order, User, Exchange, APIKey
from api.deps import get_db, get_current_user
from src.adapters import BinanceAdapter
from src.core_and_scheduler import fetch_last_closed_candle

router = APIRouter()


class PositionInfo(BaseModel):
    order_id: int
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    current_value: float
    pnl: float
    pnl_percent: float
    take_profit: Optional[float]
    stop_loss: Optional[float]


class PortfolioResponse(BaseModel):
    usdc_total: float
    usdc_free: float
    usdc_locked: float
    usdc_blocked: float  # Riservato per ordini PENDING
    usdc_available: float  # usdc_free - usdc_blocked
    positions_value: float  # Valore corrente delle posizioni
    portfolio_total: float  # usdc_total + positions_value
    positions: List[PositionInfo]


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    api_key_id: Optional[int] = Query(None, description="Specific API key ID to use"),
    network_mode: str = Query("Mainnet", description="Fallback if api_key_id not provided"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Calcola il portfolio completo con P&L delle posizioni per una specifica API key"""
    
    # Get API key - either by ID or by network_mode fallback
    if api_key_id:
        key = db.query(APIKey).filter(
            APIKey.id == api_key_id,
            APIKey.user_id == current_user.id
        ).first()
        if not key:
            raise HTTPException(status_code=400, detail="API key not found")
    else:
        # Fallback to network_mode for backward compatibility
        exchange = db.query(Exchange).filter_by(name="binance").first()
        if not exchange:
            raise HTTPException(status_code=400, detail="Exchange not found")
        key = db.query(APIKey).filter_by(
            user_id=current_user.id,
            exchange_id=exchange.id,
            is_testnet=(network_mode == "Testnet")
        ).first()
        if not key:
            raise HTTPException(status_code=400, detail=f"No API key for {network_mode}")
    
    # Get exchange info
    exchange = db.query(Exchange).filter_by(id=key.exchange_id).first()
    
    # Create adapter using ExchangeFactory with decrypted keys
    from src.exchange_factory import ExchangeFactory
    from src.crypto_utils import decrypt_api_key
    
    decrypted_key = decrypt_api_key(key.api_key, current_user.id)
    decrypted_secret = decrypt_api_key(key.secret_key, current_user.id)
    
    adapter = ExchangeFactory.create(
        exchange.name, 
        decrypted_key, 
        decrypted_secret, 
        testnet=key.is_testnet
    )
    
    # Get USDC balance
    try:
        usdc_free = adapter.get_balance("USDC")
        usdc_locked = 0  # Most adapters don't separate locked
        if hasattr(adapter, 'client'):
            usdc_balance = adapter.client.get_asset_balance(asset="USDC")
            usdc_free = float(usdc_balance['free'])
            usdc_locked = float(usdc_balance['locked'])
        usdc_total = usdc_free + usdc_locked
    except Exception:
        usdc_free = 0
        usdc_locked = 0
        usdc_total = 0
    
    # Get pending orders for THIS API key (same exchange_id and is_testnet)
    pending_orders = db.query(Order).filter(
        Order.user_id == current_user.id,
        Order.status == "PENDING",
        Order.exchange_id == key.exchange_id,
        Order.is_testnet == key.is_testnet
    ).all()
    
    usdc_blocked = sum(float(o.quantity or 0) * float(o.max_entry or 0) for o in pending_orders)
    usdc_available = max(0, usdc_free - usdc_blocked)
    
    # Get executed orders for THIS API key (include PARTIAL_FILLED)
    executed_orders = db.query(Order).filter(
        Order.user_id == current_user.id,
        Order.status.in_(["EXECUTED", "PARTIAL_FILLED"]),
        Order.exchange_id == key.exchange_id,
        Order.is_testnet == key.is_testnet
    ).all()
    
    positions = []
    positions_value = 0
    
    for order in executed_orders:
        try:
            if hasattr(adapter, 'client'):
                ticker = adapter.client.get_symbol_ticker(symbol=order.symbol)
                current_price = float(ticker['price'])
            else:
                current_price = float(order.executed_price or order.entry_price or 0)
        except:
            current_price = float(order.executed_price or order.entry_price or 0)
        
        entry_price = float(order.executed_price or order.entry_price or 0)
        quantity = float(order.quantity or 0)
        current_value = quantity * current_price
        pnl = current_value - (quantity * entry_price)
        pnl_percent = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        
        positions_value += current_value
        
        positions.append(PositionInfo(
            order_id=order.id,
            symbol=order.symbol,
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            current_value=current_value,
            pnl=pnl,
            pnl_percent=pnl_percent,
            take_profit=float(order.take_profit) if order.take_profit else None,
            stop_loss=float(order.stop_loss) if order.stop_loss else None,
        ))
    
    # Get ALL crypto balances from exchange (not just tracked positions)
    crypto_total_value = 0
    stablecoins = ['USDC', 'USDT', 'BUSD', 'DAI', 'TUSD', 'USDP', 'FDUSD']
    
    try:
        if hasattr(adapter, 'client'):
            # Get all prices in ONE call (much faster)
            all_tickers = adapter.client.get_all_tickers()
            prices = {t['symbol']: float(t['price']) for t in all_tickers}
            
            # Get all account balances
            account_info = adapter.client.get_account()
            balances = account_info.get('balances', [])
            
            for balance in balances:
                asset = balance['asset']
                total_amount = float(balance['free']) + float(balance['locked'])
                
                if total_amount <= 0.0001:  # Skip dust
                    continue
                    
                # Skip stablecoins (they're counted separately)
                if asset in stablecoins:
                    continue
                
                # Get price in USDC or USDT
                usdc_pair = f"{asset}USDC"
                usdt_pair = f"{asset}USDT"
                
                if usdc_pair in prices:
                    crypto_total_value += total_amount * prices[usdc_pair]
                elif usdt_pair in prices:
                    crypto_total_value += total_amount * prices[usdt_pair]
                # else: can't price this asset, skip
    except Exception as e:
        # If we can't get all balances, fall back to positions_value
        crypto_total_value = positions_value
    
    # Total portfolio = USDC + all crypto value
    portfolio_total = usdc_total + crypto_total_value
    
    return PortfolioResponse(
        usdc_total=usdc_total,
        usdc_free=usdc_free,
        usdc_locked=usdc_locked,
        usdc_blocked=usdc_blocked,
        usdc_available=usdc_available,
        positions_value=crypto_total_value,  # Now includes ALL crypto, not just tracked
        portfolio_total=portfolio_total,
        positions=positions
    )


class HoldingInfo(BaseModel):
    asset: str
    symbol: str  # e.g. BTCUSDC
    quantity: float
    avg_price: float  # Estimated entry price
    current_price: float
    current_value: float
    pnl: float
    pnl_percent: float


class HoldingsResponse(BaseModel):
    holdings: List[HoldingInfo]
    total_value: float
    page: int
    total_pages: int


@router.get("/holdings", response_model=HoldingsResponse)
async def get_holdings(
    api_key_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get all crypto holdings from exchange (not just tracked orders)"""
    
    if not api_key_id:
        raise HTTPException(status_code=400, detail="api_key_id required")
    
    key = db.query(APIKey).filter(
        APIKey.id == api_key_id,
        APIKey.user_id == current_user.id
    ).first()
    
    if not key:
        raise HTTPException(status_code=400, detail="API key not found")
    
    exchange = db.query(Exchange).filter_by(id=key.exchange_id).first()
    
    from src.exchange_factory import ExchangeFactory
    from src.crypto_utils import decrypt_api_key
    
    decrypted_key = decrypt_api_key(key.api_key, current_user.id)
    decrypted_secret = decrypt_api_key(key.secret_key, current_user.id)
    
    adapter = ExchangeFactory.create(
        exchange.name, decrypted_key, decrypted_secret, testnet=key.is_testnet
    )
    
    stablecoins = ['USDC', 'USDT', 'BUSD', 'DAI', 'TUSD', 'USDP', 'FDUSD']
    holdings = []
    total_value = 0
    
    try:
        if hasattr(adapter, 'client'):
            all_tickers = adapter.client.get_all_tickers()
            prices = {t['symbol']: float(t['price']) for t in all_tickers}
            
            account_info = adapter.client.get_account()
            balances = account_info.get('balances', [])
            
            for balance in balances:
                asset = balance['asset']
                quantity = float(balance['free']) + float(balance['locked'])
                
                if quantity <= 0.0001 or asset in stablecoins:
                    continue
                
                # Find price
                usdc_pair = f"{asset}USDC"
                usdt_pair = f"{asset}USDT"
                
                current_price = 0
                symbol = usdc_pair
                
                if usdc_pair in prices:
                    current_price = prices[usdc_pair]
                    symbol = usdc_pair
                elif usdt_pair in prices:
                    current_price = prices[usdt_pair]
                    symbol = usdt_pair
                else:
                    continue
                
                current_value = quantity * current_price
                total_value += current_value
                
                # Estimate avg price (we don't know actual entry, use current as placeholder)
                avg_price = current_price
                pnl = 0
                pnl_percent = 0
                
                holdings.append(HoldingInfo(
                    asset=asset,
                    symbol=symbol,
                    quantity=quantity,
                    avg_price=avg_price,
                    current_price=current_price,
                    current_value=current_value,
                    pnl=pnl,
                    pnl_percent=pnl_percent
                ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching holdings: {str(e)}")
    
    # Sort by value descending
    holdings.sort(key=lambda h: h.current_value, reverse=True)
    
    # Paginate
    total_items = len(holdings)
    total_pages = (total_items + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    
    return HoldingsResponse(
        holdings=holdings[start:end],
        total_value=total_value,
        page=page,
        total_pages=total_pages
    )


class OrderCreate(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    max_entry: float
    take_profit: float
    stop_loss: float
    entry_interval: str
    stop_interval: str


class HoldingOrderCreate(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    take_profit: float
    stop_loss: float
    stop_interval: str
    api_key_id: int


@router.post("/from-holding")
async def create_order_from_holding(
    order_data: HoldingOrderCreate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Create an EXECUTED order from an external holding (crypto bought outside the app)"""
    
    # Get API key
    key = db.query(APIKey).filter(
        APIKey.id == order_data.api_key_id,
        APIKey.user_id == current_user.id
    ).first()
    
    if not key:
        raise HTTPException(status_code=400, detail="API key not found")
    
    exchange = db.query(Exchange).filter_by(id=key.exchange_id).first()
    
    # Create adapter to place TP on exchange
    from src.exchange_factory import ExchangeFactory
    from src.crypto_utils import decrypt_api_key
    
    decrypted_key = decrypt_api_key(key.api_key, current_user.id)
    decrypted_secret = decrypt_api_key(key.secret_key, current_user.id)
    
    adapter = ExchangeFactory.create(
        exchange.name, decrypted_key, decrypted_secret, testnet=key.is_testnet
    )
    
    # Get symbol info for quantity formatting
    symbol_info = adapter.client.get_symbol_info(order_data.symbol)
    filters = {f['filterType']: f for f in symbol_info['filters']}
    step_size = float(filters['LOT_SIZE']['stepSize'])
    tick_size = float(filters['PRICE_FILTER']['tickSize'])
    
    # Format quantity and price
    from decimal import Decimal, ROUND_DOWN
    qty = Decimal(str(order_data.quantity)).quantize(Decimal(str(step_size)), rounding=ROUND_DOWN)
    tp_price = Decimal(str(order_data.take_profit)).quantize(Decimal(str(tick_size)), rounding=ROUND_DOWN)
    
    # Place TP LIMIT order on exchange
    try:
        adapter.client.create_order(
            symbol=order_data.symbol,
            side='SELL',
            type='LIMIT',
            timeInForce='GTC',
            quantity=str(qty),
            price=str(tp_price)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to place TP order on exchange: {str(e)}")
    
    # Create order in EXECUTED state (we already own the crypto)
    order = Order(
        user_id=current_user.id,
        symbol=order_data.symbol,
        quantity=float(qty),
        entry_price=order_data.entry_price,
        max_entry=order_data.entry_price,
        take_profit=float(tp_price),
        stop_loss=order_data.stop_loss,
        entry_interval="1m",
        stop_interval=order_data.stop_interval,
        status="EXECUTED",
        is_testnet=key.is_testnet,
        exchange_id=key.exchange_id,
        executed_price=order_data.entry_price,
        executed_at=datetime.now(timezone.utc)
    )
    
    db.add(order)
    db.commit()
    db.refresh(order)
    
    return {
        "id": order.id,
        "symbol": order.symbol,
        "side": order.side,
        "quantity": float(order.quantity),
        "status": order.status,
        "entry_price": float(order.entry_price) if order.entry_price else None,
        "max_entry": float(order.max_entry) if order.max_entry else None,
        "take_profit": float(order.take_profit) if order.take_profit else None,
        "stop_loss": float(order.stop_loss) if order.stop_loss else None,
        "entry_interval": order.entry_interval,
        "stop_interval": order.stop_interval,
        "executed_price": float(order.executed_price) if order.executed_price else None,
        "executed_at": order.executed_at.isoformat() if order.executed_at else None,
        "closed_at": None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "is_testnet": order.is_testnet,
        "message": "TP order placed on exchange"
    }


class OrderUpdate(BaseModel):
    entry_price: Optional[float] = None
    max_entry: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None


class OrderResponse(BaseModel):
    id: int
    symbol: str
    side: str
    quantity: float
    status: str
    entry_price: Optional[float]
    max_entry: Optional[float]
    take_profit: Optional[float]
    stop_loss: Optional[float]
    entry_interval: Optional[str]
    stop_interval: Optional[str]
    executed_price: Optional[float]
    executed_at: Optional[datetime]
    closed_at: Optional[datetime]
    created_at: Optional[datetime]
    is_testnet: Optional[bool]

    class Config:
        from_attributes = True


@router.get("", response_model=List[OrderResponse])
async def list_orders(
    status: Optional[str] = Query(None, description="Filter by status"),
    api_key_id: Optional[int] = Query(None, description="Filter by API key"),
    network_mode: Optional[str] = Query(None, description="Fallback filter"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    query = db.query(Order).filter(Order.user_id == current_user.id)
    
    # Filter by API key if provided
    if api_key_id:
        key = db.query(APIKey).filter(
            APIKey.id == api_key_id,
            APIKey.user_id == current_user.id
        ).first()
        if key:
            query = query.filter(
                Order.exchange_id == key.exchange_id,
                Order.is_testnet == key.is_testnet
            )
    elif network_mode:
        # Fallback to network_mode filter
        query = query.filter(Order.is_testnet == (network_mode == "Testnet"))
    
    if status:
        if status == "CLOSED":
            query = query.filter(Order.status.in_(["CLOSED_TP", "CLOSED_SL", "CLOSED_MANUAL", "CANCELLED", "CLOSED_EXTERNALLY"]))
        else:
            query = query.filter(Order.status == status)
    
    return query.order_by(Order.created_at.desc()).all()


@router.post("", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    network_mode: str = Query("Testnet", description="Testnet or Mainnet"),
    exchange_name: str = Query("binance", description="Exchange: binance, bybit"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    # Validation
    if not (order_data.stop_loss < order_data.entry_price < order_data.take_profit):
        raise HTTPException(status_code=400, detail="Must be: Stop Loss < Entry Price < Take Profit")
    
    if order_data.max_entry < order_data.entry_price:
        raise HTTPException(status_code=400, detail="Max Entry must be >= Entry Price")
    
    # Get API key for specified exchange
    exchange = db.query(Exchange).filter_by(name=exchange_name.lower()).first()
    if not exchange:
        raise HTTPException(status_code=400, detail=f"Exchange '{exchange_name}' not found")
    
    key = db.query(APIKey).filter_by(
        user_id=current_user.id,
        exchange_id=exchange.id,
        is_testnet=(network_mode == "Testnet")
    ).first()
    
    if not key:
        raise HTTPException(status_code=400, detail=f"No API key configured for {exchange_name} {network_mode}")
    
    # Use ExchangeFactory to create adapter with decrypted keys
    from src.exchange_factory import ExchangeFactory
    from src.crypto_utils import decrypt_api_key
    
    decrypted_key = decrypt_api_key(key.api_key, current_user.id)
    decrypted_secret = decrypt_api_key(key.secret_key, current_user.id)
    
    adapter = ExchangeFactory.create(exchange_name, decrypted_key, decrypted_secret, testnet=(network_mode == "Testnet"))
    
    is_market_order = order_data.entry_interval == "Market"
    
    if not is_market_order:
        # Check last candle for non-market orders (only for Binance currently)
        if exchange_name.lower() == "binance":
            try:
                last_close = float(fetch_last_closed_candle(order_data.symbol, order_data.entry_interval, adapter.client)[4])
                if last_close >= order_data.take_profit:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Previous {order_data.entry_interval} candle ({last_close:.2f}) >= TP; order not placed"
                    )
            except HTTPException:
                raise
            except Exception:
                pass  # Allow order creation even if candle check fails
    
    # Create order with exchange_id
    order = Order(
        user_id=current_user.id,
        exchange_id=exchange.id,
        symbol=order_data.symbol,
        side="LONG",
        quantity=Decimal(str(order_data.quantity)),
        status="PENDING",
        entry_price=Decimal(str(order_data.entry_price)),
        max_entry=Decimal(str(order_data.max_entry)),
        take_profit=Decimal(str(order_data.take_profit)),
        stop_loss=Decimal(str(order_data.stop_loss)),
        entry_interval=order_data.entry_interval,
        stop_interval=order_data.stop_interval,
        created_at=datetime.now(timezone.utc),
        is_testnet=(network_mode == "Testnet")
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    
    # Execute immediately for Market orders
    if is_market_order:
        try:
            # Get symbol info for precision
            symbol_info = adapter.client.get_symbol_info(order_data.symbol)
            filters = {f['filterType']: f for f in symbol_info['filters']}
            step_size = float(filters['LOT_SIZE']['stepSize'])
            min_qty = float(filters['LOT_SIZE']['minQty'])
            min_notional = float(filters.get('NOTIONAL', filters.get('MIN_NOTIONAL', {})).get('minNotional', 0))
            
            # Round quantity DOWN to step size (Binance requirement)
            import math
            qty = math.floor(float(order_data.quantity) / step_size) * step_size
            
            # Check minimum quantity
            if qty < min_qty:
                raise Exception(f"Quantity {qty} below minimum {min_qty}")
            
            # Check minimum notional
            current_price = float(adapter.client.get_symbol_ticker(symbol=order_data.symbol)['price'])
            notional = qty * current_price
            if notional < min_notional:
                raise Exception(f"Order value ${notional:.2f} below minimum ${min_notional:.2f}")
            
            # Format quantity as string
            qty_str = ('{:.8f}'.format(qty)).rstrip('0').rstrip('.')
            
            # Place market buy order
            market_order = adapter.client.order_market_buy(
                symbol=order_data.symbol,
                quantity=qty_str
            )
            
            # Get executed price
            executed_price = float(market_order.get('fills', [{}])[0].get('price', order_data.entry_price))
            
            # Update order status
            order.status = "EXECUTED"
            order.executed_price = Decimal(str(executed_price))
            order.executed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(order)
            
            # Set up TP/SL with OCO order
            try:
                adapter.update_spot_tp_sl(
                    order_data.symbol,
                    qty,
                    float(order_data.take_profit),
                    float(order_data.stop_loss),
                    user_id=current_user.id
                )
            except Exception as e:
                # TP/SL setup failed but order was executed
                pass
                
        except Exception as e:
            # Market order failed - mark as cancelled
            order.status = "CANCELLED"
            order.closed_at = datetime.now(timezone.utc)
            db.commit()
            raise HTTPException(status_code=400, detail=f"Market order failed: {str(e)}")
    
    return order


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    order_data: OrderUpdate,
    network_mode: str = Query("Testnet"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Update fields
    if order_data.entry_price is not None:
        order.entry_price = Decimal(str(order_data.entry_price))
    if order_data.max_entry is not None:
        order.max_entry = Decimal(str(order_data.max_entry))
    if order_data.take_profit is not None:
        order.take_profit = Decimal(str(order_data.take_profit))
    if order_data.stop_loss is not None:
        order.stop_loss = Decimal(str(order_data.stop_loss))
    
    # If EXECUTED, update on Binance too
    if order.status == "EXECUTED" and (order_data.take_profit or order_data.stop_loss):
        exchange = db.query(Exchange).filter_by(name="binance").first()
        key = db.query(APIKey).filter_by(
            user_id=current_user.id,
            exchange_id=exchange.id,
            is_testnet=(network_mode == "Testnet")
        ).first()
        
        if key:
            from src.crypto_utils import decrypt_api_key
            decrypted_key = decrypt_api_key(key.api_key, current_user.id)
            decrypted_secret = decrypt_api_key(key.secret_key, current_user.id)
            adapter = BinanceAdapter(decrypted_key, decrypted_secret, testnet=(network_mode == "Testnet"))
            try:
                adapter.update_spot_tp_sl(
                    order.symbol,
                    float(order.quantity),
                    float(order.take_profit),
                    float(order.stop_loss),
                    user_id=current_user.id
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to update on Binance: {str(e)}")
    
    db.commit()
    db.refresh(order)
    return order


@router.delete("/{order_id}")
async def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status not in ["PENDING"]:
        raise HTTPException(status_code=400, detail="Can only cancel PENDING orders")
    
    order.status = "CANCELLED"
    order.closed_at = datetime.now(timezone.utc)
    db.commit()
    
    return {"message": f"Order {order_id} cancelled"}


@router.post("/{order_id}/close")
async def close_order(
    order_id: int,
    network_mode: str = Query("Testnet"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status != "EXECUTED":
        raise HTTPException(status_code=400, detail="Can only close EXECUTED orders")
    
    # Get adapter
    exchange = db.query(Exchange).filter_by(name="binance").first()
    key = db.query(APIKey).filter_by(
        user_id=current_user.id,
        exchange_id=exchange.id,
        is_testnet=(network_mode == "Testnet")
    ).first()
    
    if not key:
        raise HTTPException(status_code=400, detail="No API key configured")
    
    from src.crypto_utils import decrypt_api_key
    decrypted_key = decrypt_api_key(key.api_key, current_user.id)
    decrypted_secret = decrypt_api_key(key.secret_key, current_user.id)
    
    adapter = BinanceAdapter(decrypted_key, decrypted_secret, testnet=(network_mode == "Testnet"))
    
    try:
        asset_name = order.symbol.replace("USDC", "")
        balance = adapter.get_balance(asset_name)
        
        symbol_info = adapter.client.get_symbol_info(order.symbol)
        filters = {f['filterType']: f for f in symbol_info['filters']}
        step_size = float(filters['LOT_SIZE']['stepSize'])
        
        if balance < step_size:
            order.status = "CLOSED_EXTERNALLY"
            order.closed_at = datetime.now(timezone.utc)
            db.commit()
            return {"message": "Balance too low, marked as externally closed"}
        
        qty_to_close = min(float(order.quantity), balance)
        adapter.close_position_market(order.symbol, qty_to_close)
        
        order.status = "CLOSED_MANUAL"
        order.closed_at = datetime.now(timezone.utc)
        db.commit()
        
        return {"message": f"Order {order_id} closed manually"}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to close order: {str(e)}")
