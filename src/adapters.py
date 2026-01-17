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
    
    def get_open_orders(self, symbol: str) -> list:
        """Get open orders for a symbol - returns list of dicts with 'side', 'orderId', 'origQty', 'price'"""
        raise NotImplementedError
    
    def get_asset_balance_detail(self, asset: str) -> dict:
        """Get detailed balance - returns dict with 'free' and 'locked'"""
        raise NotImplementedError
    
    def get_recent_trades(self, symbol: str, limit: int = 5) -> list:
        """Get recent trades - returns list of dicts with 'isBuyer', 'qty', 'price'"""
        raise NotImplementedError

class BinanceAdapter(ExchangeAdapter):

    def __init__(self, api_key, api_secret, testnet=True):
        self.client = Client(api_key, api_secret, testnet=testnet)


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
        with SessionLocal() as session:
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
        """Get total balance (free + locked) for an asset"""
        bal = self.client.get_asset_balance(asset=asset)
        if bal:
            free = float(bal.get('free', 0))
            locked = float(bal.get('locked', 0))
            return free + locked
        return 0.0

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

    def update_spot_tp_sl(self, symbol, quantity, new_tp, new_sl, user_id=None, old_tp=None, tp_order_id=None):
        """
        Update TP/SL for a position.
        tp_order_id: If provided, directly cancel this Binance order ID (most accurate)
        old_tp: Fallback - used to identify the specific order to cancel by price
        """
        import logging
        logger = logging.getLogger('adapters')
        
        try:
            # Get symbol info for proper formatting
            symbol_info = self.client.get_symbol_info(symbol)
            filters = {f['filterType']: f for f in symbol_info['filters']}
            step_size = filters['LOT_SIZE']['stepSize']
            tick_size = filters['PRICE_FILTER']['tickSize']
            
            from decimal import Decimal, ROUND_DOWN
            
            def format_qty(qty):
                step = Decimal(str(step_size))
                qty_dec = Decimal(str(qty)).quantize(step, rounding=ROUND_DOWN)
                return str(qty_dec).rstrip('0').rstrip('.')
            
            def format_price(price):
                tick = Decimal(str(tick_size))
                price_dec = Decimal(str(price)).quantize(tick, rounding=ROUND_DOWN)
                return str(price_dec).rstrip('0').rstrip('.')
            
            # Cancel existing TP order
            if tp_order_id:
                # Best case: we know the exact order ID
                logger.info(f"[UPDATE_TP] Cancelling TP order by ID: {tp_order_id}")
                try:
                    self.client.cancel_order(symbol=symbol, orderId=int(tp_order_id))
                    logger.info(f"[UPDATE_TP] Cancelled order {tp_order_id}")
                except Exception as e:
                    logger.warning(f"[UPDATE_TP] Could not cancel order {tp_order_id}: {e}")
            elif old_tp:
                # Fallback: find by qty+price
                logger.info(f"[UPDATE_TP] No tp_order_id, searching by qty={quantity} price={old_tp}")
                open_orders = self.client.get_open_orders(symbol=symbol)
                for order in open_orders:
                    if order['side'] == 'SELL':
                        order_qty = float(order['origQty'])
                        order_price = float(order['price'])
                        qty_matches = abs(order_qty - float(quantity)) < 0.0001
                        price_matches = abs(order_price - float(old_tp)) < 0.1
                        if qty_matches and price_matches:
                            logger.info(f"[UPDATE_TP] Found matching order {order['orderId']}, cancelling")
                            self.client.cancel_order(symbol=symbol, orderId=order['orderId'])
                            break

            # Create new TP order with properly formatted qty and price
            qty_str = format_qty(quantity)
            price_str = format_price(new_tp)
            print(f"[UPDATE_TP] Creating TP order: qty={qty_str} price={price_str} (raw: {quantity})")
            
            new_order = self.client.create_order(
                symbol=symbol,
                side='SELL',
                type='LIMIT',
                timeInForce='GTC',
                quantity=qty_str,
                price=price_str
            )
            new_tp_order_id = str(new_order.get('orderId'))
            logger.info(f"[UPDATE_TP] Created new TP order {new_tp_order_id} @ {price_str}")

            return new_tp_order_id
        except BinanceAPIException as e:
            logger.error(f"[UPDATE_TP] Binance API error: {e}")
            raise
        except Exception as e:
            logger.error(f"[UPDATE_TP] Error: {e}")
            raise
    
    def get_open_orders(self, symbol: str) -> list:
        """Get open orders for a symbol"""
        return self.client.get_open_orders(symbol=symbol)
    
    def get_asset_balance_detail(self, asset: str) -> dict:
        """Get detailed balance - returns dict with 'free' and 'locked'"""
        bal = self.client.get_asset_balance(asset=asset)
        if bal:
            return {'free': float(bal.get('free', 0)), 'locked': float(bal.get('locked', 0))}
        return {'free': 0.0, 'locked': 0.0}
    
    def get_recent_trades(self, symbol: str, limit: int = 5) -> list:
        """Get recent trades - normalized format"""
        trades = self.client.get_my_trades(symbol=symbol, limit=limit)
        return [{'isBuyer': t.get('isBuyer', True), 'qty': float(t.get('qty', 0)), 'price': float(t.get('price', 0))} for t in trades]

