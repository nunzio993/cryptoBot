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
                step = Decimal(str(step_size)).normalize()  # "0.00100000" -> "0.001"
                qty_dec = Decimal(str(qty))
                # Round down to step
                result = (qty_dec / step).quantize(Decimal('1'), rounding=ROUND_DOWN) * step
                return str(result.normalize())
            
            def format_price(price):
                tick = Decimal(str(tick_size)).normalize()
                # Handle both Decimal and float inputs, avoid scientific notation
                if isinstance(price, Decimal):
                    price_dec = price
                else:
                    price_dec = Decimal(str(float(price)))
                result = (price_dec / tick).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick
                # Use format to avoid scientific notation
                return f"{float(result):.10f}".rstrip('0').rstrip('.')
            
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
            print(f"[UPDATE_TP] step={step_size} qty={qty_str} price={price_str} (raw: {quantity})")
            
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
    
    # === Wrapper methods for uniform interface ===
    
    def get_symbol_info(self, symbol: str) -> dict:
        """Get symbol info - normalized format"""
        return self.client.get_symbol_info(symbol)
    
    def get_all_tickers(self) -> list:
        """Get all tickers"""
        return self.client.get_all_tickers()
    
    def get_account(self) -> dict:
        """Get account info"""
        return self.client.get_account()
    
    def get_asset_balance(self, asset: str) -> dict:
        """Get asset balance - returns dict with 'free' and 'locked'"""
        return self.client.get_asset_balance(asset=asset)
    
    def order_market_buy(self, symbol: str, quantity: float) -> dict:
        """Place a market buy order"""
        qty_str = ('{:.8f}'.format(quantity)).rstrip('0').rstrip('.')
        return self.client.order_market_buy(symbol=symbol, quantity=qty_str)
    
    def get_symbol_ticker(self, symbol: str) -> dict:
        """Get symbol ticker"""
        return self.client.get_symbol_ticker(symbol=symbol)
    
    def get_klines(self, symbol: str, interval: str, limit: int = 2) -> list:
        """Get klines/candlesticks"""
        return self.client.get_klines(symbol=symbol, interval=interval, limit=limit)

