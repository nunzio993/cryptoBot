import os
from dotenv import load_dotenv
load_dotenv()

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from models import SessionLocal, User, ChatSubscription

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message handler for /start command"""
    welcome_message = (
        "👋 Benvenuto nel bot di CryptoBot!\n\n"
        "Questo bot ti invierà notifiche sui tuoi ordini di trading.\n\n"
        "📌 Per collegare il tuo account:\n"
        "1. Vai su orderdash.cloud → Profilo → Telegram\n"
        "2. Copia il codice mostrato\n"
        "3. Inviami: /link <codice>\n\n"
        "Es: /link abc123"
    )
    await update.message.reply_text(welcome_message)


async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = SessionLocal()
    chat_id = str(update.effective_chat.id)
    if len(context.args) != 1:
        await update.message.reply_text("Usa: /link <codice>")
        session.close()
        return

    code = context.args[0]
    user = session.query(User).filter_by(telegram_link_code=code).first()
    if not user:
        await update.message.reply_text("Codice non valido o già usato.")
        session.close()
        return

    # Verifica che non sia già collegato
    existing = session.query(ChatSubscription).filter_by(chat_id=chat_id).first()
    if existing:
        await update.message.reply_text("Questo account Telegram è già collegato.")
        session.close()
        return

    session.add(ChatSubscription(user_id=user.id, chat_id=chat_id))
    # Se vuoi annullare il codice dopo il link (consigliato):
    user.telegram_link_code = None
    session.commit()
    session.close()
    await update.message.reply_text("✅ Telegram collegato al tuo account! Riceverai solo le tue notifiche personali.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("link", link))
    print("Bot avviato. Invia /link <codice> da Telegram per collegarti al sito.")
    app.run_polling(drop_pending_updates=True)

