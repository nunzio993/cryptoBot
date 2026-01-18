"""
WebSocket handlers for real-time exchange data streams.
Handles Binance User Data Stream and Bybit Private Stream for order updates.
"""

import asyncio
import json
import logging
import websockets
from typing import Callable, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger('websocket_handlers')


class BinanceUserDataStream:
    """
    Binance User Data Stream for real-time order updates.
    
    Events handled:
    - executionReport: Order updates (NEW, FILLED, CANCELED, etc.)
    """
    
    STREAM_URL = "wss://stream.binance.com:9443/ws/"
    TESTNET_STREAM_URL = "wss://testnet.binance.vision/ws/"
    KEEPALIVE_INTERVAL = 30 * 60  # 30 minutes
    
    def __init__(
        self,
        client,  # Binance client for listen key management
        on_order_update: Callable[[Dict], None],
        testnet: bool = False,
        user_id: int = None,
        exchange_id: int = None
    ):
        self.client = client
        self.on_order_update = on_order_update
        self.testnet = testnet
        self.user_id = user_id
        self.exchange_id = exchange_id
        self.listen_key: Optional[str] = None
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self._keepalive_task: Optional[asyncio.Task] = None
        self._stream_task: Optional[asyncio.Task] = None
        
    @property
    def stream_url(self) -> str:
        base = self.TESTNET_STREAM_URL if self.testnet else self.STREAM_URL
        return f"{base}{self.listen_key}"
    
    def _get_listen_key(self) -> str:
        """Create or get existing listen key."""
        try:
            response = self.client.stream_get_listen_key()
            return response
        except Exception as e:
            logger.error(f"[WS] Failed to get listen key: {e}")
            raise
    
    def _keepalive_listen_key(self):
        """Send keepalive ping for listen key."""
        try:
            self.client.stream_keepalive(self.listen_key)
            logger.debug(f"[WS] Listen key keepalive sent")
        except Exception as e:
            logger.warning(f"[WS] Listen key keepalive failed: {e}")
    
    def _close_listen_key(self):
        """Close listen key when done."""
        try:
            if self.listen_key:
                self.client.stream_close(self.listen_key)
                logger.info(f"[WS] Listen key closed")
        except Exception as e:
            logger.warning(f"[WS] Failed to close listen key: {e}")
    
    async def _keepalive_loop(self):
        """Send keepalive every 30 minutes."""
        while self.running:
            await asyncio.sleep(self.KEEPALIVE_INTERVAL)
            if self.running:
                self._keepalive_listen_key()
    
    async def _handle_message(self, message: str):
        """Process incoming WebSocket message."""
        try:
            data = json.loads(message)
            event_type = data.get('e')
            
            if event_type == 'executionReport':
                await self._handle_execution_report(data)
            elif event_type == 'outboundAccountPosition':
                # Balance update - could be useful for future features
                pass
            elif event_type == 'listenKeyExpired':
                logger.warning("[WS] Listen key expired, reconnecting...")
                await self._reconnect()
            else:
                logger.debug(f"[WS] Unhandled event type: {event_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"[WS] Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"[WS] Error handling message: {e}")
    
    async def _handle_execution_report(self, data: Dict):
        """
        Handle executionReport event (order update).
        
        Key fields:
        - s: Symbol (e.g., BNBUSDC)
        - i: Order ID
        - X: Current order status (NEW, FILLED, CANCELED, etc.)
        - x: Execution type (NEW, TRADE, CANCELED, etc.)
        - S: Side (BUY, SELL)
        - o: Order type (LIMIT, MARKET, etc.)
        - q: Original quantity
        - p: Price
        - z: Cumulative filled quantity
        """
        order_id = str(data.get('i'))
        symbol = data.get('s')
        status = data.get('X')
        exec_type = data.get('x')
        side = data.get('S')
        
        logger.info(f"[WS] Order update: {symbol} #{order_id} {side} status={status} exec={exec_type}")
        
        # Call the handler with enriched data
        event = {
            'type': 'order_update',
            'exchange': 'binance',
            'order_id': order_id,
            'symbol': symbol,
            'status': status,
            'execution_type': exec_type,
            'side': side,
            'price': data.get('p'),
            'quantity': data.get('q'),
            'filled_quantity': data.get('z'),
            'user_id': self.user_id,
            'exchange_id': self.exchange_id,
            'testnet': self.testnet,
            'raw': data
        }
        
        try:
            await self.on_order_update(event)
        except Exception as e:
            logger.error(f"[WS] Error in order update handler: {e}")
    
    async def _stream_loop(self):
        """Main WebSocket stream loop with auto-reconnect."""
        retry_delay = 1
        max_retry_delay = 60
        
        while self.running:
            try:
                logger.info(f"[WS] Connecting to Binance stream...")
                
                async with websockets.connect(self.stream_url) as ws:
                    self.ws = ws
                    retry_delay = 1  # Reset on successful connect
                    logger.info(f"[WS] Connected to Binance User Data Stream")
                    
                    async for message in ws:
                        if not self.running:
                            break
                        await self._handle_message(message)
                        
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"[WS] Connection closed: {e}")
            except Exception as e:
                logger.error(f"[WS] Stream error: {e}")
            
            if self.running:
                logger.info(f"[WS] Reconnecting in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
                
                # Get new listen key on reconnect
                try:
                    self.listen_key = self._get_listen_key()
                except Exception:
                    pass
    
    async def _reconnect(self):
        """Force reconnect by closing current connection."""
        if self.ws:
            await self.ws.close()
    
    async def start(self):
        """Start the WebSocket stream."""
        if self.running:
            return
            
        self.running = True
        self.listen_key = self._get_listen_key()
        
        # Start keepalive task
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())
        
        # Start stream task
        self._stream_task = asyncio.create_task(self._stream_loop())
        
        logger.info(f"[WS] Binance User Data Stream started (testnet={self.testnet})")
    
    async def stop(self):
        """Stop the WebSocket stream."""
        self.running = False
        
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
        
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
        
        if self.ws:
            await self.ws.close()
        
        self._close_listen_key()
        logger.info(f"[WS] Binance User Data Stream stopped")


