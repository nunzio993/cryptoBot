"""
Order event handlers for WebSocket events.
Processes order updates from Binance/Bybit WebSocket streams.
"""

import logging
from datetime import datetime, timezone
from typing import Dict
from models import Order, SessionLocal

logger = logging.getLogger('order_events')


async def handle_order_update(event: Dict):
    """
    Handle order update events from WebSocket streams.
    
    Events:
    - FILLED: TP hit, mark order as closed
    - CANCELED: TP cancelled externally, mark order accordingly
    - PARTIALLY_FILLED: Update quantity and resize TP order
    """
    order_id = event.get('order_id')
    status = event.get('status')
    side = event.get('side')
    user_id = event.get('user_id')
    exchange = event.get('exchange')
    symbol = event.get('symbol')
    
    logger.info(f"[EVENT] {exchange} {symbol} order #{order_id} -> {status}")
    
    # Handle BUY orders for partial fill (our entry orders)
    if side == 'BUY' and status == 'PARTIALLY_FILLED':
        await handle_entry_partial_fill(event)
        return
    
    # Only process SELL orders (our TP orders) for FILLED/CANCELED
    if side != 'SELL':
        return
    
    with SessionLocal() as session:
        # Find the order by tp_order_id
        db_order = session.query(Order).filter(
            Order.tp_order_id == str(order_id),
            Order.user_id == user_id
        ).first()
        
        if not db_order:
            logger.debug(f"[EVENT] No matching order found for TP {order_id}")
            return
        
        if status == 'FILLED':
            await handle_tp_filled(db_order, event, session)
        elif status == 'CANCELED':
            await handle_tp_cancelled(db_order, event, session)
        elif status == 'PARTIALLY_FILLED':
            # TP partially filled - update remaining quantity
            await handle_tp_partial_fill(db_order, event, session)


async def handle_tp_filled(order: Order, event: Dict, session):
    """Handle TP order filled - position closed at target price."""
    logger.info(f"[TP_FILLED] Order {order.id} ({order.symbol}): TP hit at {event.get('price')}")
    
    order.status = 'CLOSED_TP'
    order.closed_at = datetime.now(timezone.utc)
    order.tp_order_id = None
    session.commit()
    
    # Send Telegram notification
    try:
        from src.telegram_notifications import notify_tp_hit
        exchange_name = event.get('exchange', 'unknown')
        notify_tp_hit(order, exchange_name=exchange_name)
    except Exception as e:
        logger.warning(f"[TP_FILLED] Failed to send notification: {e}")
    
    # Broadcast WebSocket update to frontend
    try:
        from api.websocket_manager import manager
        import asyncio
        await manager.broadcast_order_update(order.user_id, order.id, 'CLOSED_TP')
        await manager.broadcast_portfolio_update(order.user_id)
    except Exception as e:
        logger.warning(f"[TP_FILLED] Failed to broadcast update: {e}")


async def handle_tp_cancelled(order: Order, event: Dict, session):
    """Handle TP order cancelled - either externally or by user."""
    logger.warning(f"[TP_CANCELLED] Order {order.id} ({order.symbol}): TP {order.tp_order_id} cancelled")
    
    # CRITICAL: Re-fetch the order to get the latest state
    # This prevents race condition where split/update already cleared tp_order_id
    session.refresh(order)
    
    # If tp_order_id is already None, it means split/update already handled this
    if not order.tp_order_id:
        logger.info(f"[TP_CANCELLED] Order {order.id}: tp_order_id already cleared, skipping")
        return
    
    # Check if the cancelled order ID matches what we expect
    if str(order.tp_order_id) != str(event.get('order_id')):
        logger.info(f"[TP_CANCELLED] Order {order.id}: TP ID mismatch, skipping (got {event.get('order_id')}, expected {order.tp_order_id})")
        return
    
    # Skip if API is currently updating this order (updating flag is set)
    if getattr(order, 'updating', False):
        logger.info(f"[TP_CANCELLED] Order {order.id}: Skipping (API is updating)")
        return
    
    order.status = 'CLOSED_EXTERNALLY'
    order.closed_at = datetime.now(timezone.utc)
    order.tp_order_id = None
    session.commit()
    
    # Send Telegram notification
    try:
        from src.telegram_notifications import notify_tp_cancelled
        exchange_name = event.get('exchange', 'unknown')
        notify_tp_cancelled(order, exchange_name=exchange_name)
    except Exception as e:
        logger.warning(f"[TP_CANCELLED] Failed to send notification: {e}")
    
    # Broadcast WebSocket update to frontend
    try:
        from api.websocket_manager import manager
        await manager.broadcast_order_update(order.user_id, order.id, 'CLOSED_EXTERNALLY')
        await manager.broadcast_portfolio_update(order.user_id)
    except Exception as e:
        logger.warning(f"[TP_CANCELLED] Failed to broadcast update: {e}")


