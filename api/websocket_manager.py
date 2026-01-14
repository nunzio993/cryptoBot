"""
WebSocket Connection Manager for real-time updates.
Handles multiple connections per user and broadcasts events.
"""
from typing import Dict, List
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for all users."""
    
    def __init__(self):
        # Dict of user_id -> list of active WebSocket connections
        self.active_connections: Dict[int, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Accept a new WebSocket connection for a user."""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        
        self.active_connections[user_id].append(websocket)
        logger.info(f"WebSocket connected for user {user_id}. Total connections: {len(self.active_connections[user_id])}")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove a WebSocket connection for a user."""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
                logger.info(f"WebSocket disconnected for user {user_id}. Remaining: {len(self.active_connections[user_id])}")
            
            # Clean up empty user entries
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
    async def send_personal_message(self, message: dict, user_id: int):
        """Send a message to a specific user (all their connections)."""
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send to user {user_id}: {e}")
                    disconnected.append(connection)
            
            # Clean up failed connections
            for conn in disconnected:
                self.disconnect(conn, user_id)
    
    async def broadcast_order_update(self, user_id: int, order_id: int, status: str, order_data: dict = None):
        """Broadcast an order status update to a user."""
        message = {
            "type": "order_update",
            "data": {
                "order_id": order_id,
                "status": status,
                "order": order_data
            }
        }
        await self.send_personal_message(message, user_id)
        logger.info(f"Broadcasted order update to user {user_id}: order {order_id} -> {status}")
    
    async def broadcast_portfolio_update(self, user_id: int):
        """Notify user to refresh their portfolio."""
        message = {
            "type": "portfolio_update",
            "data": {"refresh": True}
        }
        await self.send_personal_message(message, user_id)
        logger.info(f"Broadcasted portfolio update to user {user_id}")
    
    async def broadcast_price_update(self, user_id: int, symbol: str, price: float):
        """Broadcast a price update for a symbol."""
        message = {
            "type": "price_update",
            "data": {
                "symbol": symbol,
                "price": price
            }
        }
        await self.send_personal_message(message, user_id)
    
    def get_connected_users(self) -> List[int]:
        """Get list of all connected user IDs."""
        return list(self.active_connections.keys())
    
    def get_connection_count(self, user_id: int) -> int:
        """Get number of connections for a user."""
        return len(self.active_connections.get(user_id, []))


# Global instance
manager = ConnectionManager()
