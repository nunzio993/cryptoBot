"""
Order Service - Business logic per ordini
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from models import SessionLocal, Order, Exchange
from api.services.exchange_service import ExchangeService
from src.core_and_scheduler import fetch_last_closed_candle


class OrderService:
    """Service per operazioni sugli ordini"""
    
    @staticmethod
    def create_order(
        user_id: int,
        symbol: str,
        quantity: float,
        entry_price: float,
        max_entry: float,
        take_profit: float,
        stop_loss: float,
        entry_interval: str,
        stop_interval: str,
        exchange_name: str = "binance",
        is_testnet: bool = False
    ) -> Order:
        """
        Crea un nuovo ordine.
        
        Per ordini Market, esegue immediatamente.
        Per ordini con interval, crea ordine PENDING.
        """
        # Validation
        if not (stop_loss < entry_price < take_profit):
            raise ValueError("Must be: Stop Loss < Entry Price < Take Profit")
        
        if max_entry < entry_price:
            raise ValueError("Max Entry must be >= Entry Price")
        
        # Get exchange ID
        exchange_id = ExchangeService.get_exchange_id(exchange_name)
        
        # Get adapter
        adapter = ExchangeService.get_adapter(user_id, exchange_name, is_testnet)
        
        is_market_order = entry_interval == "Market"
        
        # Check last candle for non-market orders
        if not is_market_order:
            try:
                last_close = float(fetch_last_closed_candle(symbol, entry_interval, adapter.client)[4])
                if last_close >= take_profit:
                    raise ValueError(
                        f"Previous {entry_interval} candle ({last_close:.2f}) >= TP; order not placed"
                    )
            except ValueError:
                raise
            except Exception:
                pass  # Allow order creation if candle check fails
        
        # Create order
        with SessionLocal() as session:
            order = Order(
                user_id=user_id,
                exchange_id=exchange_id,
                symbol=symbol,
                side="LONG",
                quantity=Decimal(str(quantity)),
                status="PENDING",
                entry_price=Decimal(str(entry_price)),
                max_entry=Decimal(str(max_entry)),
                take_profit=Decimal(str(take_profit)),
                stop_loss=Decimal(str(stop_loss)),
                entry_interval=entry_interval,
                stop_interval=stop_interval,
                created_at=datetime.now(timezone.utc),
                is_testnet=is_testnet
            )
            session.add(order)
            session.commit()
            session.refresh(order)
            
            # Execute immediately for Market orders
            if is_market_order:
                OrderService._execute_market_order(session, order, adapter)
            
            return order
    
    @staticmethod
    def _execute_market_order(session, order: Order, adapter) -> None:
        """Esegue un ordine market immediatamente"""
        try:
            # Get symbol info for precision
            symbol_info = adapter.client.get_symbol_info(order.symbol)
            filters = {f['filterType']: f for f in symbol_info['filters']}
            step_size = float(filters['LOT_SIZE']['stepSize'])
            
            # Round quantity
            precision = len(str(step_size).rstrip('0').split('.')[-1]) if '.' in str(step_size) else 0
            qty = round(float(order.quantity), precision)
            
            # Place market buy order
            market_order = adapter.client.order_market_buy(
                symbol=order.symbol,
                quantity=qty
            )
            
            # Get executed price
            executed_price = float(market_order.get('fills', [{}])[0].get('price', order.entry_price))
            
            # Update order
            order.status = "EXECUTED"
            order.executed_price = Decimal(str(executed_price))
            order.executed_at = datetime.now(timezone.utc)
            session.commit()
            
            # Set up TP/SL
            try:
                adapter.update_spot_tp_sl(
                    order.symbol,
                    qty,
                    float(order.take_profit),
                    float(order.stop_loss),
                    user_id=order.user_id
                )
            except Exception:
                pass  # TP/SL failed but order executed
                
        except Exception as e:
            order.status = "CANCELLED"
            order.closed_at = datetime.now(timezone.utc)
            session.commit()
            raise ValueError(f"Market order failed: {str(e)}")
    
    @staticmethod
    def cancel_order(order_id: int, user_id: int) -> dict:
        """Cancella un ordine PENDING"""
        with SessionLocal() as session:
            order = session.query(Order).filter(
                Order.id == order_id,
                Order.user_id == user_id
            ).first()
            
            if not order:
                raise ValueError("Order not found")
            
            if order.status != "PENDING":
                raise ValueError("Can only cancel PENDING orders")
            
            order.status = "CANCELLED"
            order.closed_at = datetime.now(timezone.utc)
            session.commit()
            
            return {"message": f"Order {order_id} cancelled"}
    
    @staticmethod
    def close_order(
        order_id: int, 
        user_id: int, 
        exchange_name: str = "binance",
        is_testnet: bool = False
    ) -> dict:
        """Chiude un ordine EXECUTED vendendo a mercato"""
        with SessionLocal() as session:
            order = session.query(Order).filter(
                Order.id == order_id,
                Order.user_id == user_id
            ).first()
            
            if not order:
                raise ValueError("Order not found")
            
            if order.status != "EXECUTED":
                raise ValueError("Can only close EXECUTED orders")
            
            adapter = ExchangeService.get_adapter(user_id, exchange_name, is_testnet)
            
            try:
                asset_name = order.symbol.replace("USDC", "")
                balance = adapter.get_balance(asset_name)
                
                symbol_info = adapter.client.get_symbol_info(order.symbol)
                filters = {f['filterType']: f for f in symbol_info['filters']}
                step_size = float(filters['LOT_SIZE']['stepSize'])
                
                if balance < step_size:
                    order.status = "CLOSED_EXTERNALLY"
                    order.closed_at = datetime.now(timezone.utc)
                    session.commit()
                    return {"message": "Balance too low, marked as externally closed"}
                
                qty_to_close = min(float(order.quantity), balance)
                adapter.close_position_market(order.symbol, qty_to_close)
                
                order.status = "CLOSED_MANUAL"
                order.closed_at = datetime.now(timezone.utc)
                session.commit()
                
                return {"message": f"Order {order_id} closed manually"}
                
            except Exception as e:
                raise ValueError(f"Failed to close order: {str(e)}")
