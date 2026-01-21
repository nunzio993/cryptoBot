"""
Test script to diagnose why Stop Loss is not triggering.
Run this on VPS to see exactly what values are being compared.

Usage: python scripts/test_sl_logic.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone, timedelta
from models import Order, Exchange, APIKey, SessionLocal
from src.exchange_factory import ExchangeFactory
from src.crypto_utils import decrypt_api_key

# Interval mappings (same as core_and_scheduler.py)
INTERVAL_MAP = {
    'M5': '5m', 'H1': '1h', 'H4': '4h', 'Daily': '1d',
    '5m': '5m', '1h': '1h', '4h': '4h', '1d': '1d',
    'Market': '1m',
}

INTERVAL_SECONDS = {
    'M5': 5*60, 'H1': 60*60, 'H4': 4*60*60, 'Daily': 24*60*60,
    '5m': 5*60, '1h': 60*60, '4h': 4*60*60, '1d': 24*60*60,
    'Market': 60, '1m': 60,
}

def get_candle_close_time(candle_open_ts, interval):
    seconds = INTERVAL_SECONDS.get(interval)
    if seconds is None:
        print(f"  ⚠️  WARNING: Unknown interval '{interval}', using 5 min default!")
        seconds = 5 * 60
    return candle_open_ts + timedelta(seconds=seconds)

def test_sl_for_order(order_id=None):
    with SessionLocal() as session:
        if order_id:
            orders = session.query(Order).filter(Order.id == order_id).all()
        else:
            orders = session.query(Order).filter(Order.status.in_(['EXECUTED', 'PARTIAL_FILLED'])).all()
        
        if not orders:
            print("No executed orders found.")
            return
            
        for order in orders:
            print(f"\n{'='*60}")
            print(f"ORDER #{order.id} - {order.symbol}")
            print(f"{'='*60}")
            
            # Get exchange info
            exchange = session.query(Exchange).filter_by(id=order.exchange_id).first()
            exchange_name = exchange.name if exchange else "binance"
            is_testnet = order.is_testnet or False
            
            print(f"  Exchange: {exchange_name} ({'Testnet' if is_testnet else 'Mainnet'})")
            print(f"  Status: {order.status}")
            print(f"  Stop Loss: ${order.stop_loss}")
            print(f"  Stop Interval: {order.stop_interval}")
            print(f"  Entry Interval: {order.entry_interval}")
            print(f"  Executed at: {order.executed_at}")
            print(f"  SL Updated at: {order.sl_updated_at}")
            print(f"  Created at: {order.created_at}")
            
            if order.stop_loss is None:
                print(f"  ❌ No stop loss set - skipping")
                continue
            
            # Get API key
            api_key_obj = session.query(APIKey).filter_by(
                user_id=order.user_id,
                exchange_id=order.exchange_id,
                is_testnet=is_testnet
            ).first()
            
            if not api_key_obj:
                print(f"  ❌ No API key found for {exchange_name}")
                continue
            
            # Create adapter
            try:
                decrypted_key = decrypt_api_key(api_key_obj.api_key, order.user_id)
                decrypted_secret = decrypt_api_key(api_key_obj.secret_key, order.user_id)
                
                adapter = ExchangeFactory.create(
                    exchange_name=exchange_name,
                    api_key=decrypted_key,
                    api_secret=decrypted_secret,
                    testnet=is_testnet
                )
            except Exception as e:
                print(f"  ❌ Failed to create adapter: {e}")
                continue
            
            # Fetch candle
            interval = order.stop_interval if order.stop_interval else order.entry_interval
            api_interval = INTERVAL_MAP.get(interval, interval)
            
            print(f"\n  📊 Fetching candle data...")
            print(f"     Interval: {interval} -> API: {api_interval}")
            
            try:
                klines = adapter.get_klines(order.symbol, api_interval, limit=2)
                if not klines or len(klines) < 2:
                    print(f"  ❌ Not enough candle data: got {len(klines) if klines else 0}")
                    continue
                    
                candle = klines[-2]  # Last closed candle
                print(f"     Raw candle: {candle[:5]}...")
                
            except Exception as e:
                print(f"  ❌ Failed to fetch candles: {e}")
                continue
            
            # Parse candle
            last_close = float(candle[4])
            ts_candle = datetime.fromtimestamp(int(candle[0]) / 1000, tz=timezone.utc)
            candle_close_time = get_candle_close_time(ts_candle, interval)
            
            print(f"\n  📈 Candle Analysis:")
            print(f"     Candle Open Time: {ts_candle}")
            print(f"     Candle Close Time: {candle_close_time}")
            print(f"     Last Close Price: ${last_close:.2f}")
            print(f"     Stop Loss Price: ${float(order.stop_loss):.2f}")
            
            # Reference time
            reference_time = order.sl_updated_at if order.sl_updated_at else order.executed_at
            if reference_time is None:
                reference_time = order.created_at
                print(f"     ⚠️  Using created_at as reference (no executed_at)")
            
            if reference_time.tzinfo is None:
                reference_time = reference_time.replace(tzinfo=timezone.utc)
            
            print(f"     Reference Time: {reference_time}")
            
            # Check conditions
            print(f"\n  ✅ SL Condition Checks:")
            
            price_check = last_close <= float(order.stop_loss)
            time_check = candle_close_time > reference_time
            
            print(f"     1. Price <= SL: {last_close:.2f} <= {float(order.stop_loss):.2f} = {price_check}")
            print(f"     2. Candle closes after ref: {candle_close_time} > {reference_time} = {time_check}")
            
            if price_check and time_check:
                print(f"\n  🎯 SL SHOULD TRIGGER! Both conditions are TRUE")
            else:
                print(f"\n  ⏳ SL will NOT trigger:")
                if not price_check:
                    diff = last_close - float(order.stop_loss)
                    print(f"     - Price is ${diff:.2f} ABOVE stop loss")
                if not time_check:
                    time_diff = reference_time - candle_close_time
                    print(f"     - Need to wait for candle closing AFTER {reference_time}")
                    print(f"       Current candle closed at {candle_close_time}")
                    print(f"       Difference: {time_diff}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--order', type=int, help='Specific order ID to test')
    args = parser.parse_args()
    
    test_sl_for_order(args.order)
