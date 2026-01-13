"""
Exchange Factory - Factory pattern per creare adapters multi-exchange
"""
from typing import Optional
from src.adapters import BinanceAdapter, BybitAdapter, ExchangeAdapter


class ExchangeFactory:
    """Factory per creare exchange adapters in modo centralizzato"""
    
    SUPPORTED_EXCHANGES = ["binance", "bybit"]
    
    @staticmethod
    def create(
        exchange_name: str, 
        api_key: str, 
        api_secret: str, 
        testnet: bool = False
    ) -> ExchangeAdapter:
        """
        Crea un adapter per l'exchange specificato.
        
        Args:
            exchange_name: Nome dell'exchange (binance, bybit, etc.)
            api_key: API key
            api_secret: API secret
            testnet: Se True, usa l'ambiente testnet
            
        Returns:
            ExchangeAdapter: Adapter configurato per l'exchange
            
        Raises:
            ValueError: Se l'exchange non è supportato
        """
        exchange_name = exchange_name.lower()
        
        if exchange_name == "binance":
            return BinanceAdapter(api_key, api_secret, testnet=testnet)
        elif exchange_name == "bybit":
            # Bybit adapter - TODO: aggiungere supporto testnet
            return BybitAdapter(api_key, api_secret)
        else:
            raise ValueError(
                f"Exchange '{exchange_name}' not supported. "
                f"Supported: {ExchangeFactory.SUPPORTED_EXCHANGES}"
            )
    
    @staticmethod
    def get_supported_exchanges() -> list:
        """Ritorna la lista degli exchange supportati"""
        return ExchangeFactory.SUPPORTED_EXCHANGES.copy()
    
    @staticmethod
    def is_supported(exchange_name: str) -> bool:
        """Verifica se un exchange è supportato"""
        return exchange_name.lower() in ExchangeFactory.SUPPORTED_EXCHANGES
