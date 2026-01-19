import sys
from src.binance_utils import has_sufficient_balance
from binance.client import Client
from binance.exceptions import BinanceAPIException
import os
from src.adapters import BinanceAdapter
from src.trading_utils import round_to_step, format_quantity, format_price

import logging
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.telegram_notifications import notify_open, notify_close, notify_tp_hit, notify_sl_hit
from src.user_logger import log_event
from models import Order, init_db, SessionLocal, APIKey, Exchange
from sqlalchemy import and_

init_db()
    # ... codice ...
# qui la sessione si chiude sempre, anche in caso di errore
with SessionLocal() as session:
    INTERVAL_MAP = {
        'M5':    '5m',
        'H1':    '1h',
        'H4':    '4h',
        'Daily': '1d',
    }
    
    # Durata in secondi per ogni intervallo
    INTERVAL_SECONDS = {
        'M5':    5 * 60,
        'H1':    60 * 60,
        'H4':    4 * 60 * 60,
        'Daily': 24 * 60 * 60,
    }

tlogger = logging.getLogger('core')
tlogger.setLevel(logging.INFO)

def get_candle_close_time(candle_open_ts: datetime, interval: str) -> datetime:
    """Calcola il timestamp di CHIUSURA della candela"""
    from datetime import timedelta
    seconds = INTERVAL_SECONDS.get(interval, 5 * 60)
    return candle_open_ts + timedelta(seconds=seconds)

def fetch_last_closed_candle(symbol: str, interval: str, client: Client):
    api_interval = INTERVAL_MAP.get(interval, interval)
    klines = client.get_klines(symbol=symbol, interval=api_interval, limit=2)
    return klines[-2]

def get_exchange_adapter(user_id: int, exchange_name: str = "binance", is_testnet: bool = False):
    """
    Get exchange adapter using ExchangeFactory.
    Supports multiple exchanges based on order configuration.
    """
    from src.exchange_factory import ExchangeFactory
    
    with SessionLocal() as session:    
        exchange = session.query(Exchange).filter_by(name=exchange_name.lower()).first()
        if not exchange:
            raise Exception(f"Exchange '{exchange_name}' not found")
        
        api_key_obj = session.query(APIKey).filter_by(
            user_id=user_id, 
            exchange_id=exchange.id, 
            is_testnet=is_testnet
        ).first()

        if not api_key_obj:
            network_name = "Testnet" if is_testnet else "Mainnet"
            raise Exception(f"No {network_name} API key found for user {user_id} on {exchange_name}")

        # Decrypt API keys before use
        from src.crypto_utils import decrypt_api_key
        decrypted_key = decrypt_api_key(api_key_obj.api_key, user_id)
        decrypted_secret = decrypt_api_key(api_key_obj.secret_key, user_id)

        return ExchangeFactory.create(
            exchange_name=exchange_name,
            api_key=decrypted_key,
            api_secret=decrypted_secret,
            testnet=is_testnet
        )


def get_order_exchange_name(order, session) -> str:
    """Get exchange name for an order, defaults to 'binance' for old orders"""
    if order.exchange_id:
        exchange = session.query(Exchange).filter_by(id=order.exchange_id).first()
        return exchange.name if exchange else "binance"
    return "binance"



