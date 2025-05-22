# src/telegram_notifications.py
import sys
import os
import sqlite3
import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from models import SessionLocal, ChatSubscription

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
DB_PATH   = os.getenv("DB_PATH", "trades.db")

def get_user_chat_ids(user_id):
    session = SessionLocal()
    rows = session.query(ChatSubscription).filter_by(user_id=user_id).all()
    session.close()
    return [row.chat_id for row in rows]

def _send_message_sync(chat_id, text, parse_mode=None):
    """
    Invia sincronamente un messaggio a un singolo chat_id.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bot = Bot(token=BOT_TOKEN)
        return loop.run_until_complete(
            bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        )
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")

def get_all_chat_ids():
    """
    Legge la tabella telegram_subscribers e restituisce i chat_id abilitati.
    """
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("SELECT chat_id FROM telegram_subscribers WHERE enabled=1")
    rows = cur.fetchall()
    conn.close()
    return [int(row[0]) for row in rows]

def broadcast(text, parse_mode=None):
    """
    Manda il testo a tutti gli iscritti in telegram_subscribers.
    """
    for chat_id in get_all_chat_ids():
        print(f"📤 invio a chat_id: {chat_id}")
        _send_message_sync(chat_id, text, parse_mode)

def notify_open(order):
    msg = (
        "🟢 *Apertura ordine*\n"
        f"Simbolo: `{order.symbol}`\n"
        f"Quantità: {order.quantity}\n"
        f"Prezzo di entrata: {order.entry_price}\n"
    )
    for chat_id in get_user_chat_ids(order.user_id):
        _send_message_sync(chat_id, msg, parse_mode=ParseMode.MARKDOWN)

def notify_close(order):
    # ... costruisci msg come prima ...
    for chat_id in get_user_chat_ids(order.user_id):
        _send_message_sync(chat_id, msg, parse_mode=ParseMode.MARKDOWN)

