"""
Portfolio Service - Calcolo portfolio e P&L
"""
from datetime import datetime, timezone
from typing import List, Optional
from models import SessionLocal, Order, Exchange
from api.services.exchange_service import ExchangeService


class PortfolioService:
    """Service per calcolo portfolio e posizioni"""
    
    @staticmethod
    def get_portfolio(user_id: int, exchange_name: str = "binance", is_testnet: bool = False) -> dict:
        """
        Calcola il portfolio completo dell'utente.
        
        Returns:
            dict con: usdc_total, usdc_available, positions_value, portfolio_total, positions
        """
        with SessionLocal() as session:
            # Get exchange
            exchange = session.query(Exchange).filter_by(name=exchange_name.lower()).first()
            if not exchange:
                raise ValueError(f"Exchange '{exchange_name}' not found")
            
            # Get USDC balance
            try:
                balance = ExchangeService.get_balance(
                    user_id, "USDC", exchange_name, is_testnet
                )
                usdc_free = balance["free"]
                usdc_locked = balance["locked"]
                usdc_total = balance["total"]
            except Exception:
                usdc_free = 0
                usdc_locked = 0
                usdc_total = 0
            
            # Get pending orders (USDC blocked)
            pending_orders = session.query(Order).filter(
                Order.user_id == user_id,
                Order.status == "PENDING",
                Order.is_testnet == is_testnet
            ).all()
            
            usdc_blocked = sum(
                float(o.quantity or 0) * float(o.max_entry or 0) 
                for o in pending_orders
            )
            usdc_available = max(0, usdc_free - usdc_blocked)
            
            # Get executed orders (positions)
            executed_orders = session.query(Order).filter(
                Order.user_id == user_id,
                Order.status == "EXECUTED",
                Order.is_testnet == is_testnet
            ).all()
            
            positions = []
            positions_value = 0
            
            for order in executed_orders:
                position = PortfolioService._calculate_position(
                    order, exchange_name, is_testnet
                )
                if position:
                    positions.append(position)
                    positions_value += position["current_value"]
            
            portfolio_total = usdc_total + positions_value
            
            return {
                "usdc_total": usdc_total,
                "usdc_free": usdc_free,
                "usdc_locked": usdc_locked,
                "usdc_blocked": usdc_blocked,
                "usdc_available": usdc_available,
                "positions_value": positions_value,
                "portfolio_total": portfolio_total,
                "positions": positions
            }
    
    @staticmethod
    def _calculate_position(order: Order, exchange_name: str, is_testnet: bool) -> Optional[dict]:
        """Calcola P&L per una singola posizione"""
        try:
            current_price = ExchangeService.get_price(
                order.symbol, exchange_name, is_testnet
            )
        except Exception:
            current_price = float(order.executed_price or order.entry_price or 0)
        
        entry_price = float(order.executed_price or order.entry_price or 0)
        quantity = float(order.quantity or 0)
        current_value = quantity * current_price
        pnl = current_value - (quantity * entry_price)
        pnl_percent = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        
        return {
            "order_id": order.id,
            "symbol": order.symbol,
            "quantity": quantity,
            "entry_price": entry_price,
            "current_price": current_price,
            "current_value": current_value,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "take_profit": float(order.take_profit) if order.take_profit else None,
            "stop_loss": float(order.stop_loss) if order.stop_loss else None,
        }
