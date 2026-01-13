import sys
from src.binance_utils import has_sufficient_balance
from binance.client import Client
from binance.exceptions import BinanceAPIException
import os
from src.adapters import BinanceAdapter

import logging
from types import SimpleNamespace
from datetime import datetime, timezone
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.telegram_notifications import notify_open, notify_close
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

tlogger = logging.getLogger('core')
tlogger.setLevel(logging.INFO)

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

def round_step_size(value, step_size):
    return math.floor(value / step_size) * step_size

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

            candle = fetch_last_closed_candle(order.symbol, order.entry_interval, client)
            ts_candle = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)
            last_close = float(candle[4])

            tlogger.info(f"[DEBUG] order={order.id} | created={created_dt} | ts_candle={ts_candle} | entry={order.entry_price} | last_close={last_close}")

            if (
                order.entry_price <= last_close <= order.max_entry and
                ts_candle > created_dt and                  # candela successiva alla creazione
                (not order.executed_at)                     # esegui solo se mai eseguito
            ):
                exchange = session.query(Exchange).filter_by(name="binance").first()
                api_key_obj = session.query(APIKey).filter_by(
                    user_id=order.user_id,
                    exchange_id=exchange.id,
                    is_testnet=False
                ).first()

                if not api_key_obj:
                    tlogger.warning(f"[WARNING] Nessuna APIKey trovata per user {order.user_id}")
                    continue

                adapter = BinanceAdapter(
                    api_key=api_key_obj.api_key,
                    api_secret=api_key_obj.secret_key,
                    testnet=api_key_obj.is_testnet
                )

                try:
                    symbol_info = client.get_symbol_info(order.symbol)
                    filters = {f['filterType']: f for f in symbol_info['filters']}
                    step_size = float(filters['LOT_SIZE']['stepSize'])
                    min_notional = float(filters['MIN_NOTIONAL']['minNotional']) if 'MIN_NOTIONAL' in filters else 0

                    qty = round_step_size(float(order.quantity), float(step_size))
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

                    # TP LIMIT - use actual executed quantity
                    adapter.client.create_order(
                        symbol=order.symbol,
                        side='SELL',
                        type='LIMIT',
                        timeInForce='GTC',
                        quantity=executed_qty_str,
                        price=str(order.take_profit)
                    )

                    order.status = 'PARTIAL_FILLED' if is_partial else 'EXECUTED'
                    order.executed_at = exec_time
                    order.executed_price = exec_price
                    order.quantity = executed_qty  # Update with actual executed quantity
                    session.commit()

                    tlogger.info(f"[{'PARTIAL_FILLED' if is_partial else 'EXECUTED'}] order {order.id} @ {exec_price}, qty={executed_qty}/{original_qty}, TP placed")

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

def close_position_market(self, symbol, quantity):
    try:
        qty_str = ('{:.8f}'.format(float(quantity))).rstrip('0').rstrip('.')
        order = self.client.create_order(
            symbol=symbol,
            side='SELL',
            type='MARKET',
            quantity=qty_str
        )
        return order
    except BinanceAPIException as e:
        print(f"Errore BinanceAPI nella chiusura posizione: {e}")
        raise
    except Exception as e:
        print(f"Errore generico nella chiusura posizione: {e}")
        raise
        
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

            # PATCH: chiusura candela <= stop_loss e candela successiva all'apertura
            if (
                order.stop_loss is not None and
                last_close <= float(order.stop_loss) and
                ts_candle > order.executed_at
            ):
                exchange = session.query(Exchange).filter_by(name="binance").first()
                api_key_obj = session.query(APIKey).filter_by(
                    user_id=order.user_id,
                    exchange_id=exchange.id,
                    is_testnet=False
                ).first()
                adapter = BinanceAdapter(
                    api_key=api_key_obj.api_key,
                    api_secret=api_key_obj.secret_key,
                    testnet=api_key_obj.is_testnet
                )
                try:
                    base_asset = order.symbol.replace("USDC", "").replace("USDT", "")
                    balance = float(client.get_asset_balance(asset=base_asset)['free'])
                    symbol_info = client.get_symbol_info(order.symbol)
                    filters = {f['filterType']: f for f in symbol_info['filters']}
                    step_size = float(filters['LOT_SIZE']['stepSize'])

                    # Se saldo troppo basso, marca come chiuso esternamente e non mandare ordine
                    if balance < step_size:
                        tlogger.warning(f"[SKIP CLOSE] order {order.id}: saldo {base_asset} troppo basso ({balance})")
                        order.status = 'CLOSED_EXTERNALLY'
                        order.quantity = 0  # Update quantity to reflect actual state
                        order.closed_at = datetime.now(timezone.utc)
                        session.commit()
                        continue

                    original_qty = float(order.quantity)
                    qty_to_close = min(original_qty, balance)
                    
                    # Execute SL
                    adapter.close_position_market(order.symbol, qty_to_close)
                    
                    # Update order with actual closed quantity
                    order.quantity = qty_to_close  # Update to reflect what was actually sold
                    order.status = 'CLOSED_SL'
                    order.closed_at = datetime.now(timezone.utc)
                    session.commit()
                    
                    tlogger.info(f"[STOP LOSS] order {order.id} chiuso SL, qty={qty_to_close}/{original_qty}")
                    notify_close(order, exchange_name=exchange_name)
                except Exception as e:
                    tlogger.error(f"[ERROR] SL {order.id}: {e}")
                    
def sync_orders():
    """Sync executed orders with exchanges - mark externally closed orders"""
    with SessionLocal() as session:
        executed_orders = session.query(Order).filter(Order.status.in_(['EXECUTED', 'PARTIAL_FILLED'])).all()
        for order in executed_orders:
            # Get order configuration
            is_testnet = getattr(order, 'is_testnet', False) or False
            exchange_name = get_order_exchange_name(order, session)
            
            try:
                adapter = get_exchange_adapter(order.user_id, exchange_name, is_testnet)
                base_asset = order.symbol.replace("USDC", "")
                balance = adapter.get_balance(base_asset)
                
                if balance == 0:
                    order.status = 'CLOSED_EXTERNALLY'
                    order.closed_at = datetime.now(timezone.utc)
                    session.commit()
                    tlogger.info(f"[SYNC] order {order.id} chiuso esternamente su {exchange_name}")
            except Exception as e:
                tlogger.error(f"[ERROR] Sync {order.id} on {exchange_name}: {e}")


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
    
    scheduler = BlockingScheduler()
    
    # Check pending orders every minute
    scheduler.add_job(auto_execute_pending, 'interval', minutes=1, id='auto_execute')
    
    # Check stop losses every minute
    scheduler.add_job(check_and_execute_stop_loss, 'interval', minutes=1, id='check_sl')
    
    # Sync with exchanges every 5 minutes
    scheduler.add_job(sync_orders, 'interval', minutes=5, id='sync_exchanges')
    
    tlogger.info("Scheduler jobs registered:")
    tlogger.info("  - auto_execute_pending: every 1 min")
    tlogger.info("  - check_and_execute_stop_loss: every 1 min")
    tlogger.info("  - sync_orders: every 5 min")
    tlogger.info("")
    tlogger.info("Press CTRL+C to stop")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        tlogger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
