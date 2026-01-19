"""
Order Service - Business logic per ordini
"""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional
from models import SessionLocal, Order, Exchange
from api.services.exchange_service import ExchangeService
from src.core_and_scheduler import fetch_last_closed_candle
from src.trading_utils import format_quantity, format_price
from src.telegram_notifications import notify_open


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
    def _get_symbol_step_size(adapter, symbol: str) -> float:
        """Get step size for a symbol - works for all exchanges"""
        try:
            if hasattr(adapter, 'client') and hasattr(adapter.client, 'get_symbol_info'):
                # Binance
                symbol_info = adapter.get_symbol_info(symbol)
                if symbol_info:
                    filters = {f['filterType']: f for f in symbol_info['filters']}
                    return float(filters.get('LOT_SIZE', {}).get('stepSize', 0.00000001))
            elif hasattr(adapter, 'get_symbol_precision'):
                # Bybit/ccxt
                precision = adapter.get_symbol_precision(symbol)
                return 10 ** (-precision)
        except:
            pass
        return 0.00000001
    
    @staticmethod
    def _place_market_buy(adapter, symbol: str, quantity: float):
        """Place market buy - works for all exchanges"""
        if hasattr(adapter, 'client') and hasattr(adapter.client, 'order_market_buy'):
            # Binance
            qty_str = ('{:.8f}'.format(quantity)).rstrip('0').rstrip('.')
            return adapter.client.order_market_buy(symbol=symbol, quantity=qty_str)
        else:
            # Bybit/ccxt
            return adapter.place_order(symbol=symbol, side='BUY', type_='MARKET', quantity=quantity)
    
    @staticmethod
    def _execute_market_order(session, order: Order, adapter) -> None:
        """Esegue un ordine market immediatamente"""
        try:
            # Get step size using helper
            step_size = OrderService._get_symbol_step_size(adapter, order.symbol)
            
            # Round quantity
            precision = len(str(step_size).rstrip('0').split('.')[-1]) if '.' in str(step_size) else 0
            qty = round(float(order.quantity), precision)
            
            # Place market buy order using helper
            market_order = OrderService._place_market_buy(adapter, order.symbol, qty)
            
            # Get executed price (handle different response formats)
            if isinstance(market_order, dict):
                executed_price = float(
                    market_order.get('fills', [{}])[0].get('price', 0) or 
                    market_order.get('price', 0) or 
                    order.entry_price
                )
            else:
                executed_price = float(order.entry_price)
            
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
                # First cancel any open TP/SL orders for this symbol to unlock tokens
                try:
                    if hasattr(adapter, 'client') and hasattr(adapter.client, 'get_open_orders'):
                        # Binance
                        open_orders = adapter.client.get_open_orders(symbol=order.symbol)
                        for oo in open_orders:
                            if oo['side'] == 'SELL':  # TP orders are SELL
                                try:
                                    adapter.client.cancel_order(symbol=order.symbol, orderId=oo['orderId'])
                                except:
                                    pass
                    elif hasattr(adapter, 'cancel_all_orders'):
                        # Other exchanges
                        adapter.cancel_all_orders(order.symbol)
                except:
                    pass
                
                # Extract base asset correctly
                asset_name = order.symbol
                for quote in ['USDC', 'USDT']:
                    if asset_name.endswith(quote):
                        asset_name = asset_name[:-len(quote)]
                        break
                
                # Get free balance (works for all exchanges via adapter)
                free_balance = float(adapter.get_balance(asset_name) or 0)
                
                step_size = OrderService._get_symbol_step_size(adapter, order.symbol)
                
                if free_balance < step_size:
                    order.status = "CLOSED_EXTERNALLY"
                    order.closed_at = datetime.now(timezone.utc)
                    session.commit()
                    return {"message": "Balance too low, marked as externally closed"}
                
                qty_to_close = min(float(order.quantity), free_balance)
                adapter.close_position_market(order.symbol, qty_to_close)
                
                order.status = "CLOSED_MANUAL"
                order.closed_at = datetime.now(timezone.utc)
                session.commit()
                
                return {"message": f"Order {order_id} closed manually"}
                
            except Exception as e:
                raise ValueError(f"Failed to close order: {str(e)}")
    
    # ============= UTILITY METHODS =============
    
    @staticmethod
    def get_symbol_filters(adapter, symbol: str) -> dict:
        """
        Ottiene i filtri di trading per un simbolo (step_size, tick_size, min_qty, min_notional).
        Funziona sia per Binance che Bybit.
        """
        try:
            if hasattr(adapter, 'client') and hasattr(adapter.client, 'get_symbol_info'):
                # Binance
                symbol_info = adapter.get_symbol_info(symbol)
                if symbol_info:
                    filters = {f['filterType']: f for f in symbol_info['filters']}
                    return {
                        'step_size': float(filters.get('LOT_SIZE', {}).get('stepSize', '0.00000001')),
                        'tick_size': float(filters.get('PRICE_FILTER', {}).get('tickSize', '0.01')),
                        'min_qty': float(filters.get('LOT_SIZE', {}).get('minQty', '0.00001')),
                        'min_notional': float(filters.get('NOTIONAL', filters.get('MIN_NOTIONAL', {})).get('minNotional', '5')),
                    }
            elif hasattr(adapter, 'get_symbol_precision'):
                # Bybit
                precision = adapter.get_symbol_precision(symbol)
                return {
                    'step_size': 10 ** (-precision),
                    'tick_size': 0.01,
                    'min_qty': 10 ** (-precision),
                    'min_notional': 5.0,
                }
        except Exception:
            pass
        
        # Fallback
        return {
            'step_size': 0.00000001,
            'tick_size': 0.01,
            'min_qty': 0.00001,
            'min_notional': 5.0,
        }
    
    # format_quantity and format_price are imported from trading_utils
    # Re-export for backward compatibility
    format_quantity = staticmethod(format_quantity)
    format_price = staticmethod(format_price)
    
    @staticmethod
    def place_tp_limit_order(adapter, symbol: str, qty_str: str, price_str: str) -> str:
        """
        Piazza un ordine TP LIMIT sull'exchange.
        Returns: orderId come stringa
        """
        # Use place_order which works on both Binance and Bybit
        resp = adapter.place_order(
            symbol=symbol,
            side='SELL',
            type_='LIMIT',
            quantity=float(qty_str),
            price=float(price_str)
        )
        return str(resp.get('orderId', ''))
    
    @staticmethod
    def extract_base_asset(symbol: str) -> str:
        """Estrae l'asset base da un symbol (es. BTCUSDC -> BTC)"""
        for quote in ['USDC', 'USDT', 'BUSD']:
            if symbol.endswith(quote):
                return symbol[:-len(quote)]
        return symbol
    
    # ============= CREATE FROM HOLDING =============
    
    @staticmethod
    def create_from_holding(
        user_id: int,
        api_key_id: int,
        symbol: str,
        quantity: float,
        entry_price: float,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        stop_interval: str = "1h",
        db_session=None
    ) -> Order:
        """
        Crea un ordine EXECUTED da una posizione esterna (crypto già posseduta).
        Piazza automaticamente un ordine TP sull'exchange se take_profit è fornito.
        
        Args:
            user_id: ID dell'utente
            api_key_id: ID della API key da usare
            symbol: Simbolo (es. BTCUSDC)
            quantity: Quantità da gestire
            entry_price: Prezzo medio di acquisto
            take_profit: Prezzo TP (opzionale)
            stop_loss: Prezzo SL (opzionale)
            stop_interval: Intervallo per controllo SL
            db_session: Sessione DB esterna (opzionale)
            
        Returns:
            Order creato
        """
        # Get adapter from API key (ensures correct testnet flag)
        adapter, exchange_name, is_testnet, exchange_id = ExchangeService.get_adapter_by_key_id(
            user_id, api_key_id
        )
        
        # Get symbol filters
        filters = OrderService.get_symbol_filters(adapter, symbol)
        
        # Check actual balance
        base_asset = OrderService.extract_base_asset(symbol)
        free_balance = float(adapter.get_balance(base_asset) or 0)
        
        if free_balance < filters['min_qty']:
            raise ValueError(
                f"Insufficient {base_asset} balance. Have {free_balance:.8f}, need at least {filters['min_qty']}"
            )
        
        # Use smaller of requested or available quantity
        qty_to_use = min(quantity, free_balance)
        qty_str = OrderService.format_quantity(qty_to_use, filters['step_size'])
        
        if float(qty_str) < filters['min_qty']:
            raise ValueError(f"Quantity {qty_str} is below minimum {filters['min_qty']}")
        
        # Place TP order on exchange if take_profit provided
        tp_order_id = None
        tp_price_value = None
        
        if take_profit:
            price_str = OrderService.format_price(take_profit, filters['tick_size'])
            tp_price_value = float(price_str)
            
            # Check minimum notional
            order_value = float(qty_str) * float(price_str)
            if order_value < filters['min_notional']:
                raise ValueError(
                    f"Order value (${order_value:.2f}) below minimum (${filters['min_notional']}). "
                    "Increase quantity or TP price."
                )
            
            try:
                tp_order_id = OrderService.place_tp_limit_order(adapter, symbol, qty_str, price_str)
            except Exception as e:
                raise ValueError(f"Failed to place TP order: {str(e)}")
        
        # Create order in database
        session = db_session or SessionLocal()
        try:
            order = Order(
                user_id=user_id,
                exchange_id=exchange_id,
                symbol=symbol,
                side='BUY',
                quantity=float(qty_str),
                entry_price=entry_price,
                max_entry=entry_price,
                take_profit=tp_price_value,
                stop_loss=stop_loss,
                entry_interval="1m",
                stop_interval=stop_interval,
                status="EXECUTED",
                is_testnet=is_testnet,
                executed_price=entry_price,
                executed_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                tp_order_id=tp_order_id
            )
            session.add(order)
            session.commit()
            session.refresh(order)
            
            # Send Telegram notification for new tracked position
            try:
                notify_open(SimpleNamespace(
                    symbol=order.symbol,
                    quantity=float(order.quantity),
                    entry_price=float(order.entry_price),
                    user_id=user_id,
                    is_testnet=is_testnet
                ), exchange_name=exchange_name)
            except Exception:
                pass  # Notification is optional
            
            return order
        finally:
            if not db_session:
                session.close()
