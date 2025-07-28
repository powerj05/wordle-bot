import os
import logging
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
import json
import sys
from dotenv import load_dotenv
from boto3 import resource
from boto3.dynamodb.conditions import Attr, Key
from datetime import datetime, date, timedelta

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
WEBAPP_URL = os.environ.get("WEBAPP_URL")

scores_table = resource('dynamodb').Table('WordleScores')
tournaments_table = resource('dynamodb').Table('WordleTournaments')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Received /start from user {update.effective_user.id}")
    await update.message.reply_text("Bot is running after reboot!")

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Received /play from user {update.effective_user.id}")
    webapp = WebAppInfo(url=WEBAPP_URL)
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

            table_item = {
                'user_id' : str(user_id),
                'date' : date.today().isoformat(),
                'score' : score
            }

            http_response = scores_table.put_item(Item = table_item)
            logging.info(f"Insert response: {http_response}")

            if score > 6:
                score = 'X'

            response = (
                f"🏁 Game Over!\n\n"
                f"Secret Word: {secret_word}\n"
                f"Your Score: {score}/6\n"
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

ASK_START_DATE, ASK_DAYS = range(2)

# Entry point: ask for start date
async def start_create_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"Entering start_create_tournament")
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ You can only create tournaments in a group chat.")
        return ConversationHandler.END

    # Save user ID to chat_data to enforce user ownership if needed
    context.chat_data['creator_id'] = update.effective_user.id

    await update.message.reply_text(
        "📅 When should the tournament start?\nPlease enter a date in YYYY-MM-DD format (e.g., 2025-08-01)."
    )
    return ASK_START_DATE

# Handle start date input
async def receive_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"receive_start_date triggered with input: {update.message.text}")
    text = update.message.text.strip()
    logging.info(f"receive_start_date called with input: {text}")

    try:
        parsed_date = datetime.strptime(text, "%Y-%m-%d").date()
        if parsed_date < date.today():
            await update.message.reply_text("❌ Start date can't be in the past. Try again.")
            return ASK_START_DATE

        context.chat_data['start_date'] = parsed_date
        await update.message.reply_text("🗓️ How many days should the tournament run? (1–30)")
        return ASK_DAYS
    except ValueError:
        await update.message.reply_text("❌ Invalid date format. Use YYYY-MM-DD.")
        return ASK_START_DATE

    except ValueError:
        await update.message.reply_text("Invalid date format. Use YYYY-MM-DD.")
        return ASK_START_DATE

# Handle number of days input
async def receive_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    logging.info(f"receive_start_date called with input: {text}")


    try:
        days = int(update.message.text.strip())
        if not (1 <= days <= 30):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a number between 1 and 30.")
        return ASK_DAYS

    user = update.effective_user
    chat = update.effective_chat
    start_date = context.chat_data['start_date']
    end_date = start_date + timedelta(days=days - 1)

    # Save to DynamoDB
    tournaments_table.put_item(Item={
        'chat_id': str(chat.id),
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'participants': [user.id],
        'created_by': user.id,
    })

    await update.message.reply_text(
        f"✅ Tournament created!\n\n"
        f"Start: {start_date}\nEnd: {end_date}\nCreated by: {user.first_name}"
    )
    return ConversationHandler.END

# Cancel fallback
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tournament creation cancelled.")
    return ConversationHandler.END

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # if in group chat and tournament exists for group chat
    # add user to participants
    chat = update.effective_chat
    user = update.effective_user
    chat_id = str(chat.id)

    if chat.type not in ['group','supergroup']:
        await update.message.reply_text(
            "Must be in a group chat to join a tournament.",
            reply_to_message_id=update.message.message_id
        )
        return

    try:
        response = tournaments_table.get_item(Key={'chat_id':chat_id})
        item = response.get('Item')
        if not item:
            await update.message.reply_text(
                "No active tournament found for this group chat. Use /createtournament to create one.",
                reply_to_message_id=update.message.message_id
            )
            return

        participants = item['participants']

        if user.id in participants:
            await update.message.reply_text(
                f"{user.first_name} is already in this tournament.",
                reply_to_message_id=update.message.message_id
            )
            return

        participants.append(user.id)

        tournaments_table.update_item(
            Key={'chat_id':chat_id},
            UpdateExpression="SET participants = :p",
            ExpressionAttributeValues={':p':participants}
        )

        await update.message.reply_text(
            f"{user.first_name} has joined the tournament! 🎉",
            reply_to_message_id=update.message.message_id
        )

    except Exception as e:
        logging.ERROR(f"Error adding user {user.id} to tournament for chat {chat_id}: {e}")
        await update.message.reply_text(
            "⚠️ An error occurred while trying to join the tournament.",
            reply_to_message_id=update.message.message_id
        )

