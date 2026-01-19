"""
Statistics API endpoint
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, timedelta
from decimal import Decimal

from models import SessionLocal, Order, BalanceHistory
from models import User
from api.deps import get_current_user

router = APIRouter()


class BalancePoint(BaseModel):
    date: str
    total: float


class StatisticsMetrics(BaseModel):
    current_balance: float
    all_time_profit: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float


class StatisticsResponse(BaseModel):
    metrics: StatisticsMetrics
    balance_history: List[BalancePoint]


@router.get("", response_model=StatisticsResponse)
async def get_statistics(
    days: int = Query(default=30, le=365, description="Days of history"),
    api_key_id: Optional[int] = Query(default=None, description="Filter by API key"),
    current_user: User = Depends(get_current_user)
):
    """
    Get user statistics and balance history.
    """
    with SessionLocal() as session:
        # Calculate metrics from closed orders
        closed_orders = session.query(Order).filter(
            Order.user_id == current_user.id,
            Order.status.in_(['CLOSED_TP', 'CLOSED_SL', 'CLOSED_MANUAL'])
        ).all()
        
        total_trades = len(closed_orders)
        winning_trades = len([o for o in closed_orders if o.status == 'CLOSED_TP'])
        losing_trades = len([o for o in closed_orders if o.status == 'CLOSED_SL'])
        
        # Calculate profit/loss
        all_time_profit = 0.0
        for order in closed_orders:
            entry = float(order.executed_price or order.entry_price or 0)
            qty = float(order.quantity or 0)
            
            if order.status == 'CLOSED_TP' and order.take_profit:
                # Profit = (TP - entry) * qty
                all_time_profit += (float(order.take_profit) - entry) * qty
            elif order.status == 'CLOSED_SL' and order.stop_loss:
                # Loss = (SL - entry) * qty (negative)
                all_time_profit += (float(order.stop_loss) - entry) * qty
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Get balance history
        since_date = date.today() - timedelta(days=days)
        history_query = session.query(BalanceHistory).filter(
            BalanceHistory.user_id == current_user.id,
            BalanceHistory.date >= since_date
        ).order_by(BalanceHistory.date.asc())
        
        if api_key_id:
            # Filter by specific API key (would need exchange_id and is_testnet)
            pass
        
        history = history_query.all()
        
        # Current balance from most recent entry
        current_balance = float(history[-1].total_balance) if history else 0.0
        
        balance_history = [
            BalancePoint(
                date=h.date.isoformat(),
                total=float(h.total_balance)
            )
            for h in history
        ]
        
        return StatisticsResponse(
            metrics=StatisticsMetrics(
                current_balance=current_balance,
                all_time_profit=round(all_time_profit, 2),
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=round(win_rate, 2)
            ),
            balance_history=balance_history
        )