async def handle_entry_partial_fill(event: Dict):
    """
    Handle partial fill of a BUY (entry) order.
    Updates the order quantity and resizes the TP order on exchange.
    """
    user_id = event.get('user_id')
    symbol = event.get('symbol')
    filled_qty = float(event.get('filled_quantity', 0))
    exchange_name = event.get('exchange', 'binance')
    exchange_id = event.get('exchange_id')
    testnet = event.get('testnet', False)
    
    if filled_qty <= 0:
        logger.warning(f"[PARTIAL_FILL] Invalid filled_quantity: {filled_qty}")
        return
    
    logger.info(f"[PARTIAL_FILL] Entry order partial fill: {symbol} filled_qty={filled_qty}")
    
    with SessionLocal() as session:
        # Find EXECUTED order for this symbol that might need TP resize
        # Match by user_id, symbol, exchange_id, and status
        db_order = session.query(Order).filter(
            Order.user_id == user_id,
            Order.symbol == symbol,
            Order.exchange_id == exchange_id,
            Order.is_testnet == testnet,
            Order.status.in_(['EXECUTED', 'PARTIAL_FILLED'])
        ).first()
        
        if not db_order:
            logger.debug(f"[PARTIAL_FILL] No matching executed order for {symbol}")
            return
        
        old_qty = float(db_order.quantity) if db_order.quantity else 0
        
        # Only update if filled quantity is different
        if abs(filled_qty - old_qty) < 0.00001:
            logger.debug(f"[PARTIAL_FILL] Quantity unchanged, skipping")
            return
        
        logger.info(f"[PARTIAL_FILL] Order {db_order.id}: qty {old_qty} -> {filled_qty}")
        
        # Update order quantity and status
        from decimal import Decimal
        db_order.quantity = Decimal(str(filled_qty))
        db_order.status = 'PARTIAL_FILLED'
        
        # If there's a TP order, resize it on exchange
        if db_order.tp_order_id and db_order.take_profit:
            try:
                await _resize_tp_order(db_order, filled_qty, exchange_name, testnet, session)
            except Exception as e:
                logger.error(f"[PARTIAL_FILL] Failed to resize TP: {e}")
                # Continue anyway - order quantity is updated
        
        session.commit()
        
        # Broadcast update to frontend
        try:
            from api.websocket_manager import manager
            await manager.broadcast_order_update(user_id, db_order.id, 'PARTIAL_FILLED')
            await manager.broadcast_portfolio_update(user_id)
        except Exception as e:
            logger.warning(f"[PARTIAL_FILL] Failed to broadcast: {e}")


