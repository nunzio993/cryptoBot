import sqlite3

conn = sqlite3.connect("trades.db")
conn.execute("""
CREATE TABLE IF NOT EXISTS telegram_subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT NULL,
    enabled BOOLEAN DEFAULT 1
);
""")
conn.commit()
conn.close()

print("✅ Tabella telegram_subscribers creata con successo.")
