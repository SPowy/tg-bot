#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
import json
import threading
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from dotenv import load_dotenv
from flask import Flask
import requests

load_dotenv()

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ─── Bot setup ──────────────────────────────────────────────────────────────
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logger.error("BOT_TOKEN не найден!")
    sys.exit(1)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ─── Data storage ───────────────────────────────────────────────────────────
# Format: { "group_id": { "Name": "DD.MM" } }
BIRTHDAYS_FILE = "birthdays.json"

def load_data() -> dict:
    try:
        if os.path.exists(BIRTHDAYS_FILE):
            with open(BIRTHDAYS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
    return {}

def save_data(data: dict):
    try:
        with open(BIRTHDAYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")

# ─── Simple in-memory state (chat_id -> "add" | "remove") ───────────────────
pending = {}

# ─── Keyboard ───────────────────────────────────────────────────────────────
MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Дни рождения")],
        [KeyboardButton(text="➕ Добавить"), KeyboardButton(text="❌ Удалить")],
    ],
    resize_keyboard=True,
    persistent=True,
)

# ─── Helpers ────────────────────────────────────────────────────────────────
DATE_RE = re.compile(r"^\d{2}\.\d{2}$")

def days_until(date_str: str):
    """Return (days, is_today) for a 'DD.MM' date string, or (None, False) on error."""
    try:
        now = datetime.now()
        bday = datetime.strptime(f"{date_str}.{now.year}", "%d.%m.%Y")
        if bday.date() < now.date():
            bday = bday.replace(year=now.year + 1)
        if bday.date() == now.date():
            return 0, True
        return (bday.date() - now.date()).days, False
    except Exception:
        return None, False

def birthdays_text(group: dict) -> str:
    """Build a sorted birthday list string from a {name: date} dict."""
    if not group:
        return "📭 Список дней рождения пуст."
    entries = []
    for name, date in group.items():
        d, is_today = days_until(date)
        sort_key = d if d is not None else 999
        entries.append((sort_key, is_today, name, date))
    entries.sort(key=lambda x: x[0])
    lines = ["🎂 <b>Дни рождения:</b>\n"]
    for d, is_today, name, date in entries:
        if is_today:
            lines.append(f"🎉 <b>{name}</b> — {date} (СЕГОДНЯ!)")
        elif d == 1:
            lines.append(f"🔥 <b>{name}</b> — {date} (завтра!)")
        elif d is not None:
            lines.append(f"🎈 {name} — {date} (через {d} дн.)")
        else:
            lines.append(f"📅 {name} — {date}")
    return "\n".join(lines)

# ─── Handlers ───────────────────────────────────────────────────────────────

@dp.message(F.new_chat_members)
async def on_bot_added(message: types.Message):
    try:
        bot_info = await bot.get_me()
        for member in message.new_chat_members:
            if member.id == bot_info.id:
                await message.answer(
                    "👋 Привет! Меня зовут <b>Эльза Абдрахманова</b> 🎀\n\n"
                    "Я слежу за днями рождения в этой группе и напоминаю о них каждую ночь в 01:00 🌙\n\n"
                    "Используй кнопки ниже для управления списком! 🎂",
                    reply_markup=MAIN_KB,
                )
                return
    except Exception as e:
        logger.error(f"on_bot_added error: {e}")

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    try:
        await message.answer(
            "👋 Привет! Меня зовут <b>Эльза Абдрахманова</b> 🎀\n\n"
            "Я помогаю не забывать дни рождения! 🎂\n\n"
            "Используй кнопки ниже:",
            reply_markup=MAIN_KB,
        )
    except Exception as e:
        logger.error(f"cmd_start error: {e}")

@dp.message(F.text == "📅 Дни рождения")
async def btn_list(message: types.Message):
    try:
        pending.pop(message.chat.id, None)
        data = load_data()
        group = data.get(str(message.chat.id), {})
        await message.answer(birthdays_text(group), reply_markup=MAIN_KB)
    except Exception as e:
        logger.error(f"btn_list error: {e}")
        await message.answer("❌ Ошибка при загрузке списка.", reply_markup=MAIN_KB)

@dp.message(F.text == "➕ Добавить")
async def btn_add(message: types.Message):
    try:
        pending[message.chat.id] = "add"
        await message.answer(
            "✏️ Напиши имя и дату в формате:\n"
            "<b>Имя ДД.ММ</b>\n\n"
            "Пример: <code>Анна 15.07</code>",
            reply_markup=ReplyKeyboardRemove(),
        )
    except Exception as e:
        logger.error(f"btn_add error: {e}")