async def handle_tp_partial_fill(order: Order, event: Dict, session):
    """
    Handle partial fill of a TP (SELL) order.
    Updates the remaining quantity in the order.
    """
    filled_qty = float(event.get('filled_quantity', 0))
    original_qty = float(order.quantity) if order.quantity else 0
    remaining_qty = original_qty - filled_qty
    
    logger.info(f"[TP_PARTIAL] Order {order.id}: TP partial fill, sold {filled_qty}, remaining {remaining_qty}")
    
    if remaining_qty <= 0:
        # Fully filled, treat as complete
        logger.info(f"[TP_PARTIAL] Order {order.id}: Considered fully filled")
        await handle_tp_filled(order, event, session)
        return
    
    # Update order with remaining quantity
    from decimal import Decimal
    order.quantity = Decimal(str(remaining_qty))
    session.commit()
    
    # Broadcast update
    try:
        from api.websocket_manager import manager
        await manager.broadcast_order_update(order.user_id, order.id, order.status)
        await manager.broadcast_portfolio_update(order.user_id)
    except Exception as e:
        logger.warning(f"[TP_PARTIAL] Failed to broadcast: {e}")


async def _resize_tp_order(order: Order, new_qty: float, exchange_name: str, testnet: bool, session):
    """
    Cancel existing TP and create new TP with updated quantity.
    """
    from src.core_and_scheduler import get_exchange_adapter
    
    logger.info(f"[RESIZE_TP] Order {order.id}: Resizing TP from exchange")
    
    try:
        adapter = get_exchange_adapter(order.user_id, exchange_name, testnet)
    except Exception as e:
        logger.error(f"[RESIZE_TP] Failed to get adapter: {e}")
        raise
    
    # Get symbol info for formatting
    symbol_info = adapter.get_symbol_info(order.symbol)
    filters = {f['filterType']: f for f in symbol_info['filters']}
    step_size = float(filters['LOT_SIZE']['stepSize'])
    tick_size = float(filters['PRICE_FILTER']['tickSize'])
    min_qty = float(filters['LOT_SIZE'].get('minQty', '0.00001'))
    min_notional = float(filters.get('NOTIONAL', {}).get('minNotional', '5'))
    
    # Check if new quantity is viable
    tp_price = float(order.take_profit)
    order_value = new_qty * tp_price
    
    if new_qty < min_qty:
        logger.warning(f"[RESIZE_TP] Order {order.id}: New qty {new_qty} below min {min_qty}, clearing TP")
        order.tp_order_id = None
        return
    
    if order_value < min_notional:
        logger.warning(f"[RESIZE_TP] Order {order.id}: Order value ${order_value:.2f} below min ${min_notional}, clearing TP")
        order.tp_order_id = None
        return
    
    # Cancel old TP
    old_tp_id = order.tp_order_id
    try:
        adapter.cancel_order(symbol=order.symbol, order_id=old_tp_id)
        logger.info(f"[RESIZE_TP] Cancelled old TP {old_tp_id}")
    except Exception as e:
        logger.warning(f"[RESIZE_TP] Could not cancel old TP {old_tp_id}: {e}")
    
    # Clear TP ID immediately to prevent race condition
    order.tp_order_id = None
    session.commit()
    
    # Format quantity and price
    from decimal import Decimal, ROUND_DOWN
    qty_dec = Decimal(str(new_qty)).quantize(Decimal(str(step_size)), rounding=ROUND_DOWN)
    price_dec = Decimal(str(tp_price)).quantize(Decimal(str(tick_size)), rounding=ROUND_DOWN)
    qty_str = str(qty_dec).rstrip('0').rstrip('.')
    price_str = str(price_dec).rstrip('0').rstrip('.')
    
    # Create new TP using place_order (works on both Binance and Bybit)
    try:
        resp = adapter.place_order(
            symbol=order.symbol,
            side='SELL',
            type_='LIMIT',
            quantity=float(qty_str),
            price=float(price_str)
        )
        new_tp_id = str(resp.get('orderId'))
        order.tp_order_id = new_tp_id
        logger.info(f"[RESIZE_TP] Created new TP {new_tp_id} for qty={qty_str} @ {price_str}")
    except Exception as e:
        logger.error(f"[RESIZE_TP] Failed to create new TP: {e}")
        raise

