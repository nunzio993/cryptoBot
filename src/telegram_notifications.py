# src/telegram_notifications.py
import sys
import os
import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from models import SessionLocal, ChatSubscription

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")

def get_user_chat_ids(user_id):
    with SessionLocal() as session:
        rows = session.query(ChatSubscription).filter_by(user_id=user_id).all()
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
    Restituisce tutti i chat_id abilitati dalla tabella chat_subscriptions (PostgreSQL).
    """
    with SessionLocal() as session:
        rows = session.query(ChatSubscription).filter_by(enabled=True).all()
        return [row.chat_id for row in rows]

def broadcast(text, parse_mode=None):
    """
    Manda il testo a tutti gli iscritti.
    """
    for chat_id in get_all_chat_ids():
        print(f"📤 invio a chat_id: {chat_id}")
        _send_message_sync(chat_id, text, parse_mode)


def notify_open(order, exchange_name=None):
    network = "Testnet 🧪" if getattr(order, 'is_testnet', False) else "Mainnet 🌐"
    exchange = exchange_name.upper() if exchange_name else "N/A"
    msg = (
        "🟢 *Apertura ordine*\n"
        f"Exchange: `{exchange}` ({network})\n"
        f"Simbolo: `{order.symbol}`\n"
        f"Quantità: {order.quantity}\n"
        f"Prezzo di entrata: {order.entry_price}\n"
    )
    for chat_id in get_user_chat_ids(order.user_id):
        _send_message_sync(chat_id, msg, parse_mode=ParseMode.MARKDOWN)

def notify_close(order, exchange_name=None):
    network = "Testnet 🧪" if getattr(order, 'is_testnet', False) else "Mainnet 🌐"
    exchange = exchange_name.upper() if exchange_name else "N/A"
    msg = (
        "🔴 *Chiusura ordine*\n"
        f"Exchange: `{exchange}` ({network})\n"
        f"Simbolo: `{order.symbol}`\n"
        f"Quantità: {order.quantity}\n"
        f"Status: {order.status}\n"
    )
    for chat_id in get_user_chat_ids(order.user_id):
        _send_message_sync(chat_id, msg, parse_mode=ParseMode.MARKDOWN)