def auto_execute_pending():
    with SessionLocal() as session:
        pendings = session.query(Order).filter(Order.status == 'PENDING').all()
        tlogger.info(f"[DEBUG] auto_execute: {len(pendings)} PENDING orders")

        for order in pendings:
            # Get order configuration
            is_testnet = getattr(order, 'is_testnet', False) or False
            exchange_name = get_order_exchange_name(order, session)
            network_name = "Testnet" if is_testnet else "Mainnet"
            
            try:
                adapter = get_exchange_adapter(order.user_id, exchange_name, is_testnet)
                client = adapter.client  # For Binance compatibility
            except Exception as e:
                tlogger.error(f"[ERROR] Cannot get {exchange_name} {network_name} API for user {order.user_id}: {e}")
                continue

            quote_asset = order.symbol[-4:]
            required = float(order.entry_price) * float(order.quantity)

            # Check balance using adapter
            try:
                balance = adapter.get_balance(quote_asset)
                if balance < required:
                    tlogger.error(f"[ERROR] Saldo insufficiente per order {order.id}: richiesti {required:.2f} {quote_asset}")
                    continue
            except Exception as e:
                tlogger.error(f"[ERROR] Cannot check balance for order {order.id}: {e}")
                continue

            created_dt = order.created_at
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)

            candle = fetch_last_closed_candle(order.symbol, order.entry_interval, adapter.client)
            ts_candle = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)
            candle_close_time = get_candle_close_time(ts_candle, order.entry_interval)
            last_close = float(candle[4])

            tlogger.info(f"[DEBUG] order={order.id} | created={created_dt} | candle_open={ts_candle} | candle_close={candle_close_time} | entry={order.entry_price} | last_close={last_close}")

            if (
                order.entry_price <= last_close <= order.max_entry and
                candle_close_time >= created_dt and             # candela che CHIUDE dopo/durante la creazione
                (not order.executed_at)                         # esegui solo se mai eseguito
            ):
                exchange = session.query(Exchange).filter_by(name=exchange_name).first()
                api_key_obj = session.query(APIKey).filter_by(
                    user_id=order.user_id,
                    exchange_id=exchange.id,
                    is_testnet=is_testnet  # Use order's testnet setting
                ).first()

                if not api_key_obj:
                    tlogger.warning(f"[WARNING] Nessuna APIKey {network_name} trovata per user {order.user_id} su {exchange_name}")
                    continue

                # Decrypt API keys
                from src.crypto_utils import decrypt_api_key
                decrypted_key = decrypt_api_key(api_key_obj.api_key, order.user_id)
                decrypted_secret = decrypt_api_key(api_key_obj.secret_key, order.user_id)

                # Use ExchangeFactory to create the correct adapter for this exchange
                from src.exchange_factory import ExchangeFactory
                adapter = ExchangeFactory.create(
                    exchange_name=exchange_name,
                    api_key=decrypted_key,
                    api_secret=decrypted_secret,
                    testnet=is_testnet
                )

                try:
                    symbol_info = adapter.get_symbol_info(order.symbol)
                    filters = {f['filterType']: f for f in symbol_info['filters']}
                    step_size = float(filters['LOT_SIZE']['stepSize'])
                    tick_size = float(filters['PRICE_FILTER']['tickSize'])
                    min_notional = float(filters['MIN_NOTIONAL']['minNotional']) if 'MIN_NOTIONAL' in filters else 0

                    qty = round_to_step(float(order.quantity), float(step_size))
                    notional = qty * last_close
                    if notional < min_notional:
                        tlogger.error(f"[ERROR] Notional too low for Binance rules on order {order.id}: {notional:.2f}")
                        continue

                    qty_str = ('{:.8f}'.format(float(qty))).rstrip('0').rstrip('.')

                    # BUY MARKET
                    resp = adapter.client.create_order(
                        symbol=order.symbol,
                        side='BUY',
                        type='MARKET',
                        quantity=qty_str
                    )

                    executed_qty = sum(float(fill['qty']) for fill in resp['fills'])
                    exec_price = sum(float(fill['price']) * float(fill['qty']) for fill in resp['fills']) / executed_qty if executed_qty > 0 else 0
                    exec_time = datetime.now(timezone.utc)
                    
                    # Check for partial fill
                    original_qty = float(qty)
                    is_partial = executed_qty < original_qty * 0.99  # Allow 1% tolerance
                    
                    # Format executed quantity for TP order
                    executed_qty_str = ('{:.8f}'.format(float(executed_qty))).rstrip('0').rstrip('.')
                    
                    # Format TP price properly to avoid scientific notation
                    from decimal import Decimal, ROUND_DOWN
                    tp_price_dec = Decimal(str(order.take_profit)).quantize(Decimal(str(tick_size)), rounding=ROUND_DOWN)
                    tp_price_str = str(tp_price_dec).rstrip('0').rstrip('.')

                    # TP LIMIT - use actual executed quantity
                    tp_response = adapter.client.create_order(
                        symbol=order.symbol,
                        side='SELL',
                        type='LIMIT',
                        timeInForce='GTC',
                        quantity=executed_qty_str,
                        price=tp_price_str
                    )

                    order.status = 'PARTIAL_FILLED' if is_partial else 'EXECUTED'
                    order.executed_at = exec_time
                    order.executed_price = exec_price
                    order.quantity = executed_qty  # Update with actual executed quantity
                    order.tp_order_id = str(tp_response.get('orderId'))  # Save Binance TP order ID
                    order.sl_updated_at = exec_time  # Set for WebSocket handler grace period
                    session.commit()

                    tlogger.info(f"[{'PARTIAL_FILLED' if is_partial else 'EXECUTED'}] order {order.id} @ {exec_price}, qty={executed_qty}/{original_qty}, TP placed")
                    
                    # User log
                    log_event(order.user_id, "ORDER_EXECUTED", 
                              id=order.id, symbol=order.symbol, 
                              price=exec_price, qty=executed_qty)

                    notify_open(SimpleNamespace(
                        symbol=order.symbol,
                        quantity=order.quantity,
                        entry_price=exec_price,
                        user_id=order.user_id,
                        is_testnet=is_testnet
                    ), exchange_name=exchange_name)
                except BinanceAPIException as e:
                    tlogger.error(f"[ERROR] Binance API exec {order.id}: {e}")
                    continue
                except Exception as e:
                    tlogger.error(f"[ERROR] Unexpected exec {order.id}: {e}")
                    continue
            else:
                tlogger.info(f"[DEBUG] order {order.id} NOT triggered")

