import os
import math

from binance.client import Client

client = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET"), testnet=True)
SYMBOLS = [s['symbol'] for s in client.get_exchange_info()['symbols']]

# — CONFIGURAZIONE TESTNET vs MAINNET —
API_KEY = os.getenv("5gslQFwhB1A2eo5eETDQkHZzsE4fECHvvh2npVLpCkDEuVWPgSOIJNv3GARLdFwK")
API_SECRET = os.getenv("iyPgm84XXph1VIs3hj3ICpTS8nzrJnMI703y1C7fpByasLKY8pkCugiiC6kK8GgS")

client = Client(API_KEY, API_SECRET)
# Se sei in Testnet:
# client.API_URL = "https://testnet.binance.vision/api"

def load_usdc_symbols():
    """Scarica exchangeInfo e restituisce lista di tutti i symbol *_USDC_."""
    info = client.get_exchange_info()
    all_symbols = info["symbols"]
    usdc_syms = [s for s in all_symbols if s["symbol"].endswith("USDC") and s["status"] == "TRADING"]
    return usdc_syms

def extract_symbol_filters(symbol_data):
    filters = {f["filterType"]: f for f in symbol_data["filters"]}

    # 1) min_notional (NOTIONAL o MIN_NOTIONAL)
    nf = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL")
    if nf:
        if "minNotional" in nf:
            min_notional = float(nf["minNotional"])
        elif "notional" in nf:
            min_notional = float(nf["notional"])
        else:
            min_notional = 0.0
    else:
        min_notional = 0.0

    # 2) lot size
    lot = filters.get("LOT_SIZE", {})
    min_qty = float(lot.get("minQty", 0))
    max_qty = float(lot.get("maxQty", 0))
    step    = float(lot.get("stepSize", 0))

    # 3) max orders
    mo = filters.get("MAX_NUM_ORDERS", {})
    # alcuni filtri possono chiamare il campo maxNumOrders o limitOrders
    max_orders = int(mo.get("maxNumOrders", mo.get("limitOrders", 0)) or 0)

    # 4) max algo orders
    mao = filters.get("MAX_NUM_ALGO_ORDERS", {})
    # qui può esistere maxNumAlgoOrders o limit
    max_algo_orders = int(mao.get("maxNumAlgoOrders", mao.get("limit", 0)) or 0)

    return {
        "symbol": symbol_data["symbol"],
        "min_notional": min_notional,
        "lot_size": {
            "min_qty": min_qty,
            "max_qty": max_qty,
            "step":    step
        },
        "max_orders":      max_orders,
        "max_algo_orders": max_algo_orders,
    }

if __name__ == "__main__":
    usdc_list = load_usdc_symbols()
    print(f"Trovati {len(usdc_list)} simboli USDC:")
    # Stampo i primi 10 simboli con i loro filtri già normalizzati
    for s in usdc_list[:10]:
        data = extract_symbol_filters(s)
        print(data)

def normalize_quantity(qty: float, step: float, min_qty: float, max_qty: float) -> float:
    """
    Dato un valore qty desiderato, restituisce la quantità corretta arrotondata per difetto
    al passo `step`, e controlla che sia tra min_qty e max_qty.
    """
    # arrotonda per difetto al multiplo di step
    normalized = math.floor(qty / step) * step
    # arrotondamento al numero di decimali di step
    dec = int(-math.log10(step))
    normalized = round(normalized, dec)
    if normalized < min_qty:
        raise ValueError(f"Quantity {normalized} < MIN_QTY {min_qty}")
    if normalized > max_qty:
        raise ValueError(f"Quantity {normalized} > MAX_QTY {max_qty}")
    return normalized
