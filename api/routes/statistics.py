"""
Statistics API endpoint
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, timedelta
from decimal import Decimal

from models import SessionLocal, Order, BalanceHistory, APIKey
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
    If api_key_id is provided, filter by that exchange. Otherwise, aggregate all.
    """
    with SessionLocal() as session:
        # Get exchange_id and is_testnet from api_key if provided
        exchange_id = None
        is_testnet = None
        if api_key_id:
            api_key = session.query(APIKey).filter(
                APIKey.id == api_key_id,
                APIKey.user_id == current_user.id
            ).first()
            if api_key:
                exchange_id = api_key.exchange_id
                is_testnet = api_key.is_testnet
        
        # Build order query with filters
        order_query = session.query(Order).filter(
            Order.user_id == current_user.id,
            Order.status.in_(['CLOSED_TP', 'CLOSED_SL', 'CLOSED_MANUAL'])
        )
        if exchange_id is not None:
            order_query = order_query.filter(Order.exchange_id == exchange_id)
        if is_testnet is not None:
            order_query = order_query.filter(Order.is_testnet == is_testnet)
        else:
            # Default to mainnet only when "All Exchanges" is selected
            order_query = order_query.filter(Order.is_testnet == False)
        
        closed_orders = order_query.all()
        
        total_trades = len(closed_orders)
        winning_trades = len([o for o in closed_orders if o.status == 'CLOSED_TP'])
        losing_trades = len([o for o in closed_orders if o.status == 'CLOSED_SL'])
        
        # Calculate profit/loss
        all_time_profit = 0.0
        for order in closed_orders:
            entry = float(order.executed_price or order.entry_price or 0)
            qty = float(order.quantity or 0)
            
            if order.status == 'CLOSED_TP' and order.take_profit:
                all_time_profit += (float(order.take_profit) - entry) * qty
            elif order.status == 'CLOSED_SL' and order.stop_loss:
                all_time_profit += (float(order.stop_loss) - entry) * qty
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Build balance history query with filters
        since_date = date.today() - timedelta(days=days)
        history_query = session.query(BalanceHistory).filter(
            BalanceHistory.user_id == current_user.id,
            BalanceHistory.date >= since_date
        )
        if exchange_id is not None:
            history_query = history_query.filter(BalanceHistory.exchange_id == exchange_id)
        if is_testnet is not None:
            history_query = history_query.filter(BalanceHistory.is_testnet == is_testnet)
        else:
            # Default to mainnet only when "All Exchanges" is selected
            history_query = history_query.filter(BalanceHistory.is_testnet == False)
        
        history_query = history_query.order_by(BalanceHistory.date.asc())
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