@dp.message(F.text == "❌ Удалить")
async def btn_remove(message: types.Message):
    try:
        pending[message.chat.id] = "remove"
        await message.answer(
            "✏️ Напиши имя человека, которого нужно удалить:",
            reply_markup=ReplyKeyboardRemove(),
        )
    except Exception as e:
        logger.error(f"btn_remove error: {e}")

@dp.message(F.text)
async def handle_text(message: types.Message):
    try:
        chat_id = message.chat.id
        state = pending.get(chat_id)

        if state == "add":
            pending.pop(chat_id, None)
            parts = message.text.strip().rsplit(" ", 1)
            if len(parts) != 2 or not DATE_RE.match(parts[1]):
                await message.answer(
                    "❌ Неверный формат. Используй: <b>Имя ДД.ММ</b>\n"
                    "Пример: <code>Анна 15.07</code>",
                    reply_markup=MAIN_KB,
                )
                return
            name, date_str = parts[0].strip(), parts[1].strip()
            if not name:
                await message.answer("❌ Имя не может быть пустым.", reply_markup=MAIN_KB)
                return
            # Validate date values
            try:
                datetime.strptime(f"{date_str}.2000", "%d.%m.%Y")
            except ValueError:
                await message.answer(
                    "❌ Неверная дата. Проверь день и месяц.",
                    reply_markup=MAIN_KB,
                )
                return
            data = load_data()
            cid = str(chat_id)
            if cid not in data:
                data[cid] = {}
            data[cid][name] = date_str
            save_data(data)
            d, is_today = days_until(date_str)
            if is_today:
                await message.answer(
                    f"🎉 Сохранено и сегодня же день рождения у <b>{name}</b>! 🎂",
                    reply_markup=MAIN_KB,
                )
            else:
                suffix = f"через {d} дн." if d is not None else ""
                await message.answer(
                    f"✅ Добавлено: <b>{name}</b> — {date_str}"
                    + (f" ({suffix})" if suffix else ""),
                    reply_markup=MAIN_KB,
                )

        elif state == "remove":
            pending.pop(chat_id, None)
            name = message.text.strip()
            data = load_data()
            cid = str(chat_id)
            group = data.get(cid, {})
            if name in group:
                del group[name]
                data[cid] = group
                save_data(data)
                await message.answer(f"✅ <b>{name}</b> удалён из списка.", reply_markup=MAIN_KB)
            else:
                await message.answer(
                    f"❌ Имя <b>{name}</b> не найдено в списке.\n"
                    "Проверь написание (регистр важен).",
                    reply_markup=MAIN_KB,
                )

        else:
            # No active state — just show the keyboard
            await message.answer("Используй кнопки ниже 👇", reply_markup=MAIN_KB)

    except Exception as e:
        logger.error(f"handle_text error: {e}")
        await message.answer("❌ Произошла ошибка, попробуй ещё раз.", reply_markup=MAIN_KB)

# ─── Daily reminder loop ─────────────────────────────────────────────────────
async def reminder_loop():
    reminded_today: set = set()
    while True:
        try:
            now = datetime.now()
            day_key = now.strftime("%Y-%m-%d")
            if now.hour == 1 and now.minute == 0 and day_key not in reminded_today:
                reminded_today = {day_key}
                data = load_data()
                for chat_id, group in data.items():
                    try:
                        if not group:
                            continue
                        text = birthdays_text(group)
                        await bot.send_message(int(chat_id), "🌙 <b>Ежедневное напоминание</b>\n\n" + text)
                    except Exception as e:
                        logger.error(f"reminder send error chat {chat_id}: {e}")
                await asyncio.sleep(61)
                continue
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"reminder_loop error: {e}")
            await asyncio.sleep(60)

# ─── Keep-alive Flask server ─────────────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "OK", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=5000, use_reloader=False)

def self_ping():
    """Ping self every 5 minutes to prevent Railway from sleeping."""
    url = os.getenv("SELF_URL", "http://localhost:5000")
    while True:
        try:
            requests.get(url, timeout=10)
        except Exception:
            pass
        import time
        time.sleep(300)

# ─── Entry point ─────────────────────────────────────────────────────────────
async def main():
    logger.info("🚀 Эльза Абдрахманова запускается...")
    bot_info = await bot.get_me()
    logger.info(f"✅ Бот запущен: @{bot_info.username}")
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    # Start Flask keep-alive in background threads
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()
    asyncio.run(main())

