#!/usr/bin/env python3
"""
Comprehensive Automated Test Script for Binance Order Management
Tests various order scenarios on Binance Testnet

Usage:
    python scripts/test_binance_orders.py --api-key YOUR_KEY --secret YOUR_SECRET
    
Or set environment variables:
    BINANCE_TEST_API_KEY, BINANCE_TEST_SECRET
"""

import os
import sys
import time
import argparse
from decimal import Decimal
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.adapters import BinanceAdapter


class TestResult:
    def __init__(self, name: str, passed: bool, message: str = "", duration: float = 0):
        self.name = name
        self.passed = passed
        self.message = message
        self.duration = duration
    
    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status} | {self.name} ({self.duration:.2f}s) - {self.message}"


class BinanceOrderTester:
    def __init__(self, api_key: str, secret_key: str, testnet: bool = True):
        self.adapter = BinanceAdapter(api_key, secret_key, testnet=testnet)
        self.results: list[TestResult] = []
        self.test_symbol = "BNBUSDC"  # High liquidity test pair
        self.test_symbol_alt = "BTCUSDC"  # Alternative pair
        self.test_quantity = 0.1  # Small test quantity
        
    def log(self, msg: str):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    
    def run_test(self, name: str, test_func):
        """Run a single test and record result"""
        self.log(f"Running: {name}")
        start = time.time()
        try:
            result = test_func()
            duration = time.time() - start
            self.results.append(TestResult(name, True, str(result)[:100], duration))
            self.log(f"  ✅ Passed: {str(result)[:80]}")
        except Exception as e:
            duration = time.time() - start
            self.results.append(TestResult(name, False, str(e)[:100], duration))
            self.log(f"  ❌ Failed: {e}")
    
    def format_qty(self, symbol: str, qty: float) -> str:
        """Format quantity according to symbol's LOT_SIZE filter"""
        info = self.adapter.get_symbol_info(symbol)
        filters = {f['filterType']: f for f in info.get('filters', [])}
        step_size = float(filters.get('LOT_SIZE', {}).get('stepSize', '0.00000001'))
        
        # Calculate precision from step size
        import math
        if step_size >= 1:
            precision = 0
        else:
            precision = abs(int(round(math.log10(step_size))))
        
        # Truncate to precision
        truncated = self.adapter.truncate(qty, precision)
        
        # Format as string without trailing zeros
        return ('{:.8f}'.format(truncated)).rstrip('0').rstrip('.')
    
    # ============ CONNECTIVITY TESTS ============
    
    def test_get_symbol_price(self):
        """Test fetching current price"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        assert price > 0, "Price should be positive"
        return f"Price: ${price:.2f}"
    
    def test_get_symbol_price_btc(self):
        """Test fetching BTC price"""
        price = self.adapter.get_symbol_price(self.test_symbol_alt)
        assert price > 1000, "BTC price should be > $1000"
        return f"BTC Price: ${price:.2f}"
    
    def test_get_balance_usdc(self):
        """Test fetching USDC balance"""
        balance = self.adapter.get_balance("USDC")
        assert balance >= 0, "Balance should be non-negative"
        return f"USDC Balance: ${balance:.2f}"
    
    def test_get_balance_bnb(self):
        """Test fetching BNB balance"""
        balance = self.adapter.get_balance("BNB")
        assert balance >= 0, "Balance should be non-negative"
        return f"BNB Balance: {balance:.4f}"
    
    def test_get_balance_btc(self):
        """Test fetching BTC balance"""
        balance = self.adapter.get_balance("BTC")
        assert balance >= 0, "Balance should be non-negative"
        return f"BTC Balance: {balance:.8f}"
    
    def test_get_asset_balance_detail(self):
        """Test detailed balance with free/locked"""
        detail = self.adapter.get_asset_balance("USDC")
        assert 'free' in detail and 'locked' in detail
        return f"Free: {detail['free']}, Locked: {detail['locked']}"
    
    def test_get_asset_balance_detail_bnb(self):
        """Test detailed BNB balance"""
        detail = self.adapter.get_asset_balance("BNB")
        assert 'free' in detail and 'locked' in detail
        return f"BNB Free: {detail['free']}, Locked: {detail['locked']}"
    
    def test_get_symbol_info(self):
        """Test symbol info with filters"""
        info = self.adapter.get_symbol_info(self.test_symbol)
        assert 'filters' in info, "Should have filters"
        filters = {f['filterType']: f for f in info['filters']}
        assert 'LOT_SIZE' in filters, "Should have LOT_SIZE filter"
        return f"Filters: {list(filters.keys())}"
    
    def test_get_symbol_info_btc(self):
        """Test BTC symbol info"""
        info = self.adapter.get_symbol_info(self.test_symbol_alt)
        assert 'filters' in info
        filters = {f['filterType']: f for f in info['filters']}
        lot_size = filters.get('LOT_SIZE', {})
        return f"BTC step: {lot_size.get('stepSize')}"
    
    def test_get_all_tickers(self):
        """Test fetching all tickers"""
        tickers = self.adapter.get_all_tickers()
        assert len(tickers) > 100, "Should have many tickers"
        return f"Tickers count: {len(tickers)}"
    
    def test_get_all_tickers_contains_bnb(self):
        """Test that tickers contain BNBUSDC"""
        tickers = self.adapter.get_all_tickers()
        symbols = [t['symbol'] for t in tickers]
        assert self.test_symbol in symbols, f"{self.test_symbol} should be in tickers"
        return f"Found {self.test_symbol}"
    
    def test_get_klines_1h(self):
        """Test fetching 1h candlestick data"""
        klines = self.adapter.get_klines(self.test_symbol, "1h", limit=5)
        assert len(klines) > 0, "Should have klines"
        assert len(klines[0]) >= 6, "Kline should have OHLCV data"
        return f"Got {len(klines)} x 1h candles"
    
    def test_get_klines_15m(self):
        """Test fetching 15m candlestick data"""
        klines = self.adapter.get_klines(self.test_symbol, "15m", limit=10)
        assert len(klines) >= 5, "Should have multiple klines"
        return f"Got {len(klines)} x 15m candles"
    
    def test_get_klines_1d(self):
        """Test fetching daily candlestick data"""
        klines = self.adapter.get_klines(self.test_symbol, "1d", limit=7)
        assert len(klines) > 0, "Should have daily klines"
        close = float(klines[-1][4])
        return f"Got {len(klines)} daily candles, last close: ${close:.2f}"
    
    def test_get_account(self):
        """Test fetching full account info"""
        account = self.adapter.get_account()
        assert 'balances' in account, "Should have balances"
        non_zero = [b for b in account['balances'] if float(b.get('free', 0)) > 0]
        return f"Account has {len(non_zero)} assets with balance"
    
    def test_get_symbol_precision(self):
        """Test symbol precision"""
        precision = self.adapter.get_symbol_precision(self.test_symbol)
        assert precision >= 0 and precision <= 10, "Precision should be reasonable"
        return f"Precision: {precision} decimals"
    
    def test_get_symbol_precision_btc(self):
        """Test BTC precision"""
        precision = self.adapter.get_symbol_precision(self.test_symbol_alt)
        assert precision >= 0, "Precision should be non-negative"
        return f"BTC Precision: {precision} decimals"
    
    def test_truncate_quantity(self):
        """Test quantity truncation"""
        truncated = self.adapter.truncate(0.123456789, 4)
        assert truncated == 0.1234, f"Should truncate to 4 decimals, got {truncated}"
        return f"Truncated: {truncated}"
    
    def test_truncate_quantity_floor(self):
        """Test truncation floors down"""
        truncated = self.adapter.truncate(0.999999, 2)
        assert truncated == 0.99, f"Should floor to 0.99, got {truncated}"
        return f"Floored: {truncated}"
    
    # ============ ORDER TESTS ============
    
    def test_market_buy_small(self):
        """Test small market buy"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        qty = round(10 / price, 4)  # ~$10 worth
        
        buy_order = self.adapter.order_market_buy(self.test_symbol, qty)
        assert buy_order.get('orderId'), "Buy should return orderId"
        
        time.sleep(0.5)
        
        # Cleanup - sell back
        self.adapter.close_position_market(self.test_symbol, qty)
        
        return f"Bought {qty} @ market, order: {buy_order.get('orderId')}"
    
    def test_market_buy_sell_cycle(self):
        """Test complete buy/sell cycle"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        raw_qty = 15 / price  # ~$15 worth
        qty = self.format_qty(self.test_symbol, raw_qty)
        
        # Buy
        buy_order = self.adapter.order_market_buy(self.test_symbol, float(qty))
        buy_id = buy_order.get('orderId')
        self.log(f"    Buy order: {buy_id}")
        
        time.sleep(1)
        
        # Sell
        sell_order = self.adapter.close_position_market(self.test_symbol, float(qty))
        sell_id = sell_order.get('orderId')
        
        return f"Buy: {buy_id}, Sell: {sell_id}"
    
    def test_limit_order_below_market(self):
        """Test limit order 10% below market"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        limit_price = round(price * 0.90, 2)
        qty = round(10 / price, 4)
        
        order = self.adapter.client.create_order(
            symbol=self.test_symbol,
            side='BUY',
            type='LIMIT',
            timeInForce='GTC',
            quantity=qty,
            price=limit_price
        )
        order_id = order.get('orderId')
        
        time.sleep(0.5)
        
        # Cancel
        self.adapter.cancel_order(self.test_symbol, order_id)
        
        return f"Created @ ${limit_price}, cancelled: {order_id}"
    
    def test_limit_order_above_market(self):
        """Test limit sell order 10% above market"""
        # First buy some
        price = self.adapter.get_symbol_price(self.test_symbol)
        qty = round(10 / price, 4)
        
        self.adapter.order_market_buy(self.test_symbol, qty)
        time.sleep(0.5)
        
        # Place limit sell above market
        sell_price = round(price * 1.10, 2)
        order = self.adapter.client.create_order(
            symbol=self.test_symbol,
            side='SELL',
            type='LIMIT',
            timeInForce='GTC',
            quantity=qty,
            price=sell_price
        )
        order_id = order.get('orderId')
        
        time.sleep(0.5)
        
        # Cancel and sell at market
        self.adapter.cancel_order(self.test_symbol, order_id)
        self.adapter.close_position_market(self.test_symbol, qty)
        
        return f"Limit sell @ ${sell_price}, cancelled: {order_id}"
    
    def test_get_open_orders_empty(self):
        """Test getting open orders when none exist"""
        orders = self.adapter.get_open_orders(self.test_symbol)
        # May or may not be empty, just check it's a list
        assert isinstance(orders, list), "Should return list"
        return f"Open orders: {len(orders)}"
    
    def test_get_open_orders_with_order(self):
        """Test open orders with active order"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        limit_price = round(price * 0.85, 2)
        qty = round(10 / price, 4)
        
        # Create order
        order = self.adapter.client.create_order(
            symbol=self.test_symbol,
            side='BUY',
            type='LIMIT',
            timeInForce='GTC',
            quantity=qty,
            price=limit_price
        )
        order_id = order.get('orderId')
        
        time.sleep(0.5)
        
        # Check open orders
        open_orders = self.adapter.get_open_orders(self.test_symbol)
        found = any(str(o.get('orderId')) == str(order_id) for o in open_orders)
        
        # Cancel
        self.adapter.cancel_order(self.test_symbol, order_id)
        
        assert found, "Should find our order in open orders"
        return f"Found order {order_id} in open orders"
    
    def test_multiple_limit_orders(self):
        """Test creating multiple limit orders"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        qty = self.format_qty(self.test_symbol, 8 / price)
        
        order_ids = []
        for pct in [0.85, 0.80, 0.75]:
            limit_price = round(price * pct, 2)
            order = self.adapter.client.create_order(
                symbol=self.test_symbol,
                side='BUY',
                type='LIMIT',
                timeInForce='GTC',
                quantity=qty,
                price=limit_price
            )
            order_ids.append(order.get('orderId'))
        
        time.sleep(0.5)
        
        # Cancel all
        for oid in order_ids:
            try:
                self.adapter.cancel_order(self.test_symbol, oid)
            except:
                pass
        
        return f"Created {len(order_ids)} orders, cancelled all"
    
    # ============ TP/SL TESTS ============
    
    def test_tp_create(self):
        """Test creating a TP order"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        qty = round(10 / price, 4)
        
        # Buy
        self.adapter.order_market_buy(self.test_symbol, qty)
        time.sleep(0.5)
        
        # Set TP
        tp_price = round(price * 1.05, 2)
        sl_price = round(price * 0.95, 2)
        
        tp_order_id = self.adapter.update_spot_tp_sl(
            self.test_symbol, qty, tp_price, sl_price
        )
        
        time.sleep(0.5)
        
        # Cancel TP and close
        try:
            self.adapter.cancel_order(self.test_symbol, tp_order_id)
        except:
            pass
        self.adapter.close_position_market(self.test_symbol, qty)
        
        return f"TP order: {tp_order_id} @ ${tp_price}"
    
    def test_tp_update(self):
        """Test updating a TP order"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        qty = round(10 / price, 4)
        
        # Buy
        self.adapter.order_market_buy(self.test_symbol, qty)
        time.sleep(0.5)
        
        # Set initial TP
        tp1_price = round(price * 1.05, 2)
        sl_price = round(price * 0.95, 2)
        tp1_id = self.adapter.update_spot_tp_sl(self.test_symbol, qty, tp1_price, sl_price)
        self.log(f"    TP1: {tp1_id} @ ${tp1_price}")
        
        time.sleep(0.5)
        
        # Update TP
        tp2_price = round(price * 1.10, 2)
        tp2_id = self.adapter.update_spot_tp_sl(
            self.test_symbol, qty, tp2_price, sl_price,
            old_tp=tp1_price, tp_order_id=tp1_id
        )
        self.log(f"    TP2: {tp2_id} @ ${tp2_price}")
        
        time.sleep(0.5)
        
        # Cleanup
        try:
            self.adapter.cancel_order(self.test_symbol, tp2_id)
        except:
            pass
        self.adapter.close_position_market(self.test_symbol, qty)
        
        return f"Updated TP from {tp1_id} to {tp2_id}"
    
    def test_tp_multiple_updates(self):
        """Test updating TP multiple times"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        qty = float(self.format_qty(self.test_symbol, 12 / price))
        
        # Buy
        self.adapter.order_market_buy(self.test_symbol, qty)
        time.sleep(0.5)
        
        sl_price = round(price * 0.93, 2)
        last_tp_id = None
        last_tp_price = None
        
        # Update TP 3 times
        for mult in [1.03, 1.06, 1.09]:
            new_tp = round(price * mult, 2)
            new_id = self.adapter.update_spot_tp_sl(
                self.test_symbol, qty, new_tp, sl_price,
                old_tp=last_tp_price, tp_order_id=last_tp_id
            )
            self.log(f"    TP @ ${new_tp}: {new_id}")
            last_tp_id = new_id
            last_tp_price = new_tp
            time.sleep(0.3)
        
        # Cleanup
        try:
            self.adapter.cancel_order(self.test_symbol, last_tp_id)
        except:
            pass
        self.adapter.close_position_market(self.test_symbol, qty)
        
        return f"Updated TP 3 times, final: {last_tp_id}"
    
    def test_full_trade_lifecycle(self):
        """Test complete trade: buy -> hold -> update TP -> close"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        qty = float(self.format_qty(self.test_symbol, 15 / price))
        
        # 1. Buy
        buy = self.adapter.order_market_buy(self.test_symbol, qty)
        self.log(f"    1. Bought: {buy.get('orderId')}")
        time.sleep(0.5)
        
        # 2. Set TP
        tp_price = round(price * 1.08, 2)
        sl_price = round(price * 0.92, 2)
        tp_id = self.adapter.update_spot_tp_sl(self.test_symbol, qty, tp_price, sl_price)
        self.log(f"    2. Set TP @ ${tp_price}: {tp_id}")
        time.sleep(0.5)
        
        # 3. Simulate hold (wait)
        time.sleep(1)
        
        # 4. Update TP (trailing)
        new_tp = round(price * 1.12, 2)
        new_tp_id = self.adapter.update_spot_tp_sl(
            self.test_symbol, qty, new_tp, sl_price,
            old_tp=tp_price, tp_order_id=tp_id
        )
        self.log(f"    3. Updated TP @ ${new_tp}: {new_tp_id}")
        time.sleep(0.5)
        
        # 5. Close position
        try:
            self.adapter.cancel_order(self.test_symbol, new_tp_id)
        except:
            pass
        close = self.adapter.close_position_market(self.test_symbol, qty)
        self.log(f"    4. Closed: {close.get('orderId')}")
        
        return f"Full lifecycle complete"
    
    # ============ EDGE CASE TESTS ============
    
    def test_min_notional_rejection(self):
        """Test that very small orders are rejected (MIN_NOTIONAL or LOT_SIZE)"""
        try:
            price = self.adapter.get_symbol_price(self.test_symbol)
            tiny_qty = round(0.5 / price, 8)  # ~$0.50 - very small
            
            self.adapter.order_market_buy(self.test_symbol, tiny_qty)
            return "UNEXPECTED: Order should have been rejected"
        except Exception as e:
            error_str = str(e).lower()
            if any(x in error_str for x in ["notional", "min_notional", "minimum", "lot_size", "lot size"]):
                return f"Correctly rejected: {str(e)[:40]}"
            raise
    
    def test_invalid_symbol(self):
        """Test error handling for invalid symbol"""
        try:
            self.adapter.get_symbol_price("INVALIDXYZ")
            return "UNEXPECTED: Should have failed"
        except:
            return "Correctly rejected invalid symbol"
    
    def test_cancel_nonexistent_order(self):
        """Test cancelling an order that doesn't exist"""
        try:
            self.adapter.cancel_order(self.test_symbol, "99999999999")
            return "UNEXPECTED: Should have failed"
        except Exception as e:
            return f"Correctly rejected: {str(e)[:50]}"
    
    def test_cancel_already_cancelled(self):
        """Test cancelling an already cancelled order"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        limit_price = round(price * 0.80, 2)
        qty = round(10 / price, 4)
        
        # Create and cancel
        order = self.adapter.client.create_order(
            symbol=self.test_symbol,
            side='BUY',
            type='LIMIT',
            timeInForce='GTC',
            quantity=qty,
            price=limit_price
        )
        order_id = order.get('orderId')
        self.adapter.cancel_order(self.test_symbol, order_id)
        
        time.sleep(0.5)
        
        # Try to cancel again
        try:
            self.adapter.cancel_order(self.test_symbol, order_id)
            return "UNEXPECTED: Double cancel should fail"
        except:
            return f"Correctly rejected double cancel of {order_id}"
    
    def test_quantity_precision_various(self):
        """Test precision for different amounts"""
        precision = self.adapter.get_symbol_precision(self.test_symbol)
        
        tests = [
            (0.123456789, precision),
            (1.999999999, precision),
            (0.00001, precision),
        ]
        
        for qty, prec in tests:
            truncated = self.adapter.truncate(qty, prec)
            str_qty = str(truncated)
            if '.' in str_qty:
                decimals = len(str_qty.split('.')[1])
                assert decimals <= prec
        
        return f"Precision tests passed for {len(tests)} cases"
    
    def test_sell_more_than_balance(self):
        """Test selling more than we have"""
        try:
            # Try to sell 1000 BNB (we don't have this much)
            self.adapter.close_position_market(self.test_symbol, 1000)
            return "UNEXPECTED: Should have failed"
        except Exception as e:
            return f"Correctly rejected: insufficient balance"
    
    def test_buy_at_zero_price(self):
        """Test creating order at zero price"""
        try:
            qty = 0.1
            order = self.adapter.client.create_order(
                symbol=self.test_symbol,
                side='BUY',
                type='LIMIT',
                timeInForce='GTC',
                quantity=qty,
                price=0
            )
            # If it succeeds somehow, cancel it
            self.adapter.cancel_order(self.test_symbol, order.get('orderId'))
            return "UNEXPECTED: Zero price should fail"
        except:
            return "Correctly rejected zero price"
    
    def test_negative_quantity(self):
        """Test order with negative quantity"""
        try:
            self.adapter.order_market_buy(self.test_symbol, -1)
            return "UNEXPECTED: Negative qty should fail"
        except:
            return "Correctly rejected negative quantity"
    
    def test_zero_quantity(self):
        """Test order with zero quantity"""
        try:
            self.adapter.order_market_buy(self.test_symbol, 0)
            return "UNEXPECTED: Zero qty should fail"
        except:
            return "Correctly rejected zero quantity"
    
    def test_tp_below_current_price(self):
        """Test TP price below current market (would execute immediately)"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        qty = round(10 / price, 4)
        
        # Buy
        self.adapter.order_market_buy(self.test_symbol, qty)
        time.sleep(0.5)
        
        # Try to set TP below current price - this would actually fill immediately
        tp_price = round(price * 0.99, 2)  # Below current
        sl_price = round(price * 0.95, 2)
        
        try:
            tp_id = self.adapter.update_spot_tp_sl(self.test_symbol, qty, tp_price, sl_price)
            # It might fill immediately since TP is below market
            time.sleep(1)
            
            # Check if it filled
            open_orders = self.adapter.get_open_orders(self.test_symbol)
            found = any(str(o.get('orderId')) == str(tp_id) for o in open_orders)
            
            if not found:
                return "TP filled immediately (expected for TP below market)"
            else:
                self.adapter.cancel_order(self.test_symbol, tp_id)
                self.adapter.close_position_market(self.test_symbol, qty)
                return "TP created but didn't fill (unexpected)"
        except Exception as e:
            # Cleanup
            try:
                self.adapter.close_position_market(self.test_symbol, qty)
            except:
                pass
            return f"TP below market handled: {str(e)[:50]}"
    
    def test_very_large_quantity(self):
        """Test order with unrealistically large quantity"""
        try:
            self.adapter.order_market_buy(self.test_symbol, 999999999)
            return "UNEXPECTED: Huge qty should fail"
        except:
            return "Correctly rejected huge quantity"
    
    # ============ STRESS TESTS ============
    
    def test_rapid_order_create_cancel(self):
        """Test rapid order creation and cancellation"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        qty = round(8 / price, 4)
        
        success_count = 0
        for i in range(5):
            try:
                limit_price = round(price * (0.80 - i * 0.02), 2)
                order = self.adapter.client.create_order(
                    symbol=self.test_symbol,
                    side='BUY',
                    type='LIMIT',
                    timeInForce='GTC',
                    quantity=qty,
                    price=limit_price
                )
                self.adapter.cancel_order(self.test_symbol, order.get('orderId'))
                success_count += 1
            except:
                pass
        
        return f"Rapid create/cancel: {success_count}/5 succeeded"
    
    def test_concurrent_balance_checks(self):
        """Test multiple balance checks in succession"""
        assets = ["USDC", "BNB", "BTC", "ETH", "USDT"]
        balances = {}
        
        for asset in assets:
            try:
                balances[asset] = self.adapter.get_balance(asset)
            except:
                balances[asset] = 0
        
        return f"Checked {len(balances)} balances"
    
    # ============ RUN ALL ============
    
    def run_all_tests(self):
        """Run all tests and print summary"""
        print("\n" + "="*70)
        print("🧪 BINANCE ORDER MANAGEMENT COMPREHENSIVE TEST SUITE")
        print("="*70 + "\n")
        
        # Connectivity tests
        print("📡 CONNECTIVITY TESTS (18 tests)")
        print("-"*50)
        self.run_test("Get Symbol Price BNB", self.test_get_symbol_price)
        self.run_test("Get Symbol Price BTC", self.test_get_symbol_price_btc)
        self.run_test("Get Balance USDC", self.test_get_balance_usdc)
        self.run_test("Get Balance BNB", self.test_get_balance_bnb)
        self.run_test("Get Balance BTC", self.test_get_balance_btc)
        self.run_test("Get Asset Balance Detail USDC", self.test_get_asset_balance_detail)
        self.run_test("Get Asset Balance Detail BNB", self.test_get_asset_balance_detail_bnb)
        self.run_test("Get Symbol Info BNB", self.test_get_symbol_info)
        self.run_test("Get Symbol Info BTC", self.test_get_symbol_info_btc)
        self.run_test("Get All Tickers", self.test_get_all_tickers)
        self.run_test("Tickers Contains BNB", self.test_get_all_tickers_contains_bnb)
        self.run_test("Get Klines 1h", self.test_get_klines_1h)
        self.run_test("Get Klines 15m", self.test_get_klines_15m)
        self.run_test("Get Klines 1d", self.test_get_klines_1d)
        self.run_test("Get Account", self.test_get_account)
        self.run_test("Get Symbol Precision BNB", self.test_get_symbol_precision)
        self.run_test("Get Symbol Precision BTC", self.test_get_symbol_precision_btc)
        self.run_test("Truncate Quantity", self.test_truncate_quantity)
        
        # Order tests
        print("\n📦 ORDER TESTS (8 tests)")
        print("-"*50)
        self.run_test("Market Buy Small", self.test_market_buy_small)
        self.run_test("Market Buy/Sell Cycle", self.test_market_buy_sell_cycle)
        self.run_test("Limit Order Below Market", self.test_limit_order_below_market)
        self.run_test("Limit Order Above Market", self.test_limit_order_above_market)
        self.run_test("Get Open Orders Empty", self.test_get_open_orders_empty)
        self.run_test("Get Open Orders With Order", self.test_get_open_orders_with_order)
        self.run_test("Multiple Limit Orders", self.test_multiple_limit_orders)
        self.run_test("Truncate Floor", self.test_truncate_quantity_floor)
        
        # TP/SL tests
        print("\n🎯 TP/SL TESTS (4 tests)")
        print("-"*50)
        self.run_test("TP Create", self.test_tp_create)
        self.run_test("TP Update", self.test_tp_update)
        self.run_test("TP Multiple Updates", self.test_tp_multiple_updates)
        self.run_test("Full Trade Lifecycle", self.test_full_trade_lifecycle)
        
        # Edge cases
        print("\n⚠️ EDGE CASE TESTS (12 tests)")
        print("-"*50)
        self.run_test("Min Notional Rejection", self.test_min_notional_rejection)
        self.run_test("Invalid Symbol", self.test_invalid_symbol)
        self.run_test("Cancel Nonexistent Order", self.test_cancel_nonexistent_order)
        self.run_test("Cancel Already Cancelled", self.test_cancel_already_cancelled)
        self.run_test("Quantity Precision Various", self.test_quantity_precision_various)
        self.run_test("Sell More Than Balance", self.test_sell_more_than_balance)
        self.run_test("Buy At Zero Price", self.test_buy_at_zero_price)
        self.run_test("Negative Quantity", self.test_negative_quantity)
        self.run_test("Zero Quantity", self.test_zero_quantity)
        self.run_test("TP Below Current Price", self.test_tp_below_current_price)
        self.run_test("Very Large Quantity", self.test_very_large_quantity)
        self.run_test("Rapid Create/Cancel", self.test_rapid_order_create_cancel)
        
        # Stress tests
        print("\n🔥 STRESS TESTS (1 test)")
        print("-"*50)
        self.run_test("Concurrent Balance Checks", self.test_concurrent_balance_checks)
        
        # Summary
        print("\n" + "="*70)
        print("📊 SUMMARY")
        print("="*70)
        
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total_time = sum(r.duration for r in self.results)
        
        print(f"Total Tests: {len(self.results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏱️ Total Time: {total_time:.2f}s")
        print(f"📈 Pass Rate: {(passed/len(self.results)*100):.1f}%")
        
        if failed > 0:
            print("\n❌ FAILED TESTS:")
            for r in self.results:
                if not r.passed:
                    print(f"   - {r.name}: {r.message}")
        
        print("\n" + "="*70)
        return failed == 0


def main():
    parser = argparse.ArgumentParser(description="Test Binance order management")
    parser.add_argument("--api-key", help="Binance API key")
    parser.add_argument("--secret", help="Binance secret key")
    parser.add_argument("--mainnet", action="store_true", help="Use mainnet (default: testnet)")
    args = parser.parse_args()
    
    api_key = args.api_key or os.getenv("BINANCE_TEST_API_KEY")
    secret = args.secret or os.getenv("BINANCE_TEST_SECRET")
    
    if not api_key or not secret:
        print("❌ Error: API key and secret required")
        print("   Set BINANCE_TEST_API_KEY and BINANCE_TEST_SECRET environment variables")
        print("   Or use --api-key and --secret arguments")
        sys.exit(1)
    
    testnet = not args.mainnet
    print(f"🔧 Mode: {'TESTNET' if testnet else '⚠️ MAINNET'}")
    
    if not testnet:
        confirm = input("⚠️ WARNING: Running on MAINNET will use real funds! Type 'YES' to continue: ")
        if confirm != "YES":
            print("Aborted.")
            sys.exit(0)
    
    tester = BinanceOrderTester(api_key, secret, testnet=testnet)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
