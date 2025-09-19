import os
import logging
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, ConversationHandler, filters
)
from dotenv import load_dotenv
import asyncio
from typing import Dict, List

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from environment variable
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Conversation states
SETTING_REMINDER, SETTING_AUTO_REPLY = range(2)

# Store reminders and auto-reply messages
user_reminders: Dict[int, List[Dict]] = {}
user_auto_reply: Dict[int, str] = {}
pending_reminders: Dict[int, List[asyncio.Task]] = {}

# Reminder time options
REMINDER_TIMES = {
    '5min': timedelta(minutes=5),
    '10min': timedelta(minutes=10),
    '30min': timedelta(minutes=30),
    '1h': timedelta(hours=1)
}

# Keyboard for reminder times
reminder_keyboard = [['5min', '10min', '30min', '1h']]
reply_markup = ReplyKeyboardMarkup(reminder_keyboard, one_time_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message and instructions."""
    welcome_text = """
🤖 Welcome to Auto Reply & Reminder Bot!

Available commands:
/start - Show this help message
/setreminder - Set a new reminder
/setautoreply - Set auto-reply message
/listreminders - List all your reminders
/clearreminders - Clear all reminders
/disableautoreply - Disable auto-reply

The bot will remind you at the specified time and auto-reply to messages when enabled.
    """
    await update.message.reply_text(welcome_text)

async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the reminder setting process."""
    user_id = update.effective_user.id
    
    if len(context.args) > 0:
        # If reminder text is provided as command argument
        reminder_text = ' '.join(context.args)
        await update.message.reply_text(
            f"Please choose reminder time:",
            reply_markup=reply_markup
        )
        context.user_data['reminder_text'] = reminder_text
        return SETTING_REMINDER
    else:
        await update.message.reply_text(
            "Please send me the reminder text. Example: /setreminder Call John"
        )
        return SETTING_REMINDER

async def reminder_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store reminder text and ask for time."""
    reminder_text = update.message.text
    context.user_data['reminder_text'] = reminder_text
    
    await update.message.reply_text(
        "Please choose reminder time:",
        reply_markup=reply_markup
    )
    return SETTING_REMINDER

async def set_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the reminder with chosen time."""
    user_id = update.effective_user.id
    time_choice = update.message.text
    
    if time_choice not in REMINDER_TIMES:
        await update.message.reply_text("Please choose a valid time option from the keyboard.")
        return SETTING_REMINDER
    
    reminder_text = context.user_data.get('reminder_text')
    if not reminder_text:
        await update.message.reply_text("Something went wrong. Please try again.")
        return ConversationHandler.END
    
    # Calculate reminder time
    reminder_time = datetime.now() + REMINDER_TIMES[time_choice]
    
    # Store reminder
    if user_id not in user_reminders:
        user_reminders[user_id] = []
    
    reminder_data = {
        'text': reminder_text,
        'time': reminder_time,
        'set_at': datetime.now(),
        'duration': time_choice
    }
    user_reminders[user_id].append(reminder_data)
    
    # Schedule the reminder
    await schedule_reminder(user_id, reminder_data)
    
    await update.message.reply_text(
        f"✅ Reminder set! I'll remind you in {time_choice}:\n\"{reminder_text}\""
    )
    
    return ConversationHandler.END

async def schedule_reminder(user_id: int, reminder_data: Dict):
    """Schedule an asynchronous reminder."""
    delay = (reminder_data['time'] - datetime.now()).total_seconds()
    
    async def send_reminder():
        await asyncio.sleep(delay)
        try:
            # Send the reminder
            await application.bot.send_message(
                chat_id=user_id,
                text=f"⏰ Reminder: {reminder_data['text']}"
            )
            # Remove the reminder from list after sending
            if user_id in user_reminders:
                user_reminders[user_id] = [
                    r for r in user_reminders[user_id] 
                    if r['time'] != reminder_data['time']
                ]
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")
    
    # Store the task to allow cancellation if needed
    task = asyncio.create_task(send_reminder())
    if user_id not in pending_reminders:
        pending_reminders[user_id] = []
    pending_reminders[user_id].append(task)

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all reminders for the user."""
    user_id = update.effective_user.id
    
    if user_id not in user_reminders or not user_reminders[user_id]:
        await update.message.reply_text("You have no active reminders.")
        return
    
    reminders_text = "📋 Your active reminders:\n\n"
    for i, reminder in enumerate(user_reminders[user_id], 1):
        time_left = reminder['time'] - datetime.now()
        minutes_left = max(0, int(time_left.total_seconds() / 60))
        reminders_text += f"{i}. {reminder['text']}\n   ⏰ {minutes_left} minutes left\n\n"
    
    await update.message.reply_text(reminders_text)

async def clear_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all reminders for the user."""
    user_id = update.effective_user.id
    
    if user_id in user_reminders:
        # Cancel pending tasks
        if user_id in pending_reminders:
            for task in pending_reminders[user_id]:
                task.cancel()
            pending_reminders[user_id] = []
        
        user_reminders[user_id] = []
        await update.message.reply_text("✅ All reminders cleared!")
    else:
        await update.message.reply_text("You have no reminders to clear.")

async def set_auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set auto-reply message."""
    if len(context.args) > 0:
        auto_reply_text = ' '.join(context.args)
        user_id = update.effective_user.id
        user_auto_reply[user_id] = auto_reply_text
        await update.message.reply_text(f"✅ Auto-reply set to: {auto_reply_text}")
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "Please send me the auto-reply message. Example: /setautoreply I'm busy right now, I'll get back to you soon."
        )
        return SETTING_AUTO_REPLY

async def auto_reply_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store auto-reply message."""
    auto_reply_text = update.message.text
    user_id = update.effective_user.id
    user_auto_reply[user_id] = auto_reply_text
    
    await update.message.reply_text(f"✅ Auto-reply set to: {auto_reply_text}")
    return ConversationHandler.END

async def disable_auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable auto-reply."""
    user_id = update.effective_user.id
    if user_id in user_auto_reply:
        del user_auto_reply[user_id]
        await update.message.reply_text("✅ Auto-reply disabled!")
    else:
        await update.message.reply_text("Auto-reply was not enabled.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages and send auto-reply if enabled."""
    user_id = update.effective_user.id
    
    # Check if auto-reply is enabled for this user
    if user_id in user_auto_reply:
        auto_reply_text = user_auto_reply[user_id]
        await update.message.reply_text(auto_reply_text)
    
    # You can add more message handling logic here

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the current operation."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

def main():
    """Start the bot."""
    # Create the Application
    global application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add conversation handler for reminders
    reminder_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('setreminder', set_reminder)],
        states={
            SETTING_REMINDER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reminder_text_received),
                MessageHandler(filters.Regex('^(5min|10min|30min|1h)$'), set_reminder_time)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Add conversation handler for auto-reply
    auto_reply_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('setautoreply', set_auto_reply)],
        states={
            SETTING_AUTO_REPLY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, auto_reply_text_received)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(reminder_conv_handler)
    application.add_handler(auto_reply_conv_handler)
    application.add_handler(CommandHandler('listreminders', list_reminders))
    application.add_handler(CommandHandler('clearreminders', clear_reminders))
    application.add_handler(CommandHandler('disableautoreply', disable_auto_reply))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the Bot
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
