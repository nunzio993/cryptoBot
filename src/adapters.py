from binance.client import Client as BinanceClient
import ccxt

class ExchangeAdapter:
    def get_balance(self, asset: str) -> float:
        raise NotImplementedError

    def place_order(self, symbol: str, side: str, type_: str, quantity: float, price: float = None):
        raise NotImplementedError

    def cancel_order(self, symbol: str, order_id):
        raise NotImplementedError

class BinanceAdapter(ExchangeAdapter):
    def __init__(self, api_key: str, secret_key: str, testnet: bool = True):
        self.client = BinanceClient(api_key, secret_key, testnet=testnet)

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

