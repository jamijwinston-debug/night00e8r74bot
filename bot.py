import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List
import random

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, ConversationHandler, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from dotenv import load_dotenv

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
SETTING_REMINDER_TIME, SETTING_REMINDER_TEXT = range(2)

# Store reminders and auto-reply messages
user_reminders: Dict[int, List[Dict]] = {}
user_auto_reply: Dict[int, str] = {}

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

# Initialize scheduler
scheduler = AsyncIOScheduler()

# Auto-reply messages (50 predefined responses)
AUTO_REPLY_RESPONSES = [
    "Thanks for your message! I'll get back to you soon. 😊",
    "Hello! I'm currently unavailable, but I'll respond as soon as possible.",
    "Hi there! Thanks for reaching out. I'll reply shortly.",
    "I've received your message and will respond shortly. 📩",
    "Thank you for contacting me. I'll be with you in a moment.",
    "Hey! I'm away from my keyboard right now, but I'll reply soon.",
    "Thanks for your patience. I'll respond to your message shortly.",
    "Hello! Your message has been received. I'll get back to you soon.",
    "I'm currently busy but will respond to your message as soon as I can.",
    "Thanks for getting in touch! I'll reply to your message shortly.",
    "Hi! I've received your message and will respond when I'm available.",
    "Your message has been delivered. I'll get back to you soon!",
    "Thanks for reaching out! I'll respond to your message shortly.",
    "Hello! I'm currently occupied but will reply to your message soon.",
    "I've received your message and will get back to you as soon as possible.",
    "Thanks for your message! I'll respond when I'm available.",
    "Hi there! I'm away at the moment but will reply to your message soon.",
    "Your message has been received. Thanks for your patience!",
    "Hello! I'll respond to your message as soon as I can.",
    "Thanks for contacting me! I'll get back to you shortly.",
    "I'm currently unavailable but will respond to your message soon.",
    "Hi! I've received your message and will reply shortly.",
    "Thanks for your message! I'll be with you in a moment.",
    "Hello! I'm busy right now but will respond to your message soon.",
    "I've received your message. Thanks for reaching out!",
    "Hi there! I'll get back to you as soon as I can.",
    "Thanks for your message! I'll respond when I'm free.",
    "Hello! I'm currently away but will reply to your message shortly.",
    "I've received your message and will respond soon. Thank you!",
    "Thanks for contacting me! I'll reply to your message shortly.",
    "Hi! I'm occupied at the moment but will get back to you soon.",
    "Your message has been delivered. I'll respond as soon as possible.",
    "Thanks for reaching out! I'll reply when I'm available.",
    "Hello! I've received your message and will respond shortly.",
    "I'm currently busy but will reply to your message as soon as I can.",
    "Thanks for your message! I'll get back to you soon.",
    "Hi there! I'm away from my device but will respond shortly.",
    "Your message has been received. I'll reply soon!",
    "Thanks for contacting me! I'll respond when I'm free.",
    "Hello! I'm currently unavailable but will reply to your message soon.",
    "I've received your message. Thanks for your patience!",
    "Hi! I'll get back to you as soon as I'm available.",
    "Thanks for your message! I'll respond shortly.",
    "Hello! I'm busy at the moment but will reply to your message soon.",
    "I've received your message and will get back to you shortly.",
    "Thanks for reaching out! I'll respond as soon as I can.",
    "Hi there! I'm currently away but will reply to your message soon.",
    "Your message has been delivered. I'll respond shortly!",
    "Thanks for contacting me! I'll get back to you soon.",
    "Hello! I've received your message and will reply when I'm available.",
    "I'm currently occupied but will respond to your message shortly. Thank you!"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message and instructions."""
    welcome_text = """
🤖 Welcome to Auto Reply & Reminder Bot!

I can help you with:
• Auto-replying to messages with predefined responses
• Setting reminders for 5min, 10min, 30min, or 1h

Available commands:
/start - Show this help message
/help - Show list of commands
/remind - Set a new reminder
/list - List all your active reminders
/cancel - Cancel all reminders
/autoreply - Set auto-reply message
/disableautoreply - Disable auto-reply

To set a reminder, use /remind or click the button below!
    """
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information."""
    help_text = """
📋 Available Commands:

/start - Show welcome message and instructions
/help - Show this help message
/remind - Set a new reminder (5min, 10min, 30min, 1h)
/list - List all your active reminders
/cancel - Cancel all your reminders
/autoreply - Set auto-reply message
/disableautoreply - Disable auto-reply

Examples:
/remind 5min Call John
/autoreply I'm busy right now, will reply soon!
    """
    await update.message.reply_text(help_text)

async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the reminder setting process."""
    user_id = update.effective_user.id
    
    if len(context.args) >= 2:
        # If reminder time and text are provided as command arguments
        time_arg = context.args[0].lower()
        reminder_text = ' '.join(context.args[1:])
        
        # Validate time argument
        if time_arg not in REMINDER_TIMES and time_arg not in ['5m', '10m', '30m', '1h']:
            await update.message.reply_text(
                "Invalid time format. Please use: 5min, 10min, 30min, or 1h"
            )
            return ConversationHandler.END
        
        # Normalize time format
        time_mapping = {'5m': '5min', '10m': '10min', '30m': '30min', '1h': '1h'}
        time_choice = time_mapping.get(time_arg, time_arg)
        
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
        
        # Schedule the reminder using APScheduler
        job_id = f"reminder_{user_id}_{reminder_time.timestamp()}"
        scheduler.add_job(
            send_reminder,
            DateTrigger(run_date=reminder_time),
            args=[user_id, reminder_text],
            id=job_id
        )
        
        await update.message.reply_text(
            f"✅ Reminder set! I'll remind you in {time_choice}:\n\"{reminder_text}\""
        )
        
        return ConversationHandler.END
    else:
        # If no arguments provided, start interactive setup
        await update.message.reply_text(
            "Please choose reminder time:",
            reply_markup=reply_markup
        )
        return SETTING_REMINDER_TIME

async def set_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store reminder time and ask for reminder text."""
    time_choice = update.message.text
    
    if time_choice not in REMINDER_TIMES:
        await update.message.reply_text(
            "Please choose a valid time option from the keyboard.",
            reply_markup=reply_markup
        )
        return SETTING_REMINDER_TIME
    
    context.user_data['reminder_time'] = time_choice
    await update.message.reply_text(
        "Great! Now please send me the reminder text:",
        reply_markup=ReplyKeyboardRemove()
    )
    return SETTING_REMINDER_TEXT

async def set_reminder_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the reminder with the provided text."""
    user_id = update.effective_user.id
    reminder_text = update.message.text
    time_choice = context.user_data.get('reminder_time')
    
    if not time_choice:
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
    
    # Schedule the reminder using APScheduler
    job_id = f"reminder_{user_id}_{reminder_time.timestamp()}"
    scheduler.add_job(
        send_reminder,
        DateTrigger(run_date=reminder_time),
        args=[user_id, reminder_text],
        id=job_id
    )
    
    await update.message.reply_text(
        f"✅ Reminder set! I'll remind you in {time_choice}:\n\"{reminder_text}\""
    )
    
    return ConversationHandler.END

async def send_reminder(user_id: int, reminder_text: str):
    """Send reminder to user."""
    try:
        # Send the reminder
        await application.bot.send_message(
            chat_id=user_id,
            text=f"⏰ Reminder: {reminder_text}"
        )
        
        # Remove the reminder from the list
        if user_id in user_reminders:
            user_reminders[user_id] = [
                r for r in user_reminders[user_id] 
                if r['text'] != reminder_text
            ]
    except Exception as e:
        logger.error(f"Error sending reminder to user {user_id}: {e}")

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

async def cancel_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel all reminders for the user."""
    user_id = update.effective_user.id
    
    if user_id in user_reminders and user_reminders[user_id]:
        # Remove all jobs for this user
        jobs = scheduler.get_jobs()
        for job in jobs:
            if job.id.startswith(f"reminder_{user_id}_"):
                scheduler.remove_job(job.id)
        
        count = len(user_reminders[user_id])
        user_reminders[user_id] = []
        await update.message.reply_text(f"✅ All {count} reminders cancelled!")
    else:
        await update.message.reply_text("You have no reminders to cancel.")

async def set_auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set auto-reply message."""
    if len(context.args) > 0:
        auto_reply_text = ' '.join(context.args)
        user_id = update.effective_user.id
        user_auto_reply[user_id] = auto_reply_text
        await update.message.reply_text(f"✅ Auto-reply set to: {auto_reply_text}")
    else:
        await update.message.reply_text(
            "Please provide an auto-reply message. Example: /autoreply I'm busy right now, I'll get back to you soon."
        )

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
    else:
        # Send a random predefined response
        response = random.choice(AUTO_REPLY_RESPONSES)
        await update.message.reply_text(response)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the current operation."""
    await update.message.reply_text(
        "Operation cancelled.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by Updates."""
    logger.error(f"Exception while handling an update: {context.error}")

def main():
    """Start the bot."""
    global application
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")
        return
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add conversation handler for reminders
    reminder_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('remind', set_reminder)],
        states={
            SETTING_REMINDER_TIME: [
                MessageHandler(filters.Regex('^(5min|10min|30min|1h)$'), set_reminder_time)
            ],
            SETTING_REMINDER_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_reminder_text)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(reminder_conv_handler)
    application.add_handler(CommandHandler('list', list_reminders))
    application.add_handler(CommandHandler('cancel', cancel_reminders))
    application.add_handler(CommandHandler('autoreply', set_auto_reply))
    application.add_handler(CommandHandler('disableautoreply', disable_auto_reply))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)

    # Start the scheduler
    scheduler.start()
    
    # Start the Bot with polling (for Background Worker)
    print("Bot is running with polling...")
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == '__main__':
    main()