# NOTE: Removed orphan close_position_market function that was defined at module level
# but used 'self' parameter. It was dead code - use adapter.close_position_market() instead.

def check_and_execute_stop_loss():
    with SessionLocal() as session:
        # Include both EXECUTED and PARTIAL_FILLED orders
        open_orders = session.query(Order).filter(Order.status.in_(['EXECUTED', 'PARTIAL_FILLED'])).all()
        for order in open_orders:
            # Get order configuration
            is_testnet = getattr(order, 'is_testnet', False) or False
            exchange_name = get_order_exchange_name(order, session)
            network_name = "Testnet" if is_testnet else "Mainnet"
            
            try:
                adapter = get_exchange_adapter(order.user_id, exchange_name, is_testnet)
                client = adapter.client
            except Exception as e:
                tlogger.error(f"[ERROR] {exchange_name} {network_name} API per SL user {order.user_id}: {e}")
                continue

            # Considera la candela daily/interval di stop, non di entry
            interval = order.stop_interval if order.stop_interval else order.entry_interval
            candle = fetch_last_closed_candle(order.symbol, interval, client)
            last_close = float(candle[4])
            ts_candle = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)
            candle_close_time = get_candle_close_time(ts_candle, interval)

            # Check: chiusura candela <= stop_loss e candela che TERMINA dopo esecuzione/modifica
            # Use sl_updated_at if SL was modified, otherwise use executed_at
            # Strict > ensures we wait for a candle that CLOSES after modification
            reference_time = order.sl_updated_at if order.sl_updated_at else order.executed_at
            
            # Grace period: skip SL check if order was modified in the last 60 seconds
            # This prevents race condition where scheduler reads before API commits
            now = datetime.now(timezone.utc)
            if order.sl_updated_at and (now - order.sl_updated_at).total_seconds() < 60:
                tlogger.info(f"[SL_GRACE] Order {order.id} modified {(now - order.sl_updated_at).total_seconds():.1f}s ago, skipping (60s grace period)")
                continue
            
            if (
                order.stop_loss is not None and
                last_close <= float(order.stop_loss) and
                candle_close_time > reference_time  # Candle must CLOSE strictly after reference time
            ):
                # NOTE: We reuse the 'adapter' created above (line 261) which already has
                # decrypted API keys and correct testnet setting from get_exchange_adapter()
                
                try:
                    base_asset = order.symbol.replace("USDC", "").replace("USDT", "")
                    balance_info = adapter.get_asset_balance(base_asset)
                    # Use TOTAL balance (free + locked), not just free
                    # BNB might be locked in pending TP orders
                    free_bal = float(balance_info.get('free', 0))
                    locked_bal = float(balance_info.get('locked', 0))
                    balance = free_bal + locked_bal
                    symbol_info = adapter.get_symbol_info(order.symbol)
                    filters = {f['filterType']: f for f in symbol_info['filters']}
                    step_size = float(filters['LOT_SIZE']['stepSize'])

                    # Se saldo troppo basso, marca come chiuso esternamente e non mandare ordine
                    if balance < step_size:
                        tlogger.warning(f"[SKIP CLOSE] order {order.id}: saldo {base_asset} troppo basso ({balance})")
                        order.status = 'CLOSED_EXTERNALLY'
                        # Keep original quantity for reference, don't zero it
                        order.closed_at = datetime.now(timezone.utc)
                        session.commit()
                        continue

                    original_qty = float(order.quantity)
                    qty_to_close = min(original_qty, balance)
                    
                    # Cancel TP order first if it exists (BNB is locked in TP)
                    if order.tp_order_id:
                        try:
                            tlogger.info(f"[SL] Cancelling TP order {order.tp_order_id} before SL execution for order {order.id}")
                            adapter.cancel_order(order.symbol, order.tp_order_id)
                            order.tp_order_id = None
                            session.commit()
                        except Exception as cancel_err:
                            tlogger.error(f"[SL] Failed to cancel TP {order.tp_order_id}: {cancel_err}")
                    
                    # Execute SL using the correctly initialized adapter
                    adapter.close_position_market(order.symbol, qty_to_close)
                    
                    # Update order with actual closed quantity
                    order.quantity = qty_to_close  # Update to reflect what was actually sold
                    order.status = 'CLOSED_SL'
                    order.closed_at = datetime.now(timezone.utc)
                    session.commit()
                    
                    tlogger.info(f"[STOP LOSS] order {order.id} chiuso SL, qty={qty_to_close}/{original_qty}")
                    log_event(order.user_id, "ORDER_CLOSED_SL", 
                              id=order.id, symbol=order.symbol, price=last_close)
                    notify_sl_hit(order, exit_price=last_close, exchange_name=exchange_name)
                except Exception as e:
                    tlogger.error(f"[ERROR] SL {order.id}: {e}")

