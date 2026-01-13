"""
Exchange Service - Gestione adapters e operazioni exchange
"""
from typing import Optional
from models import SessionLocal, APIKey, Exchange
from src.exchange_factory import ExchangeFactory
from src.adapters import ExchangeAdapter


class ExchangeService:
    """Service per operazioni sugli exchange"""
    
    @staticmethod
    def get_adapter(
        user_id: int, 
        exchange_name: str = "binance", 
        is_testnet: bool = False
    ) -> ExchangeAdapter:
        """
        Ottiene un adapter configurato per l'utente e l'exchange specificati.
        
        Args:
            user_id: ID dell'utente
            exchange_name: Nome dell'exchange
            is_testnet: Se True, usa chiavi testnet
            
        Returns:
            ExchangeAdapter configurato
            
        Raises:
            ValueError: Se non trova le API keys
        """
        with SessionLocal() as session:
            exchange = session.query(Exchange).filter_by(name=exchange_name.lower()).first()
            if not exchange:
                raise ValueError(f"Exchange '{exchange_name}' not found in database")
            
            api_key = session.query(APIKey).filter_by(
                user_id=user_id,
                exchange_id=exchange.id,
                is_testnet=is_testnet
            ).first()
            
            if not api_key:
                network = "Testnet" if is_testnet else "Mainnet"
                raise ValueError(
                    f"No {network} API key found for user {user_id} on {exchange_name}"
                )
            
            return ExchangeFactory.create(
                exchange_name=exchange_name,
                api_key=api_key.api_key,
                api_secret=api_key.secret_key,
                testnet=is_testnet
            )
    
    @staticmethod
    def get_exchange_id(exchange_name: str = "binance") -> int:
        """Ottiene l'ID dell'exchange dal database"""
        with SessionLocal() as session:
            exchange = session.query(Exchange).filter_by(name=exchange_name.lower()).first()
            if not exchange:
                raise ValueError(f"Exchange '{exchange_name}' not found")
            return exchange.id
    
    @staticmethod
    def get_balance(user_id: int, asset: str, exchange_name: str = "binance", is_testnet: bool = False) -> dict:
        """Ottiene il saldo di un asset"""
        adapter = ExchangeService.get_adapter(user_id, exchange_name, is_testnet)
        
        if exchange_name.lower() == "binance":
            balance = adapter.client.get_asset_balance(asset=asset)
            return {
                "asset": asset,
                "free": float(balance['free']),
                "locked": float(balance['locked']),
                "total": float(balance['free']) + float(balance['locked'])
            }
        else:
            free = adapter.get_balance(asset)
            return {
                "asset": asset,
                "free": free,
                "locked": 0,
                "total": free
            }
    
    @staticmethod
    def get_price(symbol: str, exchange_name: str = "binance", is_testnet: bool = False) -> float:
        """Ottiene il prezzo corrente di un simbolo (usa API pubblica)"""
        if exchange_name.lower() == "binance":
            from binance.client import Client
            client = Client(testnet=is_testnet)
            ticker = client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        else:
            raise NotImplementedError(f"get_price not implemented for {exchange_name}")
    
    @staticmethod
    def get_symbols(quote_asset: str = "USDC", exchange_name: str = "binance") -> list:
        """Ottiene la lista dei simboli disponibili"""
        if exchange_name.lower() == "binance":
            from binance.client import Client
            client = Client()
            info = client.get_exchange_info()
            symbols = [
                {"symbol": s['symbol']}
                for s in info['symbols']
                if s['quoteAsset'] == quote_asset and s['status'] == 'TRADING'
            ]
            return sorted(symbols, key=lambda x: x['symbol'])
        else:
            raise NotImplementedError(f"get_symbols not implemented for {exchange_name}")