class BybitPrivateStream:
    """
    Bybit Private Stream for real-time order updates.
    
    Topics:
    - order: Order updates
    """
    
    STREAM_URL = "wss://stream.bybit.com/v5/private"
    TESTNET_STREAM_URL = "wss://stream-testnet.bybit.com/v5/private"
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        on_order_update: Callable[[Dict], None],
        testnet: bool = False,
        user_id: int = None,
        exchange_id: int = None
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.on_order_update = on_order_update
        self.testnet = testnet
        self.user_id = user_id
        self.exchange_id = exchange_id
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self._stream_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
    
    @property  
    def stream_url(self) -> str:
        return self.TESTNET_STREAM_URL if self.testnet else self.STREAM_URL
    
    def _generate_signature(self, expires: int) -> str:
        """Generate authentication signature."""
        import hmac
        import hashlib
        
        val = f"GET/realtime{expires}"
        return hmac.new(
            self.api_secret.encode('utf-8'),
            val.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _authenticate(self, ws):
        """Send authentication message."""
        import time
        
        expires = int((time.time() + 10) * 1000)
        signature = self._generate_signature(expires)
        
        auth_msg = {
            "op": "auth",
            "args": [self.api_key, expires, signature]
        }
        
        await ws.send(json.dumps(auth_msg))
        response = await ws.recv()
        data = json.loads(response)
        
        if data.get('success'):
            logger.info("[WS] Bybit authentication successful")
            return True
        else:
            logger.error(f"[WS] Bybit authentication failed: {data}")
            return False
    
    async def _subscribe(self, ws):
        """Subscribe to order topic."""
        sub_msg = {
            "op": "subscribe",
            "args": ["order.spot"]
        }
        await ws.send(json.dumps(sub_msg))
        logger.info("[WS] Subscribed to Bybit order topic")
    
    async def _ping_loop(self):
        """Send ping every 20 seconds to keep connection alive."""
        while self.running:
            await asyncio.sleep(20)
            if self.ws and self.running:
                try:
                    await self.ws.send(json.dumps({"op": "ping"}))
                except Exception as e:
                    logger.warning(f"[WS] Bybit ping failed: {e}")
    
    async def _handle_message(self, message: str):
        """Process incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            # Handle pong
            if data.get('op') == 'pong':
                return
            
            # Handle order updates
            topic = data.get('topic')
            if topic and topic.startswith('order'):
                for order_data in data.get('data', []):
                    await self._handle_order_update(order_data)
                    
        except json.JSONDecodeError as e:
            logger.error(f"[WS] Failed to parse Bybit message: {e}")
        except Exception as e:
            logger.error(f"[WS] Error handling Bybit message: {e}")
    
    async def _handle_order_update(self, data: Dict):
        """Handle order update from Bybit."""
        order_id = data.get('orderId')
        symbol = data.get('symbol')
        status = data.get('orderStatus')
        side = data.get('side')
        
        logger.info(f"[WS] Bybit order update: {symbol} #{order_id} {side} status={status}")
        
        # Map Bybit status to common format
        status_map = {
            'New': 'NEW',
            'PartiallyFilled': 'PARTIALLY_FILLED',
            'Filled': 'FILLED',
            'Cancelled': 'CANCELED',
            'Rejected': 'REJECTED'
        }
        
        event = {
            'type': 'order_update',
            'exchange': 'bybit',
            'order_id': order_id,
            'symbol': symbol,
            'status': status_map.get(status, status),
            'side': side.upper() if side else None,
            'price': data.get('price'),
            'quantity': data.get('qty'),
            'filled_quantity': data.get('cumExecQty'),
            'user_id': self.user_id,
            'exchange_id': self.exchange_id,
            'testnet': self.testnet,
            'raw': data
        }
        
        try:
            await self.on_order_update(event)
        except Exception as e:
            logger.error(f"[WS] Error in Bybit order update handler: {e}")
    
    async def _stream_loop(self):
        """Main WebSocket stream loop with auto-reconnect."""
        retry_delay = 1
        max_retry_delay = 60
        
        while self.running:
            try:
                logger.info(f"[WS] Connecting to Bybit stream...")
                
                async with websockets.connect(self.stream_url) as ws:
                    self.ws = ws
                    
                    # Authenticate
                    if not await self._authenticate(ws):
                        await asyncio.sleep(retry_delay)
                        continue
                    
                    # Subscribe to topics
                    await self._subscribe(ws)
                    
                    retry_delay = 1  # Reset on successful connect
                    logger.info(f"[WS] Connected to Bybit Private Stream")
                    
                    async for message in ws:
                        if not self.running:
                            break
                        await self._handle_message(message)
                        
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"[WS] Bybit connection closed: {e}")
            except Exception as e:
                logger.error(f"[WS] Bybit stream error: {e}")
            
            if self.running:
                logger.info(f"[WS] Bybit reconnecting in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
    
    async def start(self):
        """Start the WebSocket stream."""
        if self.running:
            return
            
        self.running = True
        
        # Start ping task
        self._ping_task = asyncio.create_task(self._ping_loop())
        
        # Start stream task
        self._stream_task = asyncio.create_task(self._stream_loop())
        
        logger.info(f"[WS] Bybit Private Stream started (testnet={self.testnet})")
    
    async def stop(self):
        """Stop the WebSocket stream."""
        self.running = False
        
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
        
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
        
        if self.ws:
            await self.ws.close()
        
        logger.info(f"[WS] Bybit Private Stream stopped")


class ExchangeWebSocketManager:
    """
    Manages WebSocket connections for multiple users and exchanges.
    """
    
    def __init__(self, on_order_update: Callable[[Dict], None]):
        self.on_order_update = on_order_update
        self.streams: Dict[str, any] = {}  # key: "{user_id}_{exchange}_{testnet}"
    
    def _stream_key(self, user_id: int, exchange: str, testnet: bool) -> str:
        return f"{user_id}_{exchange}_{testnet}"
    
    async def start_binance_stream(
        self,
        user_id: int,
        exchange_id: int,
        client,
        testnet: bool = False
    ):
        """Start Binance WebSocket for a user."""
        key = self._stream_key(user_id, 'binance', testnet)
        
        if key in self.streams:
            logger.info(f"[WS] Binance stream already running for {key}")
            return
        
        stream = BinanceUserDataStream(
            client=client,
            on_order_update=self.on_order_update,
            testnet=testnet,
            user_id=user_id,
            exchange_id=exchange_id
        )
        
        self.streams[key] = stream
        await stream.start()
    
    async def start_bybit_stream(
        self,
        user_id: int,
        exchange_id: int,
        api_key: str,
        api_secret: str,
        testnet: bool = False
    ):
        """Start Bybit WebSocket for a user."""
        key = self._stream_key(user_id, 'bybit', testnet)
        
        if key in self.streams:
            logger.info(f"[WS] Bybit stream already running for {key}")
            return
        
        stream = BybitPrivateStream(
            api_key=api_key,
            api_secret=api_secret,
            on_order_update=self.on_order_update,
            testnet=testnet,
            user_id=user_id,
            exchange_id=exchange_id
        )
        
        self.streams[key] = stream
        await stream.start()
    
    async def stop_stream(self, user_id: int, exchange: str, testnet: bool):
        """Stop a specific stream."""
        key = self._stream_key(user_id, exchange, testnet)
        
        if key in self.streams:
            await self.streams[key].stop()
            del self.streams[key]
    
    async def stop_all(self):
        """Stop all streams."""
        for key, stream in list(self.streams.items()):
            await stream.stop()
        self.streams.clear()
        logger.info("[WS] All streams stopped")