def check_tp_fills():
    """Check if TP orders have been filled and update order status accordingly"""
    with SessionLocal() as session:
        executed_orders = session.query(Order).filter(Order.status.in_(['EXECUTED', 'PARTIAL_FILLED'])).all()
        
        for order in executed_orders:
            is_testnet = getattr(order, 'is_testnet', False) or False
            exchange_name = get_order_exchange_name(order, session)
            
            try:
                adapter = get_exchange_adapter(order.user_id, exchange_name, is_testnet)
                
                # Check if there are any open SELL orders for this symbol
                open_orders = adapter.get_open_orders(symbol=order.symbol)
                has_tp_order = any(o['side'] == 'SELL' for o in open_orders)
                
                if not has_tp_order:
                    # No TP order exists - check if balance shows position was sold
                    base_asset = order.symbol.replace("USDC", "").replace("USDT", "")
                    bal = adapter.get_asset_balance_detail(base_asset)
                    total_balance = bal['free'] + bal['locked']
                    order_qty = float(order.quantity) if order.quantity else 0
                    
                    # If balance is significantly lower than order qty and no TP order exists,
                    # the TP might have been filled
                    if total_balance < order_qty * 0.5:  # Threshold: if less than 50% remains
                        # Check recent trades to confirm TP fill
                        try:
                            trades = adapter.get_recent_trades(symbol=order.symbol, limit=5)
                            for trade in trades:
                                if not trade.get('isBuyer', True):  # SELL trade
                                    trade_qty = float(trade.get('qty', 0))
                                    trade_price = float(trade.get('price', 0))
                                    tp_price = float(order.take_profit) if order.take_profit else 0
                                    
                                    # If trade price is near TP and quantity matches
                                    if tp_price > 0 and trade_qty >= order_qty * 0.9 and abs(trade_price - tp_price) / tp_price < 0.02:
                                        order.status = 'CLOSED_TP'
                                        order.closed_at = datetime.now(timezone.utc)
                                        session.commit()
                                        tlogger.info(f"[TP CHECK] order {order.id} TP fillato @ {trade_price}")
                                        log_event(order.user_id, "ORDER_CLOSED_TP", 
                                                  id=order.id, symbol=order.symbol, price=trade_price)
                                        notify_tp_hit(order, exit_price=trade_price, exchange_name=exchange_name)
                                        break
                        except:
                            pass
                            
            except Exception as e:
                tlogger.error(f"[ERROR] TP check {order.id}: {e}")
                    
                    