class BybitAdapter(ExchangeAdapter):
    """Bybit exchange adapter - spot trading"""
    
    def __init__(self, api_key: str, secret_key: str, testnet: bool = False):
        config = {
            'apiKey': api_key,
            'secret': secret_key,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        }
        
        if testnet:
            config['sandbox'] = True
            # Bybit testnet URLs
            config['urls'] = {
                'api': {
                    'public': 'https://api-testnet.bybit.com',
                    'private': 'https://api-testnet.bybit.com',
                }
            }
        
        self.client = ccxt.bybit(config)
        self.testnet = testnet
    
    def truncate(self, quantity: float, precision: int) -> float:
        factor = 10 ** precision
        return math.floor(quantity * factor) / factor
    
    def get_symbol_precision(self, symbol: str) -> int:
        """Get quantity precision for a symbol"""
        try:
            markets = self.client.load_markets()
            if symbol in markets:
                return markets[symbol].get('precision', {}).get('amount', 8)
            # Try with / format (BTC/USDC)
            formatted = symbol.replace('USDC', '/USDC').replace('USDT', '/USDT')
            if formatted in markets:
                return markets[formatted].get('precision', {}).get('amount', 8)
        except:
            pass
        return 8  # fallback
    
    def _format_symbol(self, symbol: str) -> str:
        """Convert BTCUSDC to BTC/USDC format for ccxt"""
        for quote in ['USDC', 'USDT']:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                return f"{base}/{quote}"
        return symbol
    
    def get_balance(self, asset: str) -> float:
        """Get total balance (free + used) for an asset"""
        try:
            bal = self.client.fetch_balance()
            if asset in bal:
                free = float(bal[asset].get('free', 0.0))
                used = float(bal[asset].get('used', 0.0))
                return free + used
            return 0.0
        except Exception as e:
            print(f"Bybit get_balance error: {e}")
            return 0.0
    
    def get_symbol_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        try:
            formatted = self._format_symbol(symbol)
            ticker = self.client.fetch_ticker(formatted)
            return float(ticker.get('last', 0))
        except Exception as e:
            print(f"Bybit get_symbol_price error: {e}")
            return 0.0
    
    def place_order(self, symbol: str, side: str, type_: str, quantity: float, price: float = None):
        formatted = self._format_symbol(symbol)
        order_type = type_.lower()
        order_side = side.lower()
        
        if order_type == 'market':
            return self.client.create_market_order(formatted, order_side, quantity)
        else:
            return self.client.create_limit_order(formatted, order_side, quantity, price)
    
    def cancel_order(self, symbol: str, order_id):
        formatted = self._format_symbol(symbol)
        return self.client.cancel_order(order_id, formatted)
    
    def close_position_market(self, symbol: str, quantity: float):
        """Close a spot position by selling at market"""
        try:
            precision = self.get_symbol_precision(symbol)
            truncated_qty = self.truncate(float(quantity) * 0.999, precision)
            formatted = self._format_symbol(symbol)
            
            order = self.client.create_market_order(
                formatted,
                'sell',
                truncated_qty
            )
            return order
        except Exception as e:
            print(f"Bybit close_position_market error: {e}")
            raise
    
    def update_spot_tp_sl(self, symbol: str, quantity: float, new_tp: float, new_sl: float, user_id: int = None):
        """Update TP/SL for a spot position"""
        with SessionLocal() as session:
            try:
                formatted = self._format_symbol(symbol)
                
                # Cancel existing open orders for this symbol
                open_orders = self.client.fetch_open_orders(formatted)
                for order in open_orders:
                    if order['side'] == 'sell':
                        try:
                            self.client.cancel_order(order['id'], formatted)
                        except:
                            pass
                
                # Place new TP limit order
                precision = self.get_symbol_precision(symbol)
                truncated_qty = self.truncate(float(quantity), precision)
                
                self.client.create_limit_order(
                    formatted,
                    'sell',
                    truncated_qty,
                    new_tp
                )
                
                # Update order in database
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
            except Exception as e:
                print(f"Bybit update_spot_tp_sl error: {e}")
                raise
    
    def get_open_orders(self, symbol: str) -> list:
        """Get open orders for a symbol - ccxt format"""
        formatted = self._format_symbol(symbol)
        orders = self.client.fetch_open_orders(formatted)
        # Normalize to same format as Binance
        return [{'side': o['side'].upper(), 'orderId': o['id'], 'origQty': o['amount'], 'price': o['price']} for o in orders]
    
    def get_asset_balance_detail(self, asset: str) -> dict:
        """Get detailed balance - returns dict with 'free' and 'locked'"""
        try:
            bal = self.client.fetch_balance()
            if asset in bal:
                return {'free': float(bal[asset].get('free', 0)), 'locked': float(bal[asset].get('used', 0))}
            return {'free': 0.0, 'locked': 0.0}
        except Exception as e:
            print(f"Bybit get_asset_balance_detail error: {e}")
            return {'free': 0.0, 'locked': 0.0}
    
    def get_recent_trades(self, symbol: str, limit: int = 5) -> list:
        """Get recent trades - normalized format"""
        try:
            formatted = self._format_symbol(symbol)
            trades = self.client.fetch_my_trades(formatted, limit=limit)
            return [{'isBuyer': t['side'].lower() == 'buy', 'qty': float(t['amount']), 'price': float(t['price'])} for t in trades]
        except Exception as e:
            print(f"Bybit get_recent_trades error: {e}")
            return []
