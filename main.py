#!/usr/bin/env python3
"""
Telegram Bot - Anonymous Messages
Sends all messages to admin
"""

import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from flask import Flask
from threading import Thread
import requests
import time

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [6114745287, 1301888151]  # Main and secondary admin

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set in environment variables")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN, default=types.BotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Flask app for keep-alive
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is active!", 200

def run_flask():
    """Run Flask server in background"""
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

def start_flask():
    """Start Flask in a daemon thread"""
    thread = Thread(target=run_flask, daemon=True)
    thread.start()
    logger.info("Flask server started on port 5000")

def self_ping():
    """Keep-alive ping every 4 minutes"""
    def ping_loop():
        while True:
            try:
                time.sleep(240)  # 4 minutes
                try:
                    response = requests.get("http://0.0.0.0:5000", timeout=10)
                    logger.info(f"✅ Self-ping successful: {response.status_code}")
                except Exception as e:
                    logger.warning(f"Self-ping failed: {e}")
            except Exception as e:
                logger.error(f"Ping loop error: {e}")
                time.sleep(60)
    
    thread = Thread(target=ping_loop, daemon=True)
    thread.start()

# Bot handlers
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    """Handle /start command"""
    try:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📝 Send Message")]],
            resize_keyboard=True
        )
        await message.answer(
            f"👋 Welcome! Send me any message and I'll forward it to admin.\n\n"
            f"Your ID: <code>{message.from_user.id}</code>",
            reply_markup=keyboard
        )
        logger.info(f"User {message.from_user.id} started bot")
    except Exception as e:
        logger.error(f"Error in start_handler: {e}")

@dp.message(Command("stats"))
async def stats_handler(message: types.Message):
    """Handle /stats command (admin only)"""
    try:
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("❌ You don't have permission to use this command")
            return
        
        await message.answer("📊 Bot is running normally")
        logger.info(f"Admin {message.from_user.id} requested stats")
    except Exception as e:
        logger.error(f"Error in stats_handler: {e}")

@dp.message()
async def message_handler(message: types.Message):
    """Handle all messages - forward to admin"""
    try:
        # Don't process messages from admin
        if message.from_user.id in ADMIN_IDS:
            return
        
        # Create message text with sender info
        sender_info = (
            f"<b>📨 New Message</b>\n\n"
            f"<b>From:</b> {message.from_user.first_name or 'Unknown'}\n"
            f"<b>Username:</b> @{message.from_user.username or 'N/A'}\n"
            f"<b>ID:</b> <code>{message.from_user.id}</code>\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"<b>Message:</b>\n{message.text or '[No text]'}"
        )
        
        # Send to all admins
        for admin_id in ADMIN_IDS:
            try:
                # Send info message
                await bot.send_message(
                    admin_id,
                    sender_info,
                    parse_mode=ParseMode.HTML
                )
                
                # Send anonymous message
                await bot.send_message(
                    admin_id,
                    f"<b>Анонимное сообщение:</b>\n\n{message.text or '[No text]'}",
                    parse_mode=ParseMode.HTML
                )
                
                logger.info(f"Message from {message.from_user.id} sent to admin {admin_id}")
            except Exception as e:
                logger.error(f"Failed to send message to admin {admin_id}: {e}")
        
        # Send confirmation to user
        await message.answer("✅ Your message has been sent to admin!")
        
    except Exception as e:
        logger.error(f"Error in message_handler: {e}")
        try:
            await message.answer("❌ Error processing message. Please try again.")
        except:
            pass

async def main():
    """Main function to start the bot"""
    try:
        logger.info("🤖 Bot starting...")
        
        # Start Flask server
        start_flask()
        
        # Start self-ping
        self_ping()
        
        # Start polling
        logger.info("✅ Bot is running!")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Startup error: {e}")
        time.sleep(10)