def sync_orders():
    """Sync executed orders with exchanges - mark externally closed orders and handle partial sells"""
    with SessionLocal() as session:
        executed_orders = session.query(Order).filter(Order.status.in_(['EXECUTED', 'PARTIAL_FILLED'])).all()
        for order in executed_orders:
            # Get order configuration
            is_testnet = getattr(order, 'is_testnet', False) or False
            exchange_name = get_order_exchange_name(order, session)
            
            try:
                adapter = get_exchange_adapter(order.user_id, exchange_name, is_testnet)
                
                # Skip sync for orders with active TP - they're being managed
                if order.tp_order_id:
                    tlogger.debug(f"[SYNC] Order {order.id} has active TP, skipping sync check")
                    continue
                
                base_asset = order.symbol.replace("USDC", "").replace("USDT", "")
                
                # Get TOTAL balance (free + locked) - for Bybit, assets might be locked in TP orders
                balance_info = adapter.get_asset_balance(base_asset)
                free_bal = float(balance_info.get('free', 0))
                locked_bal = float(balance_info.get('locked', 0))
                balance = free_bal + locked_bal
                order_qty = float(order.quantity) if order.quantity else 0
                
                network_name = "Testnet" if is_testnet else "Mainnet"
                tlogger.info(f"[SYNC DEBUG] order {order.id} | {exchange_name} {network_name} | asset={base_asset} | balance={balance} (free={free_bal}, locked={locked_bal}) | order_qty={order_qty}")
                
                # Get minimum quantity for the symbol
                min_qty = 0.0
                try:
                    if hasattr(adapter, 'client'):
                        symbol_info = adapter.get_symbol_info(order.symbol)
                        if symbol_info:
                            filters = {f['filterType']: f for f in symbol_info['filters']}
                            min_qty = float(filters['LOT_SIZE']['minQty'])
                except:
                    pass  # Use default 0
                
                # Only close if balance is truly 0 AND order was executed some time ago (not just now)
                order_age_minutes = 0
                if order.executed_at:
                    order_age_minutes = (datetime.now(timezone.utc) - order.executed_at).total_seconds() / 60
                
                if (balance == 0 or (balance > 0 and balance < min_qty)) and order_age_minutes > 5:
                    # Fully closed externally or below minimum (only if order is older than 5 min)
                    order.status = 'CLOSED_EXTERNALLY'
                    order.closed_at = datetime.now(timezone.utc)
                    session.commit()
                    if balance > 0:
                        tlogger.info(f"[SYNC] order {order.id} quantità {balance} sotto minimo {min_qty}, chiuso automaticamente")
                    else:
                        tlogger.info(f"[SYNC] order {order.id} chiuso esternamente su {exchange_name}")
                    
                elif balance < order_qty * 0.95:  # 5% tolerance for fees/rounding
                    # Partially sold - update quantity and recreate TP/SL
                    old_qty = order_qty
                    new_qty = balance
                    order.quantity = new_qty
                    session.commit()
                    tlogger.info(f"[SYNC] order {order.id} vendita parziale: {old_qty:.6f} -> {new_qty:.6f}")
                    
                    # Try to cancel old TP/SL orders on exchange and create new ones
                    try:
                        # Cancel existing orders for this symbol
                        if hasattr(adapter, 'client'):
                            open_orders = adapter.client.get_open_orders(symbol=order.symbol)
                            for oo in open_orders:
                                try:
                                    adapter.client.cancel_order(symbol=order.symbol, orderId=oo['orderId'])
                                    tlogger.info(f"[SYNC] Cancellato ordine {oo['orderId']} per {order.symbol}")
                                except Exception as cancel_err:
                                    tlogger.warning(f"[SYNC] Errore cancellazione ordine: {cancel_err}")
                            
                            # Get symbol info for formatting
                            symbol_info = adapter.get_symbol_info(order.symbol)
                            if symbol_info:
                                filters = {f['filterType']: f for f in symbol_info['filters']}
                                step_size = float(filters['LOT_SIZE']['stepSize'])
                                tick_size = float(filters['PRICE_FILTER']['tickSize'])
                                min_qty = float(filters['LOT_SIZE']['minQty'])
                                
                                # Format new quantity
                                formatted_qty = round_to_step(new_qty, step_size)
                                
                                if formatted_qty >= min_qty:
                                    # Recreate TP order if exists
                                    if order.take_profit and float(order.take_profit) > 0:
                                        tp_price = round_to_step(float(order.take_profit), tick_size)
                                        try:
                                            adapter.client.create_order(
                                                symbol=order.symbol,
                                                side='SELL',
                                                type='LIMIT',
                                                timeInForce='GTC',
                                                quantity=str(formatted_qty),
                                                price=str(tp_price)
                                            )
                                            tlogger.info(f"[SYNC] Ricreato TP per ordine {order.id}: qty={formatted_qty}, price={tp_price}")
                                        except Exception as tp_err:
                                            tlogger.warning(f"[SYNC] Errore creazione TP: {tp_err}")
                                else:
                                    # Quantity below minimum - mark as closed
                                    tlogger.info(f"[SYNC] order {order.id} quantità {formatted_qty} sotto minimo {min_qty}, chiuso automaticamente")
                                    order.status = 'CLOSED_EXTERNALLY'
                                    order.closed_at = datetime.now(timezone.utc)
                                    session.commit()
                                    
                    except Exception as ex:
                        tlogger.error(f"[SYNC] Errore aggiornamento TP/SL per ordine {order.id}: {ex}")
                        
            except Exception as e:
                tlogger.error(f"[ERROR] Sync {order.id} on {exchange_name}: {e}")

