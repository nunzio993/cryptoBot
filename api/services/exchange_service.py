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
            
            # IMPORTANT: Decrypt API keys before creating adapter
            from src.crypto_utils import decrypt_api_key
            decrypted_key = decrypt_api_key(api_key.api_key, user_id)
            decrypted_secret = decrypt_api_key(api_key.secret_key, user_id)
            
            return ExchangeFactory.create(
                exchange_name=exchange_name,
                api_key=decrypted_key,
                api_secret=decrypted_secret,
                testnet=is_testnet
            )
    
    @staticmethod
    def get_adapter_by_key_id(user_id: int, api_key_id: int) -> tuple:
        """
        Ottiene adapter e info dalla API key ID.
        Garantisce che is_testnet venga sempre dalla API key stessa.
        
        Returns:
            tuple: (adapter, exchange_name, is_testnet, exchange_id)
        """
        with SessionLocal() as session:
            api_key = session.query(APIKey).filter(
                APIKey.id == api_key_id,
                APIKey.user_id == user_id
            ).first()
            
            if not api_key:
                raise ValueError(f"API key {api_key_id} not found for user {user_id}")
            
            exchange = session.query(Exchange).filter_by(id=api_key.exchange_id).first()
            if not exchange:
                raise ValueError(f"Exchange not found for API key {api_key_id}")
            
            from src.crypto_utils import decrypt_api_key
            decrypted_key = decrypt_api_key(api_key.api_key, user_id)
            decrypted_secret = decrypt_api_key(api_key.secret_key, user_id)
            
            adapter = ExchangeFactory.create(
                exchange_name=exchange.name,
                api_key=decrypted_key,
                api_secret=decrypted_secret,
                testnet=api_key.is_testnet
            )
            
            return adapter, exchange.name, api_key.is_testnet, api_key.exchange_id
    
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
        
        # Use adapter method that works for all exchanges
        balance_info = adapter.get_asset_balance(asset)
        return {
            "asset": asset,
            "free": float(balance_info.get('free', 0)),
            "locked": float(balance_info.get('locked', 0)),
            "total": float(balance_info.get('free', 0)) + float(balance_info.get('locked', 0))
        }
    
    @staticmethod
    def get_price(user_id: int, symbol: str, exchange_name: str = "binance", is_testnet: bool = False) -> float:
        """Ottiene il prezzo corrente di un simbolo"""
        adapter = ExchangeService.get_adapter(user_id, exchange_name, is_testnet)
        return adapter.get_symbol_price(symbol)
    
    @staticmethod
    def get_symbols(quote_asset: str = "USDC", exchange_name: str = "binance") -> list:
        """Ottiene la lista dei simboli disponibili (public API, no auth needed)"""
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
        elif exchange_name.lower() == "bybit":
            from pybit.unified_trading import HTTP
            client = HTTP()
            response = client.get_instruments_info(category="spot")
            symbols = [
                {"symbol": s['symbol']}
                for s in response.get('result', {}).get('list', [])
                if s.get('quoteCoin') == quote_asset and s.get('status') == 'Trading'
            ]
            return sorted(symbols, key=lambda x: x['symbol'])
        else:
            raise NotImplementedError(f"get_symbols not implemented for {exchange_name}")
