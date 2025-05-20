# src/core_and_scheduler.py
import sys
from src.binance_utils import has_sufficient_balance
import sqlite3
from datetime import datetime, timezone
from binance.client import Client
from binance.exceptions import BinanceAPIException
import os
import logging
from types import SimpleNamespace
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.telegram_notifications import notify_open, notify_close
from models import Order, init_db, SessionLocal
from sqlalchemy import and_
from datetime import datetime, timezone
from types import SimpleNamespace

init_db()
session = SessionLocal()

# Configuration
#DB_PATH    = os.getenv('DB_PATH', 'trades.db')

# --- Configurazione API Testnet ----------------
API_KEY    = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
client     = Client(API_KEY, API_SECRET, testnet=True)

# Interval mapping DB -> Binance API, including 5-minute timeframe
INTERVAL_MAP = {
    'M5':    '5m',
    'H1':    '1h',
    'H4':    '4h',
    'Daily': '1d',
}

# Logger setup
tlogger = logging.getLogger('core')
tlogger.setLevel(logging.INFO)

def fetch_last_closed_candle(symbol: str, interval: str):
    api_interval = INTERVAL_MAP.get(interval, interval)
    klines = client.get_klines(symbol=symbol, interval=api_interval, limit=2)
    return klines[-1]

def auto_execute_pending():
    session = SessionLocal()

    # 1) Handle PENDING -> EXECUTED
    pendings = session.query(Order).filter(Order.status == 'PENDING').all()
    tlogger.info(f"[DEBUG] auto_execute: {len(pendings)} PENDING orders")

    for order in pendings:
        quote_asset = order.symbol[-4:]
        required = float(order.entry_price) * float(order.quantity)
        if not has_sufficient_balance(client, quote_asset, required):
            tlogger.error(
                f"[ERROR] Saldo insufficiente per order {order.id}: "
                f"richiesti {required:.2f} {quote_asset}"
            )
            continue  # salta l'ordine

        created_dt = order.created_at
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)

        candle = fetch_last_closed_candle(order.symbol, order.entry_interval)
        ts_candle = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)
        last_close = float(candle[4])
        tlogger.info(
            f"[DEBUG] order={order.id} | created={created_dt} | ts_candle={ts_candle} | "
            f"entry={order.entry_price} | last_close={last_close}"
        )
        if last_close >= order.entry_price and ts_candle > created_dt:
            tlogger.info(f"[DEBUG] order {order.id} TRIGGERED: sending BUY & TP")
            try:
                qty_str = ('{:.8f}'.format(float(order.quantity))).rstrip('0').rstrip('.')
                resp = client.create_order(
                    symbol=order.symbol,
                    side='BUY',
                    type='MARKET',
                    quantity=qty_str
                )
                executed_qty = sum(float(fill['qty']) for fill in resp['fills'])
                exec_price = float(resp['fills'][0]['price'])
                exec_time = datetime.now(timezone.utc)

                client.create_order(
                    symbol=order.symbol,
                    side='SELL',
                    type='LIMIT',
                    timeInForce='GTC',
                    quantity=qty_str,
                    price=str(order.take_profit)
                )

                # Update DB
                order.status = 'EXECUTED'
                order.executed_at = exec_time
                order.executed_price = exec_price
                order.quantity = executed_qty
                session.commit()
                tlogger.info(f"[EXECUTED] order {order.id} @ {exec_price}, TP placed")

                notify_open(SimpleNamespace(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    entry_price=exec_price,
                    user_id=order.user_id  # importante per notifiche user-specific
                ))
            except BinanceAPIException as e:
                tlogger.error(f"[ERROR] Binance API exec {order.id}: {e}")
            except Exception as e:
                tlogger.error(f"[ERROR] Unexpected exec {order.id}: {e}")
        else:
            tlogger.info(f"[DEBUG] order {order.id} NOT triggered")

