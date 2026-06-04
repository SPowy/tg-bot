#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
import json
import threading
import re
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from dotenv import load_dotenv
from flask import Flask

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logger.error("BOT_TOKEN не найден!")
    sys.exit(1)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

BIRTHDAYS_FILE = "birthdays.json"

def load_data() -> dict:
    try:
        if os.path.exists(BIRTHDAYS_FILE):
            with open(BIRTHDAYS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")
    return {}

def save_data():
    try:
        with open(BIRTHDAYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(DATA, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

DATA: dict = load_data()
pending: dict = {}

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Дни рождения")],
        [KeyboardButton(text="➕ Добавить"), KeyboardButton(text="❌ Удалить")],
    ],
    resize_keyboard=True,
    persistent=True,
)

DATE_RE = re.compile(r"^\d{2}\.\d{2}$")

def days_until(date_str: str):
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
    if not group:
        return "📭 Список дней рождения пуст."
    entries = []
    for name, date in group.items():
        d, is_today = days_until(date)
        entries.append((d if d is not None else 999, is_today, name, date))
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

@dp.message(F.new_chat_members)
async def on_bot_added(message: types.Message):
    try:
        bot_info = await bot.get_me()
        for member in message.new_chat_members:
            if member.id == bot_info.id:
                await message.answer(
                    "👋 Привет! Меня зовут <b>Эльза Абдрахманова</b> 🎀\n\n"
                    "Я слежу за днями рождения в этой группе и напоминаю каждую ночь в 01:00 🌙\n\n"
                    "Используй кнопки ниже! Для работы бота нужно отвечать на его сообщения выделяя их  🎂",
                    reply_markup=MAIN_KB,
                )
                return
    except Exception as e:
        logger.error(f"on_bot_added error: {e}")

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Меня зовут <b>Эльза Абдрахманова</b> 🎀\n\n"
        "Я помогаю не забывать дни рождения! Для работы отвечай на мои сообщения 🎂\n\n"
        "Используй кнопки ниже:",
        reply_markup=MAIN_KB,
    )

@dp.message(F.text == "📅 Дни рождения")
async def btn_list(message: types.Message):
    pending.pop(message.chat.id, None)
    group = DATA.get(str(message.chat.id), {})
    await message.answer(birthdays_text(group), reply_markup=MAIN_KB)

@dp.message(F.text == "➕ Добавить")
async def btn_add(message: types.Message):
    pending[message.chat.id] = "add"
    await message.answer(
        "✏️ Напиши имя и дату в формате:\n"
        "<b>Имя ДД.ММ</b>\n\n"
        "Пример: <code>Эльза 05.03</code>",
        reply_markup=ReplyKeyboardRemove(),
    )

@dp.message(F.text == "❌ Удалить")
async def btn_remove(message: types.Message):
    pending[message.chat.id] = "remove"
    await message.answer(
        "✏️ Напиши имя человека которого нужно удалить:",
        reply_markup=ReplyKeyboardRemove(),
    )

@dp.message(F.text)
async def handle_text(message: types.Message):
    chat_id = message.chat.id
    state = pending.get(chat_id)

    if state == "add":
        pending.pop(chat_id, None)
        parts = message.text.strip().rsplit(" ", 1)
        if len(parts) != 2 or not DATE_RE.match(parts[1]):
            await message.answer(
                "❌ Неверный формат. Используй: <b>Имя ДД.ММ</b>\n"
                "Пример: <code>Эльза 05.03</code>",
                reply_markup=MAIN_KB,
            )
            return
        name, date_str = parts[0].strip(), parts[1].strip()
        if not name:
            await message.answer("❌ Имя не может быть пустым.", reply_markup=MAIN_KB)
            return
        try:
            datetime.strptime(f"{date_str}.2000", "%d.%m.%Y")
        except ValueError:
            await message.answer("❌ Неверная дата. Проверь день и месяц.", reply_markup=MAIN_KB)
            return
        cid = str(chat_id)
        if cid not in DATA:
            DATA[cid] = {}
        DATA[cid][name] = date_str
        save_data()
        d, is_today = days_until(date_str)
        if is_today:
            await message.answer(f"🎉 Сохранено и сегодня же ДР у <b>{name}</b>! 🎂", reply_markup=MAIN_KB)
        else:
            suffix = f"через {d} дн." if d is not None else ""
            await message.answer(
                f"✅ Добавлено: <b>{name}</b> — {date_str}" + (f" ({suffix})" if suffix else ""),
                reply_markup=MAIN_KB,
            )

    elif state == "remove":
        pending.pop(chat_id, None)
        name = message.text.strip()
        cid = str(chat_id)
        group = DATA.get(cid, {})
        if name in group:
            del group[name]
            DATA[cid] = group
            save_data()
            await message.answer(f"✅ <b>{name}</b> удалён из списка.", reply_markup=MAIN_KB)
        else:
            await message.answer(
                f"❌ Имя <b>{name}</b> не найдено.\nПроверь написание (регистр важен).",
                reply_markup=MAIN_KB,
            )
    else:
        await message.answer("Используй кнопки ниже 👇", reply_markup=MAIN_KB)

async def reminder_loop():
    congratulated: set = set()
    reminded: set = set()
    while True:
        try:
            now = datetime.now()
            day_key = now.strftime("%Y-%m-%d")

            if now.hour == 0 and now.minute == 0 and day_key not in congratulated:
                congratulated = {day_key}
                for chat_id, group in DATA.items():
                    for name, date in group.items():
                        _, is_today = days_until(date)
                        if is_today:
                            try:
                                await bot.send_message(
                                    int(chat_id),
                                    f"🎉🎂 <b>С ДНЕМ РОЖДЕНИЯ, {name}!</b> 🎂🎉\n\n"
                                    f"Желаем счастья, здоровья и всего самого лучшего! ✨🥳"
                                )
                            except Exception as e:
                                logger.error(f"Ошибка поздравления {chat_id}: {e}")
                await asyncio.sleep(61)
                continue

            if now.hour == 1 and now.minute == 0 and day_key not in reminded:
                reminded = {day_key}
                for chat_id, group in DATA.items():
                    try:
                        if not group:
                            continue
                        await bot.send_message(
                            int(chat_id),
                            "🌙 <b>Ежедневное напоминание</b>\n\n" + birthdays_text(group)
                        )
                    except Exception as e:
                        logger.error(f"Ошибка напоминания {chat_id}: {e}")
                await asyncio.sleep(61)
                continue

            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"reminder_loop error: {e}")
            await asyncio.sleep(60)

# ─── Flask keep-alive чтобы Railway не усыплял контейнер ─────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "OK", 200

def run_flask():
    port = int(os.getenv("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False)

async def main():
    logger.info("🚀 Эльза Абдрахманова запускается...")
    bot_info = await bot.get_me()
    logger.info(f"✅ Бот запущен: @{bot_info.username}")
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
