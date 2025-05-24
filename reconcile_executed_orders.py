# src/reconcile_executed_orders.py

from models import Order, SessionLocal
from binance.client import Client
import os
from datetime import datetime, timezone

def reconcile_executed_orders():
    """
    Sincronizza gli ordini 'EXECUTED' del database con quelli effettivi su Binance.
    Se trova ordini che risultano eseguiti solo localmente, li marca come MISMATCH_BINANCE.
    """
    # --- 1. Connessione Binance ---
    API_KEY    = os.getenv('BINANCE_API_KEY')
    API_SECRET = os.getenv('BINANCE_API_SECRET')
    TESTNET    = os.getenv('BINANCE_TESTNET', 'true').lower() == 'true'
    client = Client(API_KEY, API_SECRET, testnet=TESTNET)

    # --- 2. Connessione DB ---
    session = SessionLocal()
    print("\n[RECONCILE] Inizio riconciliazione ordini EXECUTED...")

    # --- 3. Recupera tutti gli ordini EXECUTED ---
    executed_orders = session.query(Order).filter(Order.status == 'EXECUTED').all()
    print(f"[RECONCILE] Trovati {len(executed_orders)} ordini EXECUTED nel DB.")

    # --- 4. Trova tutti i simboli da controllare ---
    symbols_in_db = list({o.symbol for o in executed_orders})

    # --- 5. Prendi tutti gli open orders SELL LIMIT da Binance per quei simboli ---
    binance_sell_orders = set()
    for symbol in symbols_in_db:
        try:
            open_orders = client.get_open_orders(symbol=symbol)
            for order in open_orders:
                if order['side'] == 'SELL' and order['status'] == 'NEW':
                    # Chiave: (symbol, quantità, TP)
                    key = (order['symbol'], float(order['origQty']), float(order['price']))
                    binance_sell_orders.add(key)
        except Exception as e:
            print(f"[RECONCILE] Errore get_open_orders({symbol}): {e}")

    # --- 6. Cerca ordini EXECUTED che NON hanno più SELL LIMIT attivo su Binance ---
    ordini_fantasma = []
    for o in executed_orders:
        key = (o.symbol, float(o.quantity), float(o.take_profit))
        if key not in binance_sell_orders:
            ordini_fantasma.append(o)

    # --- 7. Mostra e (opzionale) aggiorna DB ---
    if ordini_fantasma:
        print("\n[RECONCILE] ATTENZIONE! Ordini eseguiti nel DB ma NON presenti su Binance:")
        for o in ordini_fantasma:
            print(f" - ID: {o.id} | {o.symbol} | QTY: {o.quantity} | TP: {o.take_profit} | EXEC_AT: {o.executed_at}")

        # (Opzionale) Marca come MISMATCH_BINANCE
        for o in ordini_fantasma:
            o.status = "MISMATCH_BINANCE"
            o.closed_at = datetime.now(timezone.utc)
        session.commit()
        print(f"[RECONCILE] {len(ordini_fantasma)} ordini marcati come MISMATCH_BINANCE.")
    else:
        print("[RECONCILE] TUTTO OK: tutti gli ordini EXECUTED trovano un SELL LIMIT su Binance.")

    session.close()

if __name__ == "__main__":
    reconcile_executed_orders()

