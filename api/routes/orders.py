"""
Orders routes - CRUD per ordini trading
"""
from datetime import datetime, timezone
from typing import Optional, List
from decimal import Decimal
from types import SimpleNamespace
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from models import Order, User, Exchange, APIKey
from api.deps import get_db, get_current_user
from src.adapters import BinanceAdapter
from src.core_and_scheduler import fetch_last_closed_candle
from src.telegram_notifications import notify_open, notify_close
from src.trading_utils import format_quantity, format_price as trading_format_price

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
        
        # Check if quantity is below minimum sellable (skip dust positions)
        try:
            if hasattr(adapter, 'client'):
                symbol_info = adapter.get_symbol_info(order.symbol)
                if symbol_info:
                    filters = {f['filterType']: f for f in symbol_info['filters']}
                    min_qty = float(filters.get('LOT_SIZE', {}).get('minQty', 0))
                    if quantity < min_qty:
                        # Position too small to sell, skip it
                        continue
        except:
            pass  # If we can't check, show it anyway
        
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
    
    # Get symbols already tracked by app orders (EXECUTED or PARTIAL_FILLED)
    tracked_orders = db.query(Order).filter(
        Order.user_id == current_user.id,
        Order.exchange_id == key.exchange_id,
        Order.is_testnet == key.is_testnet,
        Order.status.in_(["EXECUTED", "PARTIAL_FILLED"])
    ).all()
    
    # Build a map of tracked quantities per asset
    tracked_quantities = {}
    for order in tracked_orders:
        # Remove quote currencies to get base asset
        base_asset = order.symbol
        for quote in ['USDC', 'USDT']:
            if base_asset.endswith(quote):
                base_asset = base_asset[:-len(quote)]
                break
        
        if base_asset not in tracked_quantities:
            tracked_quantities[base_asset] = 0
        tracked_quantities[base_asset] += float(order.quantity) if order.quantity else 0
    
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
                
                # Subtract quantity already tracked by app orders
                tracked_qty = tracked_quantities.get(asset, 0)
                external_qty = quantity - tracked_qty
                
                # Skip if no external quantity remains
                if external_qty <= 0.0001:
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
                
                current_value = external_qty * current_price
                total_value += current_value
                
                # Estimate avg price (we don't know actual entry, use current as placeholder)
                avg_price = current_price
                pnl = 0
                pnl_percent = 0
                
                holdings.append(HoldingInfo(
                    asset=asset,
                    symbol=symbol,
                    quantity=external_qty,
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
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    entry_interval: Optional[str] = "1m"
    stop_interval: Optional[str] = "1h"


class HoldingOrderCreate(BaseModel):
    symbol: str
    quantity: float
    entry_price: float
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    stop_interval: Optional[str] = "1h"
    api_key_id: int


@router.post("/from-holding")
async def create_order_from_holding(
    order_data: HoldingOrderCreate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Create an EXECUTED order from an external holding (crypto bought outside the app)"""
    
    from api.services.order_service import OrderService
    
    try:
        order = OrderService.create_from_holding(
            user_id=current_user.id,
            api_key_id=order_data.api_key_id,
            symbol=order_data.symbol,
            quantity=order_data.quantity,
            entry_price=order_data.entry_price,
            take_profit=order_data.take_profit,
            stop_loss=order_data.stop_loss,
            stop_interval=order_data.stop_interval,
            db_session=db
        )
        
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
            "message": "TP order placed on exchange" if order.tp_order_id else "Order created without TP"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class OrderUpdate(BaseModel):
    entry_price: Optional[float] = None
    max_entry: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    stop_interval: Optional[str] = None
    entry_interval: Optional[str] = None


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
    exchange_name: str = Query("binance", description="Exchange: binance, bybit (deprecated, use api_key_id)"),
    api_key_id: Optional[int] = Query(None, description="API key ID - if provided, exchange is inferred from this"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    # Validation - only require TP > SL (allow flexible positioning)
    if order_data.take_profit <= order_data.stop_loss:
        raise HTTPException(status_code=400, detail="Take Profit must be greater than Stop Loss")
    
    if order_data.max_entry < order_data.entry_price:
        raise HTTPException(status_code=400, detail="Max Entry must be >= Entry Price")
    
    # Get API key - prefer api_key_id if provided
    if api_key_id:
        key = db.query(APIKey).filter(
            APIKey.id == api_key_id,
            APIKey.user_id == current_user.id
        ).first()
        if not key:
            raise HTTPException(status_code=400, detail="API key not found")
        exchange = db.query(Exchange).filter_by(id=key.exchange_id).first()
        exchange_name = exchange.name
        print(f"[DEBUG] Using api_key_id={api_key_id}, inferred exchange={exchange_name}")
    else:
        # Fallback to exchange_name parameter
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
    
    # Check USDC balance before creating order
    order_value = float(order_data.quantity) * float(order_data.max_entry)
    print(f"[DEBUG] create_order: exchange={exchange_name}, order_value={order_value}")
    try:
        print(f"[DEBUG] About to call get_balance for USDC")
        usdc_balance = adapter.get_balance("USDC")
        print(f"[DEBUG] get_balance returned: {usdc_balance}")
        
        # Calculate already blocked USDC from pending orders
        pending_orders = db.query(Order).filter(
            Order.user_id == current_user.id,
            Order.status == "PENDING",
            Order.exchange_id == exchange.id,
            Order.is_testnet == (network_mode == "Testnet")
        ).all()
        blocked_usdc = sum(float(o.quantity) * float(o.max_entry or o.entry_price) for o in pending_orders)
        
        available_usdc = usdc_balance - blocked_usdc
        
        if order_value > available_usdc:
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient balance: required ${order_value:.2f}, available ${available_usdc:.2f} USDC"
            )
    except HTTPException:
        raise
    except Exception as e:
        # Log error but allow order creation if balance check fails
        print(f"[WARNING] Balance check failed: {e}")
    
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
            symbol_info = adapter.get_symbol_info(order_data.symbol)
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
            order.sl_updated_at = datetime.now(timezone.utc)  # For WebSocket handler grace period
            db.commit()
            
            # Send Telegram notification for market order execution
            try:
                notify_open(SimpleNamespace(
                    symbol=order.symbol,
                    quantity=float(order.quantity),
                    entry_price=executed_price,
                    user_id=current_user.id,
                    is_testnet=(network_mode == "Testnet")
                ), exchange_name=exchange_name)
            except Exception as notify_err:
                print(f"[WARNING] Telegram notification failed: {notify_err}")
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
    
    # Save old TP before updating (needed for identifying which exchange order to cancel)
    old_tp = float(order.take_profit) if order.take_profit else None
    
    # Update fields
    if order_data.entry_price is not None:
        order.entry_price = Decimal(str(order_data.entry_price))
    if order_data.max_entry is not None:
        order.max_entry = Decimal(str(order_data.max_entry))
    if order_data.take_profit is not None:
        order.take_profit = Decimal(str(order_data.take_profit))
        order.sl_updated_at = datetime.now(timezone.utc)  # Reset timing for TP_CHECK grace period
    if order_data.stop_loss is not None:
        order.stop_loss = Decimal(str(order_data.stop_loss))
        order.sl_updated_at = datetime.now(timezone.utc)  # Reset SL timing
    if order_data.stop_interval is not None:
        order.stop_interval = order_data.stop_interval
        order.sl_updated_at = datetime.now(timezone.utc)  # Reset SL timing
    if order_data.entry_interval is not None:
        order.entry_interval = order_data.entry_interval
    
    # If EXECUTED, update on exchange too
    if order.status == "EXECUTED" and (order_data.take_profit or order_data.stop_loss):
        # Get exchange from order's exchange_id
        if order.exchange_id:
            exchange = db.query(Exchange).filter_by(id=order.exchange_id).first()
            key = db.query(APIKey).filter_by(
                user_id=current_user.id,
                exchange_id=order.exchange_id,
                is_testnet=order.is_testnet if order.is_testnet is not None else (network_mode == "Testnet")
            ).first()
        else:
            # Fallback for old orders without exchange_id
            exchange = db.query(Exchange).filter_by(name="binance").first()
            key = db.query(APIKey).filter_by(
                user_id=current_user.id,
                exchange_id=exchange.id,
                is_testnet=order.is_testnet if order.is_testnet is not None else (network_mode == "Testnet")
            ).first()
        
        if key:
            from src.crypto_utils import decrypt_api_key
            from src.exchange_factory import ExchangeFactory
            
            decrypted_key = decrypt_api_key(key.api_key, current_user.id)
            decrypted_secret = decrypt_api_key(key.secret_key, current_user.id)
            
            # Get exchange name from key
            exchange = db.query(Exchange).filter_by(id=key.exchange_id).first()
            exchange_name = exchange.name if exchange else "binance"
            
            adapter = ExchangeFactory.create(
                exchange_name, decrypted_key, decrypted_secret, testnet=key.is_testnet
            )
            
            # Validate TP > current price (for LONG positions)
            try:
                current_price = adapter.get_symbol_price(order.symbol)
                new_tp = float(order.take_profit)
                new_sl = float(order.stop_loss)
                
                if new_tp <= current_price:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Take Profit ({new_tp}) must be greater than current price ({current_price:.2f})"
                    )
                
                # SL can be above current price for trailing stops or specific strategies
                # No validation needed for SL vs current price
            except HTTPException:
                raise
            except Exception:
                pass  # If price check fails, allow the update
            
            try:
                # Clear tp_order_id BEFORE cancelling to prevent race condition with TP_CHECK
                old_tp_order_id = order.tp_order_id
                order.tp_order_id = None
                db.commit()  # Commit immediately so TP_CHECK doesn't see the cancelled TP
                
                # Pass existing tp_order_id for accurate cancellation
                new_tp_order_id = adapter.update_spot_tp_sl(
                    order.symbol,
                    float(order.quantity),
                    float(order.take_profit),
                    float(order.stop_loss),
                    user_id=current_user.id,
                    old_tp=old_tp,
                    tp_order_id=old_tp_order_id
                )
                # Save new tp_order_id
                if new_tp_order_id:
                    order.tp_order_id = new_tp_order_id
            except Exception as e:
                # Restore tp_order_id if update failed
                order.tp_order_id = old_tp_order_id
                db.commit()
                raise HTTPException(status_code=400, detail=f"Failed to update on exchange: {str(e)}")
    
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
    
    # Broadcast WebSocket update
    from api.websocket_manager import manager
    await manager.broadcast_order_update(current_user.id, order_id, "CANCELLED")
    
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
    
    if order.status not in ["EXECUTED", "PARTIAL_FILLED"]:
        raise HTTPException(status_code=400, detail="Can only close EXECUTED or PARTIAL_FILLED orders")
    
    # Get adapter using order's exchange_id (not hardcoded binance)
    if order.exchange_id:
        exchange = db.query(Exchange).filter_by(id=order.exchange_id).first()
    else:
        exchange = db.query(Exchange).filter_by(name="binance").first()
    
    if not exchange:
        raise HTTPException(status_code=400, detail="Exchange not found")
    
    is_testnet = order.is_testnet if order.is_testnet is not None else (network_mode == "Testnet")
    
    key = db.query(APIKey).filter_by(
        user_id=current_user.id,
        exchange_id=exchange.id,
        is_testnet=is_testnet
    ).first()
    
    if not key:
        raise HTTPException(status_code=400, detail=f"No API key configured for {exchange.name}")
    
    from src.crypto_utils import decrypt_api_key
    from src.exchange_factory import ExchangeFactory
    
    decrypted_key = decrypt_api_key(key.api_key, current_user.id)
    decrypted_secret = decrypt_api_key(key.secret_key, current_user.id)
    
    adapter = ExchangeFactory.create(exchange.name, decrypted_key, decrypted_secret, testnet=is_testnet)
    
    try:
        # Extract base asset correctly
        asset_name = order.symbol
        for quote in ['USDC', 'USDT']:
            if asset_name.endswith(quote):
                asset_name = asset_name[:-len(quote)]
                break
        balance = adapter.get_balance(asset_name)
        
        symbol_info = adapter.get_symbol_info(order.symbol)
        filters = {f['filterType']: f for f in symbol_info['filters']}
        step_size = float(filters['LOT_SIZE']['stepSize'])
        min_qty = float(filters['LOT_SIZE']['minQty'])
        
        if balance < min_qty:
            order.status = "CLOSED_EXTERNALLY"
            order.closed_at = datetime.now(timezone.utc)
            db.commit()
            return {"message": "Balance too low to sell, marked as closed"}
        
        qty_to_close = min(float(order.quantity), balance)
        
        # Cancel TP order first if it exists (to release locked funds)
        if order.tp_order_id:
            try:
                adapter.cancel_order(order.symbol, order.tp_order_id)
            except Exception as cancel_err:
                # TP may already be filled or cancelled, continue anyway
                pass
        
        adapter.close_position_market(order.symbol, qty_to_close)
        
        order.status = "CLOSED_MANUAL"
        order.closed_at = datetime.now(timezone.utc)
        db.commit()
        
        # Send Telegram notification for manual close
        try:
            notify_close(SimpleNamespace(
                symbol=order.symbol,
                quantity=float(order.quantity),
                status="CLOSED_MANUAL",
                user_id=current_user.id,
                is_testnet=order.is_testnet
            ), exchange_name=exchange.name)
        except Exception as notify_err:
            print(f"[WARNING] Telegram notification failed: {notify_err}")
        
        # Broadcast WebSocket update
        from api.websocket_manager import manager
        await manager.broadcast_order_update(current_user.id, order_id, "CLOSED_MANUAL")
        await manager.broadcast_portfolio_update(current_user.id)
        
        return {"message": f"Order {order_id} closed manually"}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to close order: {str(e)}")


# ===== SPLIT ORDER =====

class SplitOrderRequest(BaseModel):
    split_quantity: float  # Quantity for the first part
    tp1: float  # Take profit for first part
    sl1: float  # Stop loss for first part
    tp2: float  # Take profit for second part
    sl2: float  # Stop loss for second part


@router.post("/{order_id}/split")
async def split_order(
    order_id: int,
    split_data: SplitOrderRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Split an executed order into two orders with different TP/SL.
    This is managed only in the app database, no exchange operations.
    The original order becomes the first part, a new order is created for the second part.
    """
    # Find the original order
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == current_user.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status not in ["EXECUTED", "PARTIAL_FILLED"]:
        raise HTTPException(status_code=400, detail="Can only split executed orders")
    
    original_qty = float(order.quantity)
    split_qty = split_data.split_quantity
    
    # Validate split quantity
    if split_qty <= 0 or split_qty >= original_qty:
        raise HTTPException(
            status_code=400, 
            detail=f"Split quantity must be between 0 and {original_qty}"
        )
    
    remaining_qty = original_qty - split_qty
    
    # Validate TP/SL for part 1
    entry_price = float(order.entry_price or order.executed_price or 0)
    if not (split_data.sl1 < entry_price < split_data.tp1):
        raise HTTPException(status_code=400, detail="Part 1: Stop Loss must be < Entry < Take Profit")
    if not (split_data.sl2 < entry_price < split_data.tp2):
        raise HTTPException(status_code=400, detail="Part 2: Stop Loss must be < Entry < Take Profit")
    
    # Update original order (becomes part 1)
    order.quantity = Decimal(str(split_qty))
    order.take_profit = Decimal(str(split_data.tp1))
    order.stop_loss = Decimal(str(split_data.sl1))
    
    # Create new order for part 2
    new_order = Order(
        user_id=current_user.id,
        exchange_id=order.exchange_id,
        symbol=order.symbol,
        side=order.side,
        quantity=Decimal(str(remaining_qty)),
        status=order.status,
        entry_price=order.entry_price,
        max_entry=order.max_entry,
        take_profit=Decimal(str(split_data.tp2)),
        stop_loss=Decimal(str(split_data.sl2)),
        entry_interval=order.entry_interval,
        stop_interval=order.stop_interval,
        executed_price=order.executed_price,
        executed_at=order.executed_at,
        created_at=datetime.now(timezone.utc),
        is_testnet=order.is_testnet
    )
    
    db.add(new_order)
    
    # Update TP orders on exchange (cancel old, create 2 new)
    try:
        from src.crypto_utils import decrypt_api_key
        from src.exchange_factory import ExchangeFactory
        
        # Get API key for this order's exchange
        if order.exchange_id:
            exchange = db.query(Exchange).filter_by(id=order.exchange_id).first()
            key = db.query(APIKey).filter_by(
                user_id=current_user.id,
                exchange_id=order.exchange_id,
                is_testnet=order.is_testnet
            ).first()
        else:
            exchange = db.query(Exchange).filter_by(name="binance").first()
            key = db.query(APIKey).filter_by(
                user_id=current_user.id,
                exchange_id=exchange.id if exchange else None,
                is_testnet=order.is_testnet
            ).first()
        
        if key and exchange:
            decrypted_key = decrypt_api_key(key.api_key, current_user.id)
            decrypted_secret = decrypt_api_key(key.secret_key, current_user.id)
            
            adapter = ExchangeFactory.create(
                exchange.name, decrypted_key, decrypted_secret, testnet=key.is_testnet
            )
            
            # Get symbol info for quantity formatting and validation FIRST
            # IMPORTANT: Validate BEFORE cancelling TP to avoid orphaned positions
            symbol_info = adapter.get_symbol_info(order.symbol)
            filters = {f['filterType']: f for f in symbol_info['filters']}
            step_size = float(filters['LOT_SIZE']['stepSize'])
            tick_size = float(filters['PRICE_FILTER']['tickSize'])
            min_notional = float(filters.get('NOTIONAL', {}).get('minNotional', '5'))
            min_qty = float(filters['LOT_SIZE'].get('minQty', '0.00001'))
            
            # Validate minimum order value for both parts BEFORE any exchange operations
            value1 = split_qty * float(split_data.tp1)
            value2 = remaining_qty * float(split_data.tp2)
            
            if value1 < min_notional:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Part 1 order value (${value1:.2f}) is below minimum (${min_notional}). Increase split quantity or TP price."
                )
            if value2 < min_notional:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Part 2 order value (${value2:.2f}) is below minimum (${min_notional}). Decrease split quantity or increase TP price."
                )
            if split_qty < min_qty:
                raise HTTPException(status_code=400, detail=f"Part 1 quantity {split_qty} is below minimum {min_qty}")
            if remaining_qty < min_qty:
                raise HTTPException(status_code=400, detail=f"Part 2 quantity {remaining_qty} is below minimum {min_qty}")
            
            # NOW cancel the old TP order (only after validation passes)
            # We must cancel first to release liquidity, but will recreate if new TPs fail
            old_tp_order_id = order.tp_order_id
            
            # Use centralized formatting from trading_utils
            def format_qty(qty):
                return format_quantity(float(qty), step_size)
            
            def format_price_local(price):
                return trading_format_price(float(price), tick_size)

            
            import logging
            logger = logging.getLogger('orders')
            
            # Calculate old values for potential rollback
            old_tp_price = format_price_local(order.take_profit) if order.take_profit else None
            old_qty = format_qty(float(order.quantity))
            
            # Cancel old TP first to release liquidity
            if old_tp_order_id:
                order.tp_order_id = None
                db.commit()
                
                try:
                    adapter.client.cancel_order(
                        symbol=order.symbol,
                        orderId=int(old_tp_order_id)
                    )
                    logger.info(f"[SPLIT] Cancelled old TP order {old_tp_order_id}")
                except Exception as e:
                    logger.warning(f"[SPLIT] Could not cancel old TP order {old_tp_order_id}: {e}")
            
            # Helper to recreate old TP if split fails
            def recreate_old_tp():
                if old_tp_price and old_qty:
                    try:
                        resp = adapter.client.create_order(
                            symbol=order.symbol,
                            side='SELL',
                            type='LIMIT',
                            timeInForce='GTC',
                            quantity=old_qty,
                            price=old_tp_price
                        )
                        order.tp_order_id = str(resp.get('orderId'))
                        db.commit()
                        logger.info(f"[SPLIT] Recreated old TP: {order.tp_order_id}")
                    except Exception as e:
                        logger.error(f"[SPLIT] CRITICAL: Could not recreate old TP: {e}")
            
            # Create TP order for part 1
            qty1_str = format_qty(split_qty)
            price1_str = format_price_local(split_data.tp1)
            logger.info(f"[SPLIT] Creating TP1: {qty1_str} @ {price1_str}")
            
            try:
                resp1 = adapter.client.create_order(
                    symbol=order.symbol,
                    side='SELL',
                    type='LIMIT',
                    timeInForce='GTC',
                    quantity=qty1_str,
                    price=price1_str
                )
                logger.info(f"[SPLIT] TP1 created: orderId={resp1.get('orderId')}")
            except Exception as e1:
                logger.error(f"[SPLIT] Failed to create TP1: {e1}")
                # Recreate old TP to restore original state
                recreate_old_tp()
                raise
            
            # Create TP order for part 2
            qty2_str = format_qty(remaining_qty)
            price2_str = format_price_local(split_data.tp2)
            logger.info(f"[SPLIT] Creating TP2: {qty2_str} @ {price2_str}")
            
            try:
                resp2 = adapter.client.create_order(
                    symbol=order.symbol,
                    side='SELL',
                    type='LIMIT',
                    timeInForce='GTC',
                    quantity=qty2_str,
                    price=price2_str
                )
                logger.info(f"[SPLIT] TP2 created: orderId={resp2.get('orderId')}")
            except Exception as e2:
                logger.error(f"[SPLIT] Failed to create TP2: {e2}")
                # Cancel TP1 and recreate old TP
                try:
                    adapter.client.cancel_order(symbol=order.symbol, orderId=resp1.get('orderId'))
                    logger.info(f"[SPLIT] Cancelled TP1 due to TP2 failure")
                except:
                    pass
                recreate_old_tp()
                raise
            
            # BOTH TPs created successfully - save new IDs
            order.tp_order_id = str(resp1.get('orderId'))
            new_order.tp_order_id = str(resp2.get('orderId'))
            
    except Exception as e:
        # Rollback DB changes if exchange update fails
        db.rollback()
        error_str = str(e)
        # Provide user-friendly error for common issues
        if "NOTIONAL" in error_str or "-1013" in error_str:
            raise HTTPException(
                status_code=400, 
                detail="Order value too small. Each split must be worth at least $5 (Binance minimum). Try splitting into fewer parts."
            )
        raise HTTPException(status_code=400, detail=f"Failed to update TP orders on exchange: {error_str}")
    
    db.commit()
    db.refresh(order)
    db.refresh(new_order)
    
    # Broadcast WebSocket updates
    from api.websocket_manager import manager
    await manager.broadcast_order_update(current_user.id, order_id, order.status)
    await manager.broadcast_order_update(current_user.id, new_order.id, new_order.status)
    await manager.broadcast_portfolio_update(current_user.id)
    
    return {
        "message": "Order split successfully - TP orders updated on exchange",
        "part1": {
            "id": order.id,
            "quantity": float(order.quantity),
            "take_profit": float(order.take_profit),
            "stop_loss": float(order.stop_loss)
        },
        "part2": {
            "id": new_order.id,
            "quantity": float(new_order.quantity),
            "take_profit": float(new_order.take_profit),
            "stop_loss": float(new_order.stop_loss)
        }
    }

