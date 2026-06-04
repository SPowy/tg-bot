#!/usr/bin/env python3
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

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [6114745287, 1301888151]

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=types.BotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is active!", 200

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

def start_flask():
    thread = Thread(target=run_flask, daemon=True)
    thread.start()
    logger.info("Flask started")

def self_ping():
    def ping_loop():
        while True:
            try:
                time.sleep(240)
                try:
                    response = requests.get("http://0.0.0.0:5000", timeout=10)
                    logger.info(f"Ping: {response.status_code}")
                except Exception as e:
                    logger.warning(f"Ping failed: {e}")
            except Exception as e:
                logger.error(f"Ping error: {e}")
                time.sleep(60)
    
    thread = Thread(target=ping_loop, daemon=True)
    thread.start()

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    try:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Send Message")]],
            resize_keyboard=True
        )
        await message.answer(f"Welcome! Your ID: {message.from_user.id}", reply_markup=keyboard)
        logger.info(f"User {message.from_user.id} started")
    except Exception as e:
        logger.error(f"Start error: {e}")

@dp.message(Command("stats"))
async def stats_handler(message: types.Message):
    try:
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("No permission")
            return
        await message.answer("Bot running")
    except Exception as e:
        logger.error(f"Stats error: {e}")

@dp.message()
async def message_handler(message: types.Message):
    try:
        if message.from_user.id in ADMIN_IDS:
            return
        
        text = f"From: {message.from_user.first_name}\nID: {message.from_user.id}\n\n{message.text or 'No text'}"
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
                logger.info(f"Sent to {admin_id}")
            except Exception as e:
                logger.error(f"Send error: {e}")
        
        await message.answer("Sent!")
    except Exception as e:
        logger.error(f"Message error: {e}")

async def main():
    try:
        logger.info("Bot starting...")
        start_flask()
        self_ping()
        logger.info("Bot running!")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Fatal: {e}")
        raise
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped")
    except Exception as e:
        logger.error(f"Error: {e}")
        time.sleep(10)