async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # if in group chat and tournament exists for group chat
    # remove user from participants
    chat = update.effective_chat
    user = update.effective_user
    chat_id = str(chat.id)

    if chat.type not in ['group','supergroup']:
        await update.message.reply_text(
            "Must be in a group chat to leave a tournament.",
            reply_to_message_id=update.message.message_id
        )
        return

    try:
        response = tournaments_table.get_item(Key={'chat_id':chat_id})
        item = response.get('Item')
        if not item:
            await update.message.reply_text(
                "No active tournament found for this group chat. Use /createtournament to create one.",
                reply_to_message_id=update.message.message_id
            )
            return

        participants = item['participants']

        if user.id not in participants:
            await update.message.reply_text(
                f"{user.first_name} is already not in this tournament.",
                reply_to_message_id=update.message.message_id
            )
            return

        participants.remove(user.id)

        tournaments_table.update_item(
            Key={'chat_id':chat_id},
            UpdateExpression="SET participants = :p",
            ExpressionAttributeValues={':p':participants}
        )

        await update.message.reply_text(
            f"{user.first_name} has left the tournament!",
            reply_to_message_id=update.message.message_id
        )

    except Exception as e:
        logging.ERROR(f"Error removing user {user.id} from tournament for chat {chat_id}: {e}")
        await update.message.reply_text(
            "⚠️ An error occurred while trying to leave the tournament.",
            reply_to_message_id=update.message.message_id
        )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_id = str(chat.id)

    if chat.type not in ['group','supergroup']:
        await update.message.reply_text(
            "Must be in a group chat to use this command.",
            reply_to_message_id=update.message.message_id
        )
        return

    try:
        response = tournaments_table.get_item(Key={'chat_id':chat_id})
        item = response.get('Item')
        if not item:
            await update.message.reply_text(
                "No active tournament found for this group chat. Use /createtournament to create one.",
                reply_to_message_id=update.message.message_id
            )
            return
        
        start_date = item['start_date']
        end_date = item['end_date']
        participants = item['participants']
        timediff = date.today()-date.fromisoformat(start_date)
        days_running = timediff.days+1
        leaderboard = []

        if start_date > date.today().isoformat():
            await update.message.reply_text(f"Tournament does not start until {start_date}.")
            return

        for p in participants:
            disp_name = await get_display_name(context.bot,chat_id,p)

            # Fetch today's score
            logging.info(f"Fetching today's score for user {p}.")
            td_score_resp = scores_table.query(
                KeyConditionExpression=Key('user_id').eq(str(p)) &
                                           Key('date').eq(date.today().isoformat()),
            )
            td_score_item = td_score_resp.get('Items', [])
            td_score = td_score_item[0].get('score') if td_score_item else 'NYP'
            logging.info(f"user {p}'s score for today: {td_score}")

            total_score=0
            days_played = 0

            logging.info(f"Fetching all scores for user {p}.")
            score_resp = scores_table.query(
            KeyConditionExpression=Key('user_id').eq(str(p)) &
                                    Key('date').between(start_date, end_date)
            )
            logging.info(f"Fetched scores for user {p}")
            for s in score_resp.get('Items',[]):
                score = s.get('score')
                days_played += 1
                total_score += int(score)
            total_score += 7*(days_running-days_played) # give users a score of 7 for days they didn't play
            
            avg_score = total_score/days_running
            leaderboard.append((disp_name,td_score,avg_score))
        
        leaderboard.sort(key=lambda x:x[2])

        msg = f"Leaderboard for tournament at {date.today().isoformat()} (today's scores shown in brackets):\n\n"
        for rank, (name, tdscore,avg) in enumerate(leaderboard, start=1):
            msg += f"{rank}. {name}: {avg:.2f} ({tdscore})\n"

        await update.message.reply_text(msg, reply_to_message_id=update.message.message_id)

    except Exception as e:
        logging.error(f"Error fetching leaderboard for tournament for chat {chat_id}: {e}")
        await update.message.reply_text(
            "⚠️ An error occurred while trying to fetch the leaderboard.",
            reply_to_message_id=update.message.message_id
        )

async def get_display_name(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.user.username:
            return f"@{member.user.username}"
        else:
            return member.user.first_name
    except:
        return f"User {user_id}"

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("play",play))
    application.add_handler(CommandHandler("join",join))
    application.add_handler(CommandHandler("leave",leave))
    application.add_handler(CommandHandler("leaderboard",leaderboard))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("createtournament",start_create_tournament)],
        states = {
            ASK_START_DATE: [MessageHandler(filters.TEXT, receive_start_date)],
            ASK_DAYS: [MessageHandler(filters.TEXT, receive_days)],
        },
        fallbacks=[CommandHandler("cancel",cancel)],
        per_chat=False,
        per_user=True,
    )

    application.add_handler(conv_handler)

    application.run_webhook(
        listen="0.0.0.0",
        port=8443,
        url_path=f"{BOT_TOKEN}",
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
    )

if __name__ == '__main__':
    main()