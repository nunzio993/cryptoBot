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
    """
    order_id = event.get('order_id')
    status = event.get('status')
    side = event.get('side')
    user_id = event.get('user_id')
    exchange = event.get('exchange')
    symbol = event.get('symbol')
    
    logger.info(f"[EVENT] {exchange} {symbol} order #{order_id} -> {status}")
    
    # Only process SELL orders (our TP orders)
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