def check_cancelled_tp_orders():
    """Check if TP orders have been cancelled externally on Binance.
    If a TP is cancelled, remove tp_order_id so the position shows as unprotected.
    The user can then manually recreate the TP or close the position.
    """
    with SessionLocal() as session:
        # Grace period: don't check orders created or updated in the last 30 seconds
        # This prevents race conditions where scheduler runs during API TP/SL update
        grace_period = datetime.now(timezone.utc) - timedelta(seconds=30)
        
        # Get executed orders that have a tp_order_id
        orders_with_tp = session.query(Order).filter(
            Order.status.in_(['EXECUTED', 'PARTIAL_FILLED']),
            Order.tp_order_id != None,
            Order.created_at < grace_period
        ).all()
        
        # Filter out orders that are currently being updated by the API
        filtered_orders = []
        now = datetime.now(timezone.utc)
        for order in orders_with_tp:
            # Skip orders with updating_until in the future (API is modifying TP/SL)
            updating_until = getattr(order, 'updating_until', None)
            if updating_until and now < updating_until:
                tlogger.info(f"[TP_CHECK] Order {order.id}: Skipping (protected until {updating_until})")
                continue
            filtered_orders.append(order)
        
        orders_with_tp = filtered_orders
        
        # Group orders by user, exchange, and symbol to minimize API calls
        # IMPORTANT: Must include exchange_id to avoid using wrong adapter
        from collections import defaultdict
        orders_by_user_exchange_symbol = defaultdict(list)
        for order in orders_with_tp:
            exchange_id = getattr(order, 'exchange_id', None) or 1  # Default to binance
            key = (order.user_id, exchange_id, order.symbol, getattr(order, 'is_testnet', False) or False)
            orders_by_user_exchange_symbol[key].append(order)
        
        for (user_id, exchange_id, symbol, is_testnet), user_orders in orders_by_user_exchange_symbol.items():
            try:
                # Get first order to determine exchange
                first_order = user_orders[0]
                exchange_name = get_order_exchange_name(first_order, session)
                adapter = get_exchange_adapter(user_id, exchange_name, is_testnet)
                
                # Get all open orders for this symbol
                open_orders = adapter.get_open_orders(symbol)
                open_order_ids = {str(o['orderId']) for o in open_orders}
                
                # Debug logging
                tlogger.info(f"[TP_CHECK] {exchange_name} {symbol}: Found {len(open_orders)} open orders: {list(open_order_ids)[:10]}")
                
                # Check each order's TP
                for order in user_orders:
                    tp_id_str = str(order.tp_order_id) if order.tp_order_id else None
                    tlogger.info(f"[TP_CHECK] Order {order.id}: tp_order_id={tp_id_str}, in_open={tp_id_str in open_order_ids if tp_id_str else 'N/A'}")
                    
                    if order.tp_order_id and str(order.tp_order_id) not in open_order_ids:
                        # TP was cancelled externally - mark order as closed
                        tlogger.warning(f"[TP_CANCELLED] Order {order.id} ({order.symbol}): TP order {order.tp_order_id} cancelled externally")
                        order.status = 'CLOSED_EXTERNALLY'
                        order.closed_at = datetime.now(timezone.utc)
                        order.tp_order_id = None
                        session.commit()
                        
                        # Notify via Telegram
                        try:
                            from src.telegram_notifications import notify_tp_cancelled
                            notify_tp_cancelled(order, exchange_name=exchange_name)
                            tlogger.warning(f"[TP_CANCELLED] Order {order.id} TP cancelled externally, marked as CLOSED_EXTERNALLY")
                        except:
                            pass  # Notification is optional
                        
            except Exception as e:
                tlogger.error(f"[TP_CHECK] Error checking TPs for user {user_id}, {symbol}: {e}")


