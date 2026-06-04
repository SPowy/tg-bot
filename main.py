import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from flask import Flask
from threading import Thread
import requests
import time

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN required")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=types.BotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
app = Flask(__name__)

@app.route("/")
def home():
    return "OK", 200

def flask_run():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

Thread(target=flask_run, daemon=True).start()

def ping():
    while True:
        time.sleep(240)
        try:
            requests.get("http://0.0.0.0:5000", timeout=10)
        except:
            pass

Thread(target=ping, daemon=True).start()

@dp.message(CommandStart())
async def start(msg: types.Message):
    await msg.answer("Bot running")

@dp.message()
async def handle(msg: types.Message):
    await msg.answer("OK")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

