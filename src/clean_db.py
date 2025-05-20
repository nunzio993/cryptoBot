import sqlite3

conn = sqlite3.connect("trades.db")
deleted = conn.execute("DELETE FROM trades WHERE tf='market'").rowcount
conn.commit()
conn.close()
print(f"✅ Ho rimosso {deleted} trade(s) con tf='market'.")
