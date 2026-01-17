"""
WebSocket routes for real-time updates.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from jose import jwt, JWTError
import os
import logging
from api.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required. Set it in .env file.")
ALGORITHM = "HS256"


def verify_ws_token(token: str) -> dict:
    """Verify JWT token from WebSocket connection."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Token contains: sub=username, user_id=int
        user_id = payload.get("user_id")
        username = payload.get("sub")
        if user_id is None:
            raise ValueError("Invalid token: no user_id")
        return {"user_id": int(user_id), "username": username}
    except JWTError as e:
        logger.warning(f"WebSocket auth failed: {e}")
        raise ValueError("Invalid token")



@router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token for authentication")
):
    """
    WebSocket endpoint for real-time updates.
    
    Connect with: ws://localhost:8001/ws?token=<jwt_token>
    
    Events received:
    - order_update: When an order status changes
    - portfolio_update: When portfolio needs refresh
    - price_update: When a price changes (optional)
    """
    # Verify token before accepting connection
    try:
        user_data = verify_ws_token(token)
        user_id = user_data["user_id"]
    except ValueError as e:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return
    
    # Accept and register connection
    await manager.connect(websocket, user_id)
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "data": {"message": "Connected to CryptoBot real-time updates"}
        })
        
        # Keep connection alive and listen for messages
        while True:
            try:
                # Wait for any message (ping/pong or commands)
                data = await websocket.receive_text()
                
                # Handle ping
                if data == "ping":
                    await websocket.send_text("pong")
                
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
    finally:
        manager.disconnect(websocket, user_id)


@router.get("/status")
async def websocket_status():
    """Get WebSocket connection status (for debugging)."""
    connected_users = manager.get_connected_users()
    return {
        "active_users": len(connected_users),
        "connections": {
            user_id: manager.get_connection_count(user_id)
            for user_id in connected_users
        }
    }
