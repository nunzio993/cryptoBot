#!/usr/bin/env python3
"""
Automated Test Script for Binance Order Management
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
    
    # ============ CONNECTIVITY TESTS ============
    
    def test_get_symbol_price(self):
        """Test fetching current price"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        assert price > 0, "Price should be positive"
        return f"Price: ${price:.2f}"
    
    def test_get_balance(self):
        """Test fetching USDC balance"""
        balance = self.adapter.get_balance("USDC")
        assert balance >= 0, "Balance should be non-negative"
        return f"USDC Balance: ${balance:.2f}"
    
    def test_get_asset_balance_detail(self):
        """Test detailed balance with free/locked"""
        detail = self.adapter.get_asset_balance("USDC")
        assert 'free' in detail and 'locked' in detail
        return f"Free: {detail['free']}, Locked: {detail['locked']}"
    
    def test_get_symbol_info(self):
        """Test symbol info with filters"""
        info = self.adapter.get_symbol_info(self.test_symbol)
        assert 'filters' in info, "Should have filters"
        filters = {f['filterType']: f for f in info['filters']}
        assert 'LOT_SIZE' in filters, "Should have LOT_SIZE filter"
        return f"Filters: {list(filters.keys())}"
    
    def test_get_all_tickers(self):
        """Test fetching all tickers"""
        tickers = self.adapter.get_all_tickers()
        assert len(tickers) > 100, "Should have many tickers"
        return f"Tickers count: {len(tickers)}"
    
    def test_get_klines(self):
        """Test fetching candlestick data"""
        klines = self.adapter.get_klines(self.test_symbol, "1h", limit=5)
        assert len(klines) > 0, "Should have klines"
        assert len(klines[0]) >= 6, "Kline should have OHLCV data"
        return f"Got {len(klines)} candles"
    
    # ============ ORDER TESTS ============
    
    def test_market_buy_sell(self):
        """Test market buy followed by market sell"""
        # Get current price for quantity calculation
        price = self.adapter.get_symbol_price(self.test_symbol)
        qty = round(10 / price, 4)  # ~$10 worth
        
        # Buy
        buy_order = self.adapter.order_market_buy(self.test_symbol, qty)
        assert buy_order.get('orderId'), "Buy should return orderId"
        self.log(f"    Buy order: {buy_order.get('orderId')}")
        
        time.sleep(1)  # Wait for fill
        
        # Sell
        sell_order = self.adapter.close_position_market(self.test_symbol, qty)
        assert sell_order.get('orderId'), "Sell should return orderId"
        
        return f"Buy: {buy_order.get('orderId')}, Sell: {sell_order.get('orderId')}"
    
    def test_limit_order_create_cancel(self):
        """Test creating and cancelling a limit order"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        limit_price = round(price * 0.9, 2)  # 10% below market (won't fill)
        
        # Get proper quantity formatting
        info = self.adapter.get_symbol_info(self.test_symbol)
        filters = {f['filterType']: f for f in info['filters']}
        step_size = float(filters['LOT_SIZE']['stepSize'])
        
        qty = round(10 / price, 4)  # ~$10 worth
        
        # Create limit buy order
        order = self.adapter.client.create_order(
            symbol=self.test_symbol,
            side='BUY',
            type='LIMIT',
            timeInForce='GTC',
            quantity=qty,
            price=limit_price
        )
        order_id = order.get('orderId')
        assert order_id, "Should return orderId"
        self.log(f"    Created limit order: {order_id} @ ${limit_price}")
        
        time.sleep(0.5)
        
        # Cancel it
        cancel = self.adapter.cancel_order(self.test_symbol, order_id)
        
        return f"Created and cancelled order {order_id}"
    
    def test_get_open_orders(self):
        """Test fetching open orders"""
        orders = self.adapter.get_open_orders(self.test_symbol)
        assert isinstance(orders, list), "Should return list"
        return f"Open orders: {len(orders)}"
    
    # ============ TP/SL TESTS ============
    
    def test_tp_sl_workflow(self):
        """Test full TP/SL workflow: buy -> set TP -> update TP -> close"""
        price = self.adapter.get_symbol_price(self.test_symbol)
        qty = round(10 / price, 4)  # ~$10 worth
        
        # 1. Buy position
        buy_order = self.adapter.order_market_buy(self.test_symbol, qty)
        self.log(f"    Bought {qty} @ market")
        time.sleep(1)
        
        # 2. Set initial TP (10% above)
        tp_price = round(price * 1.10, 2)
        sl_price = round(price * 0.95, 2)
        
        tp_order_id = self.adapter.update_spot_tp_sl(
            self.test_symbol, qty, tp_price, sl_price
        )
        self.log(f"    Set TP @ ${tp_price}, got order {tp_order_id}")
        
        time.sleep(0.5)
        
        # 3. Update TP (15% above)
        new_tp_price = round(price * 1.15, 2)
        new_tp_order_id = self.adapter.update_spot_tp_sl(
            self.test_symbol, qty, new_tp_price, sl_price,
            old_tp=tp_price, tp_order_id=tp_order_id
        )
        self.log(f"    Updated TP @ ${new_tp_price}, got order {new_tp_order_id}")
        
        time.sleep(0.5)
        
        # 4. Cancel TP and close position
        try:
            self.adapter.cancel_order(self.test_symbol, new_tp_order_id)
        except:
            pass  # May already be cancelled
        
        sell_order = self.adapter.close_position_market(self.test_symbol, qty)
        self.log(f"    Closed position")
        
        return f"TP workflow complete: {buy_order.get('orderId')} -> {new_tp_order_id}"
    
    # ============ EDGE CASE TESTS ============
    
    def test_min_notional_rejection(self):
        """Test that orders below min notional are rejected"""
        try:
            # Try to buy $0.50 worth (below $5 minimum)
            price = self.adapter.get_symbol_price(self.test_symbol)
            tiny_qty = round(0.5 / price, 6)  # Very small
            
            self.adapter.order_market_buy(self.test_symbol, tiny_qty)
            return "UNEXPECTED: Order should have been rejected"
        except Exception as e:
            if "MIN_NOTIONAL" in str(e) or "NOTIONAL" in str(e) or "notional" in str(e).lower():
                return "Correctly rejected: MIN_NOTIONAL"
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
    
    def test_quantity_precision(self):
        """Test quantity is properly formatted"""
        # Get symbol precision
        precision = self.adapter.get_symbol_precision(self.test_symbol)
        
        # Test truncate
        truncated = self.adapter.truncate(0.123456789, precision)
        
        # Verify precision
        str_qty = str(truncated)
        if '.' in str_qty:
            decimals = len(str_qty.split('.')[1])
            assert decimals <= precision, f"Too many decimals: {decimals} > {precision}"
        
        return f"Precision: {precision}, Truncated: {truncated}"
    
    # ============ RUN ALL ============
    
    def run_all_tests(self):
        """Run all tests and print summary"""
        print("\n" + "="*60)
        print("🧪 BINANCE ORDER MANAGEMENT TEST SUITE")
        print("="*60 + "\n")
        
        # Connectivity tests
        print("📡 CONNECTIVITY TESTS")
        print("-"*40)
        self.run_test("Get Symbol Price", self.test_get_symbol_price)
        self.run_test("Get Balance", self.test_get_balance)
        self.run_test("Get Asset Balance Detail", self.test_get_asset_balance_detail)
        self.run_test("Get Symbol Info", self.test_get_symbol_info)
        self.run_test("Get All Tickers", self.test_get_all_tickers)
        self.run_test("Get Klines", self.test_get_klines)
        
        # Order tests
        print("\n📦 ORDER TESTS")
        print("-"*40)
        self.run_test("Market Buy/Sell", self.test_market_buy_sell)
        self.run_test("Limit Order Create/Cancel", self.test_limit_order_create_cancel)
        self.run_test("Get Open Orders", self.test_get_open_orders)
        
        # TP/SL tests
        print("\n🎯 TP/SL TESTS")
        print("-"*40)
        self.run_test("TP/SL Workflow", self.test_tp_sl_workflow)
        
        # Edge cases
        print("\n⚠️ EDGE CASE TESTS")
        print("-"*40)
        self.run_test("Min Notional Rejection", self.test_min_notional_rejection)
        self.run_test("Invalid Symbol", self.test_invalid_symbol)
        self.run_test("Cancel Nonexistent Order", self.test_cancel_nonexistent_order)
        self.run_test("Quantity Precision", self.test_quantity_precision)
        
        # Summary
        print("\n" + "="*60)
        print("📊 SUMMARY")
        print("="*60)
        
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total_time = sum(r.duration for r in self.results)
        
        print(f"Total Tests: {len(self.results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏱️ Total Time: {total_time:.2f}s")
        
        if failed > 0:
            print("\n❌ FAILED TESTS:")
            for r in self.results:
                if not r.passed:
                    print(f"   - {r.name}: {r.message}")
        
        print("\n" + "="*60)
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
