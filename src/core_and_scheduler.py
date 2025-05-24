import sys
from src.binance_utils import has_sufficient_balance
from binance.client import Client
from binance.exceptions import BinanceAPIException
import os
import logging
from types import SimpleNamespace
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.telegram_notifications import notify_open, notify_close
from models import Order, init_db, SessionLocal, APIKey, Exchange
from sqlalchemy import and_
from src.adapters import BinanceAdapter

init_db()

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
    return klines[-1]

def get_binance_client(user_id):
    with SessionLocal() as session:
        exchange = session.query(Exchange).filter_by(name="binance").first()
        api_key_obj = session.query(APIKey).filter_by(user_id=user_id, exchange_id=exchange.id, is_testnet=False).first()

        if not api_key_obj:
            raise Exception(f"API key not found for user {user_id}")

        return Client(api_key_obj.api_key, api_key_obj.secret_key)

def auto_execute_pending():
    with SessionLocal() as session:
        pendings = session.query(Order).filter(Order.status == 'PENDING').all()
        tlogger.info(f"[DEBUG] auto_execute: {len(pendings)} PENDING orders")

        for order in pendings:
            try:
                client = get_binance_client(order.user_id)
            except Exception as e:
                tlogger.error(f"[ERROR] Impossibile recuperare API per user {order.user_id}: {e}")
                continue

            quote_asset = order.symbol[-4:]
            required = float(order.entry_price) * float(order.quantity)

            if not has_sufficient_balance(client, quote_asset, required):
                tlogger.error(f"[ERROR] Saldo insufficiente per order {order.id}: richiesti {required:.2f} {quote_asset}")
                continue

            created_dt = order.created_at
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)

            candle = fetch_last_closed_candle(order.symbol, order.entry_interval, client)
            ts_candle = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)
            last_close = float(candle[4])

            tlogger.info(f"[DEBUG] order={order.id} | created={created_dt} | ts_candle={ts_candle} | entry={order.entry_price} | last_close={last_close}")

            if order.entry_price <= last_close <= order.max_entry and ts_candle > created_dt:
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
                    qty_str = ('{:.8f}'.format(float(order.quantity))).rstrip('0').rstrip('.')

                    # BUY MARKET
                    resp = adapter.client.create_order(
                        symbol=order.symbol,
                        side='BUY',
                        type='MARKET',
                        quantity=qty_str
                    )

                    executed_qty = sum(float(fill['qty']) for fill in resp['fills'])
                    exec_price = float(resp['fills'][0]['price'])
                    exec_time = datetime.now(timezone.utc)

                    # TP LIMIT
                    adapter.client.create_order(
                        symbol=order.symbol,
                        side='SELL',
                        type='LIMIT',
                        timeInForce='GTC',
                        quantity=qty_str,
                        price=str(order.take_profit)
                    )

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
                        user_id=order.user_id
                    ))
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

