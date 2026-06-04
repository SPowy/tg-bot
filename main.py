import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode, ChatType
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from flask import Flask
from threading import Thread
import requests
import time

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN required")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=types.BotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
app = Flask(__name__)

BIRTHDAYS_FILE = "birthdays.json"

def load_birthdays():
    if os.path.exists(BIRTHDAYS_FILE):
        with open(BIRTHDAYS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_birthdays(data):
    with open(BIRTHDAYS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

birthdays = load_birthdays()

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

def get_days_until_birthday(date_str):
    try:
        birth_date = datetime.strptime(date_str, "%d.%m")
        today = datetime.now()
        this_year = birth_date.replace(year=today.year)
        
        if this_year < today:
            this_year = birth_date.replace(year=today.year + 1)
        
        days = (this_year - today).days
        return days
    except:
        return None

def format_birthdays_list(group_id):
    if str(group_id) not in birthdays:
        return "Нет добавленных дней рождения"
    
    group_bdays = birthdays[str(group_id)]
    if not group_bdays:
        return "Нет добавленных дней рождения"
    
    lines = ["📅 <b>Дни рождения в группе:</b>\n"]
    
    sorted_bdays = sorted(
        group_bdays.items(),
        key=lambda x: get_days_until_birthday(x[1]) or 999
    )
    
    for name, date in sorted_bdays:
        days = get_days_until_birthday(date)
        if days is not None:
            if days == 0:
                lines.append(f"🎉 <b>{name}</b> - <b>СЕГОДНЯ!</b> ({date})")
            elif days == 1:
                lines.append(f"🎂 <b>{name}</b> - завтра! ({date})")
            else:
                lines.append(f"📆 <b>{name}</b> - через {days} дней ({date})")
    
    return "\n".join(lines)

@dp.message(CommandStart())
async def start(msg: types.Message):
    if msg.chat.type == ChatType.PRIVATE:
        await msg.answer(
            "👋 Привет! Я <b>Эльза Абдрахманова</b>\n\n"
            "Я помогаю отслеживать дни рождения в группе!\n\n"
            "<b>Команды:</b>\n"
            "/add_birthday <имя> <дата> - добавить день рождения (формат: 01.01)\n"
            "/birthdays - показать все дни рождения\n"
            "/remove_birthday <имя> - удалить день рождения\n\n"
            "Добавьте меня в группу и я буду напоминать о днях рождения каждый день в 1:00 ночи!"
        )
    else:
        await msg.answer(
            "👋 Привет! Я <b>Эльза Абдрахманова</b>!\n\n"
            "Я буду напоминать вам о днях рождения каждый день в 1:00 ночи 🎂"
        )

@dp.message(Command("add_birthday"))
async def add_birthday(msg: types.Message):
    try:
        parts = msg.text.split(maxsplit=2)
        if len(parts) < 3:
            await msg.answer("Использование: /add_birthday <имя> <дата>\nПример: /add_birthday Иван 15.03")
            return
        
        name = parts[1]
        date = parts[2]
        
        if not date or len(date.split(".")) != 2:
            await msg.answer("Неверный формат даты! Используйте ДД.МММ (например: 15.03)")
            return
        
        group_id = str(msg.chat.id)
        if group_id not in birthdays:
            birthdays[group_id] = {}
        
        birthdays[group_id][name] = date
        save_birthdays(birthdays)
        
        await msg.answer(f"✅ День рождения <b>{name}</b> ({date}) добавлен!")
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.answer("❌ Ошибка при добавлении дня рождения")

@dp.message(Command("birthdays"))
async def show_birthdays(msg: types.Message):
    try:
        group_id = str(msg.chat.id)
        text = format_birthdays_list(group_id)
        await msg.answer(text)
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.answer("❌ Ошибка")

@dp.message(Command("remove_birthday"))
async def remove_birthday(msg: types.Message):
    try:
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            await msg.answer("Использование: /remove_birthday <имя>")
            return
        
        name = parts[1]
        group_id = str(msg.chat.id)
        
        if group_id in birthdays and name in birthdays[group_id]:
            del birthdays[group_id][name]
            save_birthdays(birthdays)
            await msg.answer(f"✅ День рождения <b>{name}</b> удален")
        else:
            await msg.answer(f"❌ День рождения <b>{name}</b> не найден")
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.answer("❌ Ошибка")

@dp.message()
async def handle(msg: types.Message):
    await msg.answer("Используйте команды: /add_birthday, /birthdays, /remove_birthday")

async def daily_reminder():
    while True:
        try:
            now = datetime.now()
            if now.hour == 1 and now.minute == 0:
                for group_id in birthdays.keys():
                    try:
                        text = format_birthdays_list(int(group_id))
                        await bot.send_message(int(group_id), f"🌙 <b>Напоминание о днях рождения:</b>\n\n{text}")
                    except Exception as e:
                        logger.error(f"Failed to send reminder to {group_id}: {e}")
                
                await asyncio.sleep(60)
            else:
                await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Reminder error: {e}")
            await asyncio.sleep(60)

async def main():
    try:
        logger.info("Bot starting...")
        
        asyncio.create_task(daily_reminder())
        
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