def main():
    """Main scheduler loop"""
    from apscheduler.schedulers.blocking import BlockingScheduler
    
    # Setup file logging
    os.makedirs('logs', exist_ok=True)
    file_handler = logging.FileHandler('logs/scheduler.log')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    tlogger.addHandler(file_handler)
    
    # Also log to console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    tlogger.addHandler(console_handler)
    
    tlogger.info("=" * 50)
    tlogger.info("CryptoBot Scheduler Started")
    tlogger.info("=" * 50)
    
    # Start WebSocket streams for real-time order updates
    try:
        from src.stream_manager import stream_manager
        stream_manager.start()
        tlogger.info("WebSocket streams started for real-time updates")
    except Exception as e:
        tlogger.warning(f"Could not start WebSocket streams: {e}")
        tlogger.info("Falling back to polling-only mode")
    
    scheduler = BlockingScheduler()
    
    # Check pending orders every minute
    scheduler.add_job(auto_execute_pending, 'interval', minutes=1, id='auto_execute')
    
    # Check stop losses every minute
    scheduler.add_job(check_and_execute_stop_loss, 'interval', minutes=1, id='check_sl')
    
    # Sync with exchanges every 5 minutes
    scheduler.add_job(sync_orders, 'interval', minutes=5, id='sync_exchanges')
    
    # Check for externally cancelled TP orders every 60 seconds (fallback for WebSocket)
    scheduler.add_job(check_cancelled_tp_orders, 'interval', seconds=60, id='check_tp_cancelled')
    
    tlogger.info("Scheduler jobs registered:")
    tlogger.info("  - auto_execute_pending: every 1 min")
    tlogger.info("  - check_and_execute_stop_loss: every 1 min")
    tlogger.info("  - sync_orders: every 5 min")
    tlogger.info("  - check_cancelled_tp_orders: every 60 sec (fallback)")
    tlogger.info("")
    tlogger.info("Press CTRL+C to stop")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        # Stop WebSocket streams on shutdown
        try:
            stream_manager.stop()
        except:
            pass
        tlogger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
