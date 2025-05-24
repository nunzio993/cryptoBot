from models import Order, SessionLocal, APIKey, Exchange
from src.adapters import BinanceAdapter
import os
import datetime

def get_real_balance(symbol, adapter):
    asset = symbol.replace("USDC", "")
    try:
        balance = float(adapter.get_balance(asset))
        return balance
    except Exception as e:
        print(f"Errore recupero saldo {asset}: {e}")
        return 0

def main():
    session = SessionLocal()
    exchange = session.query(Exchange).filter_by(name="binance").first()
    from sqlalchemy import text
    users = session.execute(text("SELECT DISTINCT user_id FROM orders WHERE status='EXECUTED'")).fetchall()
    for u in users:
        user_id = u[0]
        key = session.query(APIKey).filter_by(user_id=user_id, exchange_id=exchange.id, is_testnet=False).first()
        if not key:
            print(f"[user={user_id}] Nessuna API Key trovata, skippo.")
            continue

        adapter = BinanceAdapter(key.api_key, key.secret_key, testnet=False)
        orders = session.query(Order).filter_by(user_id=user_id, status="EXECUTED").all()
        for o in orders:
            real_balance = get_real_balance(o.symbol, adapter)
            print(f"[user={user_id}] Ordine {o.id} {o.symbol}: saldo reale={real_balance}")
            if real_balance < 0.005:
                print(f"[user={user_id}] Aggiorno stato ordine {o.id} {o.symbol} - saldo reale: {real_balance}")
                o.status = "CLOSED_MANUAL"
                o.closed_at = datetime.datetime.now(datetime.timezone.utc)
    session.commit()
    print("Aggiornamento completato.")

if __name__ == "__main__":
    main()