class BybitAdapter(ExchangeAdapter):
    """Bybit exchange adapter using pybit library - spot trading"""
    
    def __init__(self, api_key: str, secret_key: str, testnet: bool = False):
        from pybit.unified_trading import HTTP
        
        self.session = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=secret_key,
        )
        self.testnet = testnet
        self._markets_cache = None
        
        # For backward compatibility with code that calls adapter.client.method()
        # The adapter itself provides the same interface
        self.client = self
    
    def truncate(self, quantity: float, precision: int) -> float:
        factor = 10 ** precision
        return math.floor(quantity * factor) / factor
    
    def _format_symbol(self, symbol: str) -> str:
        """Bybit uses BTCUSDT format (no slash)"""
        return symbol.replace('/', '')
    
    def get_symbol_precision(self, symbol: str) -> int:
        """Get quantity precision for a symbol"""
        try:
            formatted = self._format_symbol(symbol)
            result = self.session.get_instruments_info(category="spot", symbol=formatted)
            if result['retCode'] == 0 and result['result']['list']:
                lot_size_filter = result['result']['list'][0].get('lotSizeFilter', {})
                base_precision = lot_size_filter.get('basePrecision', '0.00000001')
                # Count decimal places
                if '.' in base_precision:
                    return len(base_precision.split('.')[1].rstrip('0'))
                return 8
        except:
            pass
        return 8  # fallback
    
    def get_balance(self, asset: str) -> float:
        """Get total balance for an asset"""
        try:
            result = self.session.get_wallet_balance(accountType="UNIFIED")
            if result['retCode'] == 0:
                coins = result['result']['list'][0].get('coin', [])
                for coin in coins:
                    if coin['coin'] == asset:
                        return float(coin.get('walletBalance', 0))
            return 0.0
        except Exception as e:
            print(f"Bybit get_balance error: {e}")
            return 0.0
    
    def get_symbol_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        try:
            formatted = self._format_symbol(symbol)
            result = self.session.get_tickers(category="spot", symbol=formatted)
            if result['retCode'] == 0 and result['result']['list']:
                return float(result['result']['list'][0].get('lastPrice', 0))
            return 0.0
        except Exception as e:
            print(f"Bybit get_symbol_price error: {e}")
            return 0.0
    
    def place_order(self, symbol: str, side: str, type_: str, quantity: float, price: float = None):
        """Place a spot order"""
        formatted = self._format_symbol(symbol)
        order_type = "Market" if type_.lower() == 'market' else "Limit"
        order_side = side.capitalize()
        
        params = {
            "category": "spot",
            "symbol": formatted,
            "side": order_side,
            "orderType": order_type,
            "qty": str(quantity),
        }
        
        if order_type == "Limit" and price:
            # Format price according to tickSize
            try:
                instrument_info = self.session.get_instruments_info(category="spot", symbol=formatted)
                if instrument_info['retCode'] == 0 and instrument_info['result']['list']:
                    tick_size = instrument_info['result']['list'][0].get('priceFilter', {}).get('tickSize', '0.01')
                    # Count decimal places in tickSize
                    if '.' in tick_size:
                        decimals = len(tick_size.split('.')[1].rstrip('0'))
                    else:
                        decimals = 0
                    formatted_price = f"{float(price):.{decimals}f}"
                else:
                    formatted_price = str(price)
            except:
                formatted_price = str(price)
            
            params["price"] = formatted_price
            params["timeInForce"] = "GTC"
        
        result = self.session.place_order(**params)
        if result['retCode'] != 0:
            raise Exception(f"Bybit order failed: {result['retMsg']}")
        return result['result']
    
    def cancel_order(self, symbol: str, order_id=None, orderId=None):
        """Cancel an order - accepts both order_id and orderId for compatibility"""
        actual_order_id = order_id or orderId
        formatted = self._format_symbol(symbol)
        result = self.session.cancel_order(
            category="spot",
            symbol=formatted,
            orderId=str(actual_order_id)
        )
        if result['retCode'] != 0:
            raise Exception(f"Bybit cancel failed: {result['retMsg']}")
        return result['result']
    
    def close_position_market(self, symbol: str, quantity: float):
        """Close a spot position by selling at market"""
        try:
            precision = self.get_symbol_precision(symbol)
            truncated_qty = self.truncate(float(quantity) * 0.999, precision)
            
            result = self.place_order(
                symbol=symbol,
                side='Sell',
                type_='market',
                quantity=truncated_qty
            )
            return result
        except Exception as e:
            print(f"Bybit close_position_market error: {e}")
            raise
    
    def update_spot_tp_sl(self, symbol: str, quantity: float, new_tp: float, new_sl: float, user_id: int = None, old_tp: float = None, tp_order_id: str = None):
        """
        Update TP/SL for a spot position.
        tp_order_id: If provided, directly cancel this order ID (most accurate)
        old_tp: Fallback - used to identify the specific order to cancel by price
        Returns: new tp_order_id
        """
        import logging
        logger = logging.getLogger('bybit_adapter')
        
        try:
            formatted = self._format_symbol(symbol)
            
            # Cancel existing TP order
            if tp_order_id:
                logger.info(f"[BYBIT UPDATE_TP] Cancelling TP order by ID: {tp_order_id}")
                try:
                    self.cancel_order(symbol, tp_order_id)
                    logger.info(f"[BYBIT UPDATE_TP] Cancelled order {tp_order_id}")
                except Exception as e:
                    logger.warning(f"[BYBIT UPDATE_TP] Could not cancel order {tp_order_id}: {e}")
            elif old_tp:
                logger.info(f"[BYBIT UPDATE_TP] No tp_order_id, searching by price={old_tp}")
                open_orders = self.get_open_orders(symbol)
                for order in open_orders:
                    if order['side'].upper() == 'SELL':
                        order_price = float(order['price'])
                        if abs(order_price - float(old_tp)) < 0.01:
                            logger.info(f"[BYBIT UPDATE_TP] Found matching order {order['orderId']}, cancelling")
                            self.cancel_order(symbol, order['orderId'])
                            break
            
            # Place new TP limit order
            precision = self.get_symbol_precision(symbol)
            truncated_qty = self.truncate(float(quantity), precision)
            
            new_order = self.place_order(
                symbol=symbol,
                side='Sell',
                type_='limit',
                quantity=truncated_qty,
                price=new_tp
            )
            
            new_tp_order_id = str(new_order.get('orderId', ''))
            logger.info(f"[BYBIT UPDATE_TP] Created new TP order {new_tp_order_id} @ {new_tp}")
            
            return new_tp_order_id
            
        except Exception as e:
            print(f"Bybit update_spot_tp_sl error: {e}")
            raise
    
    def get_open_orders(self, symbol: str) -> list:
        """Get open orders for a symbol - normalized format"""
        try:
            formatted = self._format_symbol(symbol)
            result = self.session.get_open_orders(category="spot", symbol=formatted)
            if result['retCode'] == 0:
                orders = result['result'].get('list', [])
                return [
                    {
                        'side': o['side'].upper(),
                        'orderId': o['orderId'],
                        'origQty': float(o['qty']),
                        'price': float(o['price'])
                    }
                    for o in orders
                ]
            return []
        except Exception as e:
            print(f"Bybit get_open_orders error: {e}")
            return []
    
    def get_asset_balance_detail(self, asset: str) -> dict:
        """Get detailed balance - returns dict with 'free' and 'locked'"""
        try:
            result = self.session.get_wallet_balance(accountType="UNIFIED")
            if result['retCode'] == 0:
                coins = result['result']['list'][0].get('coin', [])
                for coin in coins:
                    if coin['coin'] == asset:
                        wallet = float(coin.get('walletBalance', 0))
                        locked = float(coin.get('locked', 0))
                        return {'free': wallet - locked, 'locked': locked}
            return {'free': 0.0, 'locked': 0.0}
        except Exception as e:
            print(f"Bybit get_asset_balance_detail error: {e}")
            return {'free': 0.0, 'locked': 0.0}
    
    def get_recent_trades(self, symbol: str, limit: int = 5) -> list:
        """Get recent trades - normalized format"""
        try:
            formatted = self._format_symbol(symbol)
            result = self.session.get_executions(category="spot", symbol=formatted, limit=limit)
            if result['retCode'] == 0:
                trades = result['result'].get('list', [])
                return [
                    {
                        'isBuyer': t['side'].lower() == 'buy',
                        'qty': float(t['execQty']),
                        'price': float(t['execPrice'])
                    }
                    for t in trades
                ]
            return []
        except Exception as e:
            print(f"Bybit get_recent_trades error: {e}")
            return []
    
    # === Wrapper methods for uniform interface ===
    
    def get_symbol_info(self, symbol: str) -> dict:
        """Get symbol info - normalized to Binance format"""
        try:
            formatted = self._format_symbol(symbol)
            result = self.session.get_instruments_info(category="spot", symbol=formatted)
            if result['retCode'] == 0 and result['result']['list']:
                info = result['result']['list'][0]
                # Normalize to Binance format
                return {
                    'symbol': symbol,
                    'status': 'TRADING' if info.get('status') == 'Trading' else info.get('status'),
                    'filters': [
                        {
                            'filterType': 'LOT_SIZE',
                            'stepSize': info.get('lotSizeFilter', {}).get('basePrecision', '0.00000001'),
                            'minQty': info.get('lotSizeFilter', {}).get('minOrderQty', '0.00000001'),
                        },
                        {
                            'filterType': 'PRICE_FILTER',
                            'tickSize': info.get('priceFilter', {}).get('tickSize', '0.01'),
                        },
                        {
                            'filterType': 'NOTIONAL',
                            'minNotional': info.get('lotSizeFilter', {}).get('minOrderAmt', '5'),
                        },
                        {
                            # Also add MIN_NOTIONAL for Binance scheduler compatibility
                            'filterType': 'MIN_NOTIONAL',
                            'minNotional': info.get('lotSizeFilter', {}).get('minOrderAmt', '5'),
                        }
                    ]
                }
            return {'symbol': symbol, 'filters': []}
        except Exception as e:
            print(f"Bybit get_symbol_info error: {e}")
            return {'symbol': symbol, 'filters': []}
    
    def get_all_tickers(self) -> list:
        """Get all tickers - normalized to Binance format"""
        try:
            result = self.session.get_tickers(category="spot")
            if result['retCode'] == 0:
                return [
                    {'symbol': t['symbol'], 'price': t['lastPrice']}
                    for t in result['result'].get('list', [])
                ]
            return []
        except Exception as e:
            print(f"Bybit get_all_tickers error: {e}")
            return []
    
    def get_account(self) -> dict:
        """Get account info - normalized to Binance format"""
        try:
            result = self.session.get_wallet_balance(accountType="UNIFIED")
            if result['retCode'] == 0:
                coins = result['result']['list'][0].get('coin', [])
                balances = []
                for c in coins:
                    wallet = c.get('walletBalance', '0') or '0'
                    locked = c.get('locked', '0') or '0'
                    free = str(float(wallet) - float(locked))
                    balances.append({'asset': c['coin'], 'free': free, 'locked': locked})
                return {'balances': balances}
            return {'balances': []}
        except Exception as e:
            print(f"Bybit get_account error: {e}")
            return {'balances': []}
    
    def get_asset_balance(self, asset: str) -> dict:
        """Get asset balance - returns dict with 'free' and 'locked'"""
        try:
            result = self.session.get_wallet_balance(accountType="UNIFIED")
            if result['retCode'] == 0:
                coins = result['result']['list'][0].get('coin', [])
                for coin in coins:
                    if coin['coin'] == asset:
                        wallet = float(coin.get('walletBalance', 0))
                        locked = float(coin.get('locked', 0))
                        return {'free': str(wallet - locked), 'locked': str(locked)}
            return {'free': '0', 'locked': '0'}
        except Exception as e:
            print(f"Bybit get_asset_balance error: {e}")
            return {'free': '0', 'locked': '0'}
    
    def order_market_buy(self, symbol: str, quantity: float) -> dict:
        """Place a market buy order"""
        return self.place_order(symbol=symbol, side='Buy', type_='market', quantity=quantity)
    
    def create_order(self, symbol: str, side: str, type: str, quantity: str, price: str = None, timeInForce: str = None, **kwargs) -> dict:
        """Create order - Binance-compatible signature"""
        order_type = "Market" if type.upper() == 'MARKET' else "Limit"
        order_side = side.capitalize()
        formatted_symbol = self._format_symbol(symbol)
        
        params = {
            "category": "spot",
            "symbol": formatted_symbol,
            "side": order_side,
            "orderType": order_type,
            "qty": str(quantity),
        }
        
        if order_type == "Limit" and price:
            # Format price according to tickSize
            try:
                instrument_info = self.session.get_instruments_info(category="spot", symbol=formatted_symbol)
                if instrument_info['retCode'] == 0 and instrument_info['result']['list']:
                    tick_size = instrument_info['result']['list'][0].get('priceFilter', {}).get('tickSize', '0.01')
                    # Count decimal places in tickSize
                    if '.' in tick_size:
                        decimals = len(tick_size.split('.')[1].rstrip('0'))
                    else:
                        decimals = 0
                    formatted_price = f"{float(price):.{decimals}f}"
                else:
                    formatted_price = str(price)
            except:
                formatted_price = str(price)
            
            params["price"] = formatted_price
            params["timeInForce"] = timeInForce or "GTC"
        
        result = self.session.place_order(**params)
        if result['retCode'] != 0:
            raise Exception(f"Bybit order failed: {result['retMsg']}")
        
        # Return in Binance-compatible format
        return {
            'orderId': result['result'].get('orderId'),
            'symbol': symbol,
            'side': side,
            'type': type,
            'origQty': quantity,
            'price': price,
            'status': 'NEW'
        }
    
    def get_symbol_ticker(self, symbol: str) -> dict:
        """Get symbol ticker - normalized to Binance format"""
        try:
            formatted = self._format_symbol(symbol)
            result = self.session.get_tickers(category="spot", symbol=formatted)
            if result['retCode'] == 0 and result['result']['list']:
                ticker = result['result']['list'][0]
                return {'symbol': symbol, 'price': ticker.get('lastPrice', '0')}
            return {'symbol': symbol, 'price': '0'}
        except Exception as e:
            print(f"Bybit get_symbol_ticker error: {e}")
            return {'symbol': symbol, 'price': '0'}
    
    def get_klines(self, symbol: str, interval: str, limit: int = 2) -> list:
        """Get klines/candlesticks - normalized to Binance format"""
        try:
            formatted = self._format_symbol(symbol)
            # Map Binance interval to Bybit interval
            interval_map = {
                '1m': '1', '3m': '3', '5m': '5', '15m': '15', '30m': '30',
                '1h': '60', '2h': '120', '4h': '240', '6h': '360', '12h': '720',
                '1d': 'D', '1w': 'W', '1M': 'M'
            }
            bybit_interval = interval_map.get(interval, '60')
            
            result = self.session.get_kline(
                category="spot",
                symbol=formatted,
                interval=bybit_interval,
                limit=limit
            )
            if result['retCode'] == 0:
                # Bybit returns [startTime, open, high, low, close, volume, turnover]
                # Binance returns [openTime, open, high, low, close, volume, closeTime, ...]
                klines = []
                for k in result['result'].get('list', []):
                    klines.append([
                        int(k[0]),  # openTime
                        k[1],       # open
                        k[2],       # high
                        k[3],       # low
                        k[4],       # close
                        k[5],       # volume
                        int(k[0]) + 60000,  # closeTime (estimated)
                        k[6],       # quoteAssetVolume
                        0,          # numberOfTrades
                        '0',        # takerBuyBaseAssetVolume
                        '0',        # takerBuyQuoteAssetVolume
                        '0'         # ignore
                    ])
                return klines
            return []
        except Exception as e:
            print(f"Bybit get_klines error: {e}")
            return []
