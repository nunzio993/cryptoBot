import os
from binance.client import Client
from datetime import datetime

# — CONFIG —
API_KEY    = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)
# client.API_URL = "https://testnet.binance.vision/api"  # se sei in Testnet

# Mappatura intervalli
INTERVALS = {
    "H1": Client.KLINE_INTERVAL_1HOUR,
    "H4": Client.KLINE_INTERVAL_4HOUR,
    "D" : Client.KLINE_INTERVAL_1DAY,
}

def get_last_close(symbol: str, timeframe: str) -> float:
    """
    Ritorna la chiusura dell'ultima candela completata per il symbol su timeframe.
    """
    interval = INTERVALS[timeframe]
    klines = client.get_klines(symbol=symbol, interval=interval, limit=2)
    # [-2] è l'ultima candela chiusa
    return float(klines[-2][4])

def check_entry_condition(last_close: float, entry_price: float, method: str) -> bool:
    """
    Controlla se soddisfa il segnale di ingresso:
      - method == "market"    → sempre True (market immediato)
      - method in ["H1","H4","D"] → chiusura >= entry_price
    """
    if method.lower() == "market":
        return True
    return last_close >= entry_price

def compute_stop_loss(entry_price: float, method: str, params: dict) -> float:
    """
    Calcola il livello di stop-loss:
      - method == "market"    → ritorna entry_price * (1 - params["percent"]/100)
      - method in ["H1","H4","D"] → params["close"][method] (chiusura di quel timeframe)
    """
    if method.lower() == "market":
        return entry_price * (1 - params.get("percent", 1)/100.0)
    return params["close"][method]

def compute_take_profit(entry_price: float, tp_percent: float) -> float:
    """
    Calcola il take-profit lineare a percentuale fissa.
    (Il trailing sarà gestito a runtime con un ordine OCO o logica separata.)
    """
    return entry_price * (1 + tp_percent/100.0)


if __name__ == "__main__":
    # Esempio d’uso rapido
    symbol = "BTCUSDC"
    tf     = "H4"
    last = get_last_close(symbol, tf)
    print(f"[{datetime.utcnow()}] {symbol} last {tf} close = {last}")
