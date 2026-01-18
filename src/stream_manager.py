"""
WebSocket Stream Manager for the trading bot.
Manages WebSocket connections for all users and exchanges.
Runs in a separate async thread alongside the blocking scheduler.
"""

import asyncio
import logging
import threading
from typing import Dict, Optional
from models import SessionLocal, APIKey, Exchange

logger = logging.getLogger('stream_manager')


class StreamManager:
    """
    Singleton manager for all exchange WebSocket streams.
    Runs async event loop in a background thread.
    """
    
    _instance: Optional['StreamManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.ws_manager = None
        self.running = False
    
    def _run_event_loop(self):
        """Run the async event loop in background thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_forever()
        finally:
            self.loop.close()
    
    def start(self):
        """Start the stream manager."""
        if self.running:
            return
            
        logger.info("[STREAM] Starting WebSocket Stream Manager...")
        
        # Start background thread for async operations
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        
        # Wait for loop to be ready
        import time
        while self.loop is None:
            time.sleep(0.01)
        
        # Initialize WebSocket manager
        from src.websocket_handlers import ExchangeWebSocketManager
        from src.order_event_handlers import handle_order_update
        
        self.ws_manager = ExchangeWebSocketManager(on_order_update=handle_order_update)
        self.running = True
        
        # Start streams for all users
        self._start_all_user_streams()
        
        logger.info("[STREAM] WebSocket Stream Manager started")
    
    def _start_all_user_streams(self):
        """Start WebSocket streams for all users with API keys."""
        with SessionLocal() as session:
            # Get all unique user/exchange combinations
            api_keys = session.query(APIKey).all()
            
            for key in api_keys:
                exchange = session.query(Exchange).filter_by(id=key.exchange_id).first()
                if not exchange:
                    continue
                    
                try:
                    self._start_stream_for_key(key, exchange.name)
                except Exception as e:
                    logger.error(f"[STREAM] Failed to start stream for user {key.user_id}: {e}")
    
    def _start_stream_for_key(self, api_key: APIKey, exchange_name: str):
        """Start WebSocket stream for a specific API key."""
        # Use the same approach as the scheduler which works
        from src.core_and_scheduler import get_exchange_adapter
        
        try:
            adapter = get_exchange_adapter(
                user_id=api_key.user_id,
                exchange_name=exchange_name,
                is_testnet=api_key.is_testnet
            )
        except Exception as e:
            logger.error(f"[STREAM] Failed to get adapter for user {api_key.user_id}: {e}")
            return
        
        if exchange_name.lower() == 'binance':
            # Use the client from the adapter
            client = adapter.client
            
            # Schedule async start on background loop
            future = asyncio.run_coroutine_threadsafe(
                self.ws_manager.start_binance_stream(
                    user_id=api_key.user_id,
                    exchange_id=api_key.exchange_id,
                    client=client,
                    testnet=api_key.is_testnet
                ),
                self.loop
            )
            # Don't wait for result to avoid blocking
            
        elif exchange_name.lower() == 'bybit':
            # For Bybit we need the raw keys, get them from adapter
            from src.crypto_utils import decrypt_api_key
            decrypted_key = decrypt_api_key(api_key.api_key, api_key.user_id)
            decrypted_secret = decrypt_api_key(api_key.secret_key, api_key.user_id)
            
            future = asyncio.run_coroutine_threadsafe(
                self.ws_manager.start_bybit_stream(
                    user_id=api_key.user_id,
                    exchange_id=api_key.exchange_id,
                    api_key=decrypted_key,
                    api_secret=decrypted_secret,
                    testnet=api_key.is_testnet
                ),
                self.loop
            )
    
    def start_stream_for_user(self, user_id: int, exchange_name: str, testnet: bool = False):
        """Start a stream for a specific user (called when new API key is added)."""
        if not self.running:
            return
            
        with SessionLocal() as session:
            exchange = session.query(Exchange).filter_by(name=exchange_name.lower()).first()
            if not exchange:
                return
                
            api_key = session.query(APIKey).filter_by(
                user_id=user_id,
                exchange_id=exchange.id,
                is_testnet=testnet
            ).first()
            
            if api_key:
                self._start_stream_for_key(api_key, exchange_name)
    
    def stop(self):
        """Stop all streams and the manager."""
        if not self.running:
            return
            
        logger.info("[STREAM] Stopping WebSocket Stream Manager...")
        
        if self.ws_manager and self.loop:
            future = asyncio.run_coroutine_threadsafe(
                self.ws_manager.stop_all(),
                self.loop
            )
            try:
                future.result(timeout=5)
            except:
                pass
        
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        if self.thread:
            self.thread.join(timeout=5)
        
        self.running = False
        logger.info("[STREAM] WebSocket Stream Manager stopped")


# Global stream manager instance
stream_manager = StreamManager()
