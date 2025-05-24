from models import SessionLocal
from models import Order, SessionLocal, APIKey, Exchange
from binance.exceptions import BinanceAPIException
from binance.client import Client as BinanceClient
from binance.client import Client

import ccxt
import math 

class ExchangeAdapter:
    def get_balance(self, asset: str) -> float:
        raise NotImplementedError

    def place_order(self, symbol: str, side: str, type_: str, quantity: float, price: float = None):
        raise NotImplementedError

    def cancel_order(self, symbol: str, order_id):
        raise NotImplementedError

class BinanceAdapter(ExchangeAdapter):

    def __init__(self, api_key, api_secret, testnet=True):
        self.client = Client(api_key, api_secret, testnet=testnet)

    def get_client(self, user_id):
        session = SessionLocal()

    def truncate(self, quantity: float, precision: int) -> float:
        factor = 10 ** precision
        return math.floor(quantity * factor) / factor

    def get_symbol_precision(self, symbol: str) -> int:
        """
        Recupera la precisione corretta per un simbolo su Binance.
        """
        info = self.client.get_exchange_info()
        for s in info['symbols']:
            if s['symbol'] == symbol:
                for f in s['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step_size = float(f['stepSize'])
                        return abs(int(round(math.log10(step_size))))
        return 3  # fallback se non trova nulla

    def close_position_market(self, symbol, quantity):
        """
        Chiude una posizione su Binance spot vendendo a mercato,
        arrotondando per difetto per evitare errori di saldo.
        """
        try:
            precision = self.get_symbol_precision(symbol)
            truncated_qty = self.truncate(float(quantity)*0.999, precision)
            qty_str = ('{:.8f}'.format(truncated_qty)).rstrip('0').rstrip('.')

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

    def get_symbol_price(self, symbol):
        ticker = self.client.get_symbol_ticker(symbol=symbol)
        return float(ticker['price'])

    def __init__(self, api_key, api_secret, testnet=True):
        self.client = Client(api_key, api_secret, testnet=testnet)

    def get_client(self, user_id):
        session = SessionLocal()
        exchange = session.query(Exchange).filter_by(name="binance").first()
        if not exchange:
            raise Exception("Exchange 'binance' non trovato nel DB")

        api_key_entry = (
            session.query(APIKey)
            .filter_by(user_id=user_id, exchange_id=exchange.id, is_testnet=False)
            .first()
        )

        if not api_key_entry:
            raise Exception(f"Nessuna API key trovata per user_id={user_id}")

        return Client(api_key_entry.api_key, api_key_entry.secret_key)

    def get_balance(self, asset: str) -> float:
        bal = self.client.get_asset_balance(asset=asset)
        return float(bal['free']) if bal and 'free' in bal else 0.0

    def place_order(self, symbol: str, side: str, type_: str, quantity: float, price: float = None):
        params = {
            'symbol': symbol,
            'side': side,
            'type': type_,
            'quantity': quantity
        }
        if price is not None:
            params['price'] = price
        return self.client.create_order(**params)

    def cancel_order(self, symbol: str, order_id):
        return self.client.cancel_order(symbol=symbol, orderId=order_id)

    def update_spot_tp_sl(self, symbol, quantity, new_tp, new_sl, user_id=None):
        session = SessionLocal()
        try:
            open_orders = self.client.get_open_orders(symbol=symbol)
            for order in open_orders:
                if order['side'] == 'SELL' and float(order['origQty']) == float(quantity):
                    self.client.cancel_order(symbol=symbol, orderId=order['orderId'])

            qty_str = ('{:.8f}'.format(float(quantity))).rstrip('0').rstrip('.')
            self.client.create_order(
                symbol=symbol,
                side='SELL',
                type='LIMIT',
                timeInForce='GTC',
                quantity=qty_str,
                price=str(new_tp)
            )

            order_query = session.query(Order).filter(
                Order.symbol == symbol,
                Order.quantity == quantity,
                Order.status == "EXECUTED"
            )
            if user_id:
                order_query = order_query.filter(Order.user_id == user_id)
            order = order_query.order_by(Order.executed_at.desc()).first()
            if order:
                order.take_profit = new_tp
                order.stop_loss = new_sl
                session.commit()

            return True
        except BinanceAPIException as e:
            print(f"Errore Binance API update TP: {e}")
            raise
        except Exception as e:
            print(f"Errore generico update TP/SL: {e}")
            raise
        finally:
            session.close()

class BybitAdapter(ExchangeAdapter):
    def __init__(self, api_key: str, secret_key: str):
        self.client = ccxt.bybit({
            'apiKey': api_key,
            'secret': secret_key
        })

    def get_balance(self, asset: str) -> float:
        bal = self.client.fetch_balance()
        return float(bal.get(asset, {}).get('free', 0.0))

    def place_order(self, symbol: str, side: str, type_: str, quantity: float, price: float = None):
        params = {
            'symbol': symbol,
            'type': type_.lower(),
            'side': side.lower(),
            'amount': quantity
        }
        if price is not None:
            params['price'] = price
        return self.client.create_order(**params)

    def cancel_order(self, symbol: str, order_id):
        return self.client.cancel_order(symbol=symbol, id=order_id)

