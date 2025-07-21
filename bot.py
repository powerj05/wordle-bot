import os
import logging
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import json
import sys
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

load_dotenv()
BOT_USERNAME = os.environ.get("BOT_USERNAME")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("NGROK_URL")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Received /start from user {update.effective_user.id}")
    await update.message.reply_text("Bot is running after reboot!")

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Received /play from user {update.effective_user.id}")
    webapp = WebAppInfo(url="https://powerj05.github.io/wordle-bot/")
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("Play Wordle", web_app=webapp)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    response = "Play today's Wordle here!"

    await update.message.reply_text(response, reply_markup=keyboard)

async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Received data from webapp: {update}")
    if update.message.web_app_data:
        raw_data = update.message.web_app_data.data
        user_id = update.effective_user.id

        try:
            data = json.loads(raw_data)
            score = data.get("score")
            attempts = data.get("attempts")
            secret_word = data.get("secret_word")

            response = (
                f"🏁 Game Over!\n\n"
                f"Secret Word: {secret_word}\n"
                f"Your Score: {score}\n"
                f"Attempts: {attempts}"
            )

            await context.bot.send_message(chat_id=user_id, text=response)

        except Exception as e:
            await context.bot.send_message(chat_id=user_id, text="⚠️ Failed to process game data.")
            print("Error parsing WebApp data:", e)

def handle_response(text: str) -> str:
    return(f"Thanks. We received {text}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_type: str = update.message.chat.type
    text: str = update.message.text

    logging.info(f"User {update.message.chat.id} in {message_type}: {text}")

    if message_type == 'group':
        if BOT_USERNAME in text:
            new_text: str = text.replace(BOT_USERNAME, '').strip()
            response: str = handle_response(new_text)
        else:
            return
    else:
        response: str = handle_response(text)
    
    logging.info(f"Bot: {response}")
    await update.message.reply_text(response)

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("play",play))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_webhook(
        listen="0.0.0.0",
        port=8443,
        url_path=f"{BOT_TOKEN}",
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )

if __name__ == '__main__':
    main()