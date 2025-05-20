import os
import argparse
import sys
import math
import sqlite3
from datetime import datetime
from binance.client import Client
from src.signals import get_last_close, check_entry_condition, compute_stop_loss, compute_take_profit
from src.symbols import normalize_quantity, extract_symbol_filters

# ---------------- CONFIG ----------------
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET, testnet=True)
# Usa Testnet per prove
client.API_URL = "https://testnet.binance.vision/api"
DB_PATH = "trades.db"

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS trades (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT NOT NULL,
      quantity REAL NOT NULL,
      stop_price REAL NOT NULL,
      tf TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'OPEN',
      created_at TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()


def save_open_trade(symbol, qty, stop_price, tf):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO trades(symbol, quantity, stop_price, tf, created_at) VALUES(?,?,?,?,?)",
        (symbol, qty, stop_price, tf, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

# Initialize DB
init_db()

# ---------------- HELPERS ----------------
def get_price_filter(symbol_info):
    for f in symbol_info.get("filters", []):
        if f.get("filterType") == "PRICE_FILTER":
            return float(f.get("tickSize", 1))
    return 1.0


def normalize_price(price: float, tick_size: float) -> float:
    precision = int(round(-math.log10(tick_size)))
    normalized = math.floor(price / tick_size) * tick_size
    return round(normalized, precision)

# ---------------- RUNNER ----------------
def main():
    parser = argparse.ArgumentParser(description="Run trading signal and place orders on Binance Testnet/Mainnet")
    parser.add_argument("--symbol",      required=True)
    parser.add_argument("--timeframe",   choices=["market","H1","H4","D"], default="market")
    parser.add_argument("--entry_price", type=float, required=True)
    parser.add_argument("--sl_method",   choices=["market","H1","H4","D"], default="market")
    parser.add_argument("--sl_percent",  type=float, default=1.0)
    parser.add_argument("--tp_percent",  type=float, default=2.0)
    parser.add_argument("--quantity",    type=float, required=True)
    args = parser.parse_args()

    symbol = args.symbol.upper()

    # Fetch symbol info & filters
    symbol_info = client.get_symbol_info(symbol)
    if not symbol_info:
        print(f"Error: Symbol {symbol} not found on Binance.")
        sys.exit(1)
    filters = extract_symbol_filters(symbol_info)
    tick_size = get_price_filter(symbol_info)

    # Normalize quantity
    try:
        qty = normalize_quantity(
            args.quantity,
            filters["lot_size"]["step"],
            filters["lot_size"]["min_qty"],
            filters["lot_size"]["max_qty"]
        )
    except ValueError as e:
        print(f"Quantity normalization error: {e}")
        sys.exit(1)

    # Fetch closes if needed
    closes = {}
    for tf in {args.timeframe, args.sl_method}:
        if tf != "market":
            closes[tf] = get_last_close(symbol, tf)

    # Check entry
    last_close = closes.get(args.timeframe)
    if not check_entry_condition(last_close, args.entry_price, args.timeframe):
        print(f"No entry: close ({args.timeframe})={last_close} vs entry_price {args.entry_price}")
        sys.exit(0)
    print(f"Entry signal: last_close {last_close} meets condition on {args.timeframe}")

    # Place market buy
    try:
        order = client.order_market_buy(symbol=symbol, quantity=qty)
    except Exception as e:
        print(f"Market buy failed: {e}")
        sys.exit(1)
    entry_price = float(order["fills"][0]["price"])
    print(f"BUY executed: {qty} {symbol} @ {entry_price}")

    # Compute SL
    raw_sl_price = compute_stop_loss(entry_price, args.sl_method, {"percent": args.sl_percent, "close": closes})
    sl_price = normalize_price(raw_sl_price, tick_size)
    print(f"Computed SL @ {sl_price}")

    # Handle SL method
    if args.sl_method.lower() == "market":
        # Immediate SL limit order
        try:
            sl_limit = normalize_price(sl_price * 0.995, tick_size)
            sl_order = client.create_order(
                symbol=symbol,
                side=Client.SIDE_SELL,
                type=Client.ORDER_TYPE_STOP_LOSS_LIMIT,
                quantity=qty,
                price=str(sl_limit),
                stopPrice=str(sl_price),
                timeInForce=Client.TIME_IN_FORCE_GTC
            )
            print(f"Immediate stop-loss order placed: {sl_order}")
        except Exception as ex:
            print(f"Immediate stop-loss placement failed: {ex}")
            sys.exit(1)
    else:
        # Schedule close-only SL
        save_open_trade(symbol, qty, sl_price, args.sl_method)
        print(f"Trade scheduled for close-only SL: {symbol}, qty={qty}, stop_price={sl_price}, tf={args.sl_method}")

if __name__ == "__main__":
    main()
