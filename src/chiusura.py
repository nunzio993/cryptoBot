# cleanup_orders.py
import sqlite3
import os

# Se usi .env per DB_PATH, caricalo con python-dotenv:
# from dotenv import load_dotenv
# load_dotenv()
# DB_PATH = os.getenv("DB_PATH", "trades.db")

DB_PATH = "trades.db"  # Modifica se il tuo DB è altrove

def cleanup():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Conta quanti ordini verranno rimossi
    cur.execute("SELECT COUNT(*) FROM orders WHERE status IN ('PENDING', 'EXECUTED')")
    to_delete = cur.fetchone()[0]
    print(f"⚠️ Verranno eliminati {to_delete} ordini con status PENDING o EXECUTED")

    # Elimina
    cur.execute("DELETE FROM orders WHERE status IN ('PENDING', 'EXECUTED')")
    conn.commit()
    conn.close()
    print("✅ Pulizia completata. La dashboard ora mostra solo gli ordini chiusi.")

if __name__ == "__main__":
    cleanup()
