#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
import json
import threading
import re
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
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
last_button_press: dict = {}

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Дни рождения")],
        [KeyboardButton(text="➕ Добавить"), KeyboardButton(text="❌ Удалить")],
        [KeyboardButton(text="🔮 Гороскоп"), KeyboardButton(text="🎲 Кто сегодня?")],
        [KeyboardButton(text="👤 Об авторе")],
    ],
    resize_keyboard=True,
    persistent=True,
)

# ДД.ММ или ДД.ММ.ГГГГ, опционально заметка после
DATE_RE = re.compile(r"^\d{2}\.\d{2}(\.\d{4})?$")

# Гифки для поздравления
BIRTHDAY_GIFS = [
    "https://media.giphy.com/media/g5R9dok94mrIvplmZd/giphy.gif",
    "https://media.giphy.com/media/artj92V8o75VPL7AeQ/giphy.gif",
    "https://media.giphy.com/media/3oEjI5VtIhHvK37WYo/giphy.gif",
    "https://media.giphy.com/media/Zk9mW5OmXTz9e/giphy.gif",
    "https://media.giphy.com/media/l0HlBO7eyXzSZkJri/giphy.gif",
]

# Случайные поздравления
CONGRATS = [
    "Пусть этот день будет самым ярким в году! 🌟",
    "Желаем море улыбок и океан счастья! 🌊😊",
    "Пусть все мечты сбываются! ✨🎯",
    "Здоровья, счастья и побольше подарков! 🎁💝",
    "Пусть каждый день будет лучше предыдущего! 🚀",
    "Столько счастья, сколько звёзд на небе! ⭐",
    "Пусть жизнь будет сладкой как торт! 🎂",
]

# Гороскопы по знакам зодиака
ZODIAC = {
    "Козерог":   ((12, 22), (1, 19)),
    "Водолей":   ((1, 20), (2, 18)),
    "Рыбы":      ((2, 19), (3, 20)),
    "Овен":      ((3, 21), (4, 19)),
    "Телец":     ((4, 20), (5, 20)),
    "Близнецы":  ((5, 21), (6, 20)),
    "Рак":       ((6, 21), (7, 22)),
    "Лев":       ((7, 23), (8, 22)),
    "Дева":      ((8, 23), (9, 22)),
    "Весы":      ((9, 23), (10, 22)),
    "Скорпион":  ((10, 23), (11, 21)),
    "Стрелец":   ((11, 22), (12, 21)),
}

ZODIAC_EMOJI = {
    "Козерог": "♑", "Водолей": "♒", "Рыбы": "♓", "Овен": "♈",
    "Телец": "♉", "Близнецы": "♊", "Рак": "♋", "Лев": "♌",
    "Дева": "♍", "Весы": "♎", "Скорпион": "♏", "Стрелец": "♐",
}

HOROSCOPES = [
    "Сегодня звёзды благоволят тебе — удача на твоей стороне! 🌟",
    "Отличный день для новых начинаний. Действуй смело! 🚀",
    "Береги энергию — она понадобится для важных дел. ⚡",
    "Сегодня стоит уделить время близким людям. ❤️",
    "Финансовая удача улыбается тебе сегодня! 💰",
    "Твоя интуиция сегодня особенно остра — доверяй ей. 🔮",
    "День принесёт неожиданные приятные сюрпризы! 🎁",
    "Сосредоточься на главном — результат превзойдёт ожидания. 🎯",
    "Отличный день для общения и новых знакомств. 🤝",
    "Звёзды советуют немного отдохнуть и набраться сил. 😴",
]

def get_zodiac(date_str: str) -> str | None:
    try:
        parts = date_str.split('.')
        day, month = int(parts[0]), int(parts[1])
        for sign, ((m1, d1), (m2, d2)) in ZODIAC.items():
            if (month == m1 and day >= d1) or (month == m2 and day <= d2):
                return sign
        return None
    except:
        return None

def days_until(date_str: str):
    try:
        now = datetime.now()
        parts = date_str.split('.')
        if len(parts) >= 2:
            bday = datetime.strptime(f"{parts[0]}.{parts[1]}.{now.year}", "%d.%m.%Y")
        else:
            return None, False
        if bday.date() < now.date():
            bday = bday.replace(year=now.year + 1)
        if bday.date() == now.date():
            return 0, True
        return (bday.date() - now.date()).days, False
    except Exception:
        return None, False

def get_age(date_str: str) -> int | None:
    try:
        parts = date_str.split('.')
        if len(parts) == 3:
            born = datetime.strptime(date_str, "%d.%m.%Y")
            today = datetime.now()
            age = today.year - born.year
            if (today.month, today.day) < (born.month, born.day):
                age -= 1
            return age
        return None
    except:
        return None

def format_date_display(date_str: str) -> str:
    parts = date_str.split('.')
    if len(parts) == 3:
        return f"{parts[0]}.{parts[1]}.{parts[2]}"
    return f"{parts[0]}.{parts[1]}"

def birthdays_text(group: dict) -> str:
    if not group:
        return "📭 Список дней рождения пуст."
    entries = []
    for name, info in group.items():
        if isinstance(info, str):
            date, note = info, ""
        else:
            date = info.get("date", "")
            note = info.get("note", "")
        d, is_today = days_until(date)
        entries.append((d if d is not None else 999, is_today, name, date, note))
    entries.sort(key=lambda x: x[0])
    lines = ["🎂 <b>Дни рождения:</b>\n"]
    for d, is_today, name, date, note in entries:
        display = format_date_display(date)
        age = get_age(date)
        zodiac = get_zodiac(date)
        age_str = f", {age} лет" if age else ""
        zodiac_str = f" {ZODIAC_EMOJI.get(zodiac, '')}" if zodiac else ""
        note_str = f" — <i>{note}</i>" if note else ""
        if is_today:
            lines.append(f"🎉 <b>{name}</b> — {display}{age_str}{zodiac_str} (СЕГОДНЯ!){note_str}")
        elif d == 1:
            lines.append(f"🔥 <b>{name}</b> — {display}{age_str}{zodiac_str} (завтра!){note_str}")
        elif d is not None:
            lines.append(f"🎈 {name} — {display}{age_str}{zodiac_str} (через {d} дн.){note_str}")
        else:
            lines.append(f"📅 {name} — {display}{zodiac_str}{note_str}")
    return "\n".join(lines)

def is_spam(chat_id: int, user_id: int) -> bool:
    now = datetime.now().timestamp()
    key = f"{chat_id}:{user_id}"
    last = last_button_press.get(key, 0)
    if now - last < 3:
        return True
    last_button_press[key] = now
    return False

# ─── Handlers ────────────────────────────────────────────────────────────────

@dp.message(F.new_chat_members)
async def on_bot_added(message: types.Message):
    try:
        bot_info = await bot.get_me()
        for member in message.new_chat_members:
            if member.id == bot_info.id:
                await message.answer(
                    "👋 Привет! Меня зовут <b>Эльза Абдрахманова</b> 🎀\n\n"
                    "Я слежу за днями рождения в этой группе и напоминаю каждую ночь 🌙\n\n"
                    "Используй кнопки ниже! 🎂",
                    reply_markup=MAIN_KB,
                )
                return
    except Exception as e:
        logger.error(f"on_bot_added error: {e}")

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Меня зовут <b>Эльза Абдрахманова</b> 🎀\n\n"
        "Я помогаю не забывать дни рождения! 🎂\n\n"
        "Используй кнопки ниже:",
        reply_markup=MAIN_KB,
    )

@dp.message(F.text == "📅 Дни рождения")
async def btn_list(message: types.Message):
    if is_spam(message.chat.id, message.from_user.id):
        await message.answer("не спамь дура, с первого раза поняла 🙄")
        return
    pending.pop(message.chat.id, None)
    group = DATA.get(str(message.chat.id), {})
    await message.answer(birthdays_text(group), reply_markup=MAIN_KB)

@dp.message(F.text == "➕ Добавить")
async def btn_add(message: types.Message):
    if is_spam(message.chat.id, message.from_user.id):
        await message.answer("не спамь дура, с первого раза поняла 🙄")
        return
    pending[message.chat.id] = "add"
    await message.answer(
        "✏️ Напиши имя, дату и (необязательно) заметку:\n\n"
        "<b>Имя ДД.ММ</b>\n"
        "<b>Имя ДД.ММ.ГГГГ</b>\n"
        "<b>Имя ДД.ММ.ГГГГ заметка</b>\n\n"
        "Примеры:\n"
        "<code>Эльза 05.03</code>\n"
        "<code>Эльза 05.03.2000</code>\n"
        "<code>Эльза 05.03.2000 духи</code>",
        reply_markup=ReplyKeyboardRemove(),
    )

@dp.message(F.text == "❌ Удалить")
async def btn_remove(message: types.Message):
    if is_spam(message.chat.id, message.from_user.id):
        await message.answer("не спамь дура, с первого раза поняла 🙄")
        return
    pending[message.chat.id] = "remove"
    await message.answer(
        "✏️ Напиши имя человека которого нужно удалить:",
        reply_markup=ReplyKeyboardRemove(),
    )

@dp.message(F.text == "🔮 Гороскоп")
async def btn_horoscope(message: types.Message):
    if is_spam(message.chat.id, message.from_user.id):
        await message.answer("не спамь дура, с первого раза поняла 🙄")
        return
    pending.pop(message.chat.id, None)

    # Ищем дату рождения этого пользователя в группе
    group = DATA.get(str(message.chat.id), {})
    user_name = message.from_user.first_name or ""
    found_date = None
    found_name = None

    for name, info in group.items():
        date = info.get("date") if isinstance(info, dict) else info
        # Ищем совпадение по имени (нечувствительно к регистру)
        if user_name.lower() in name.lower() or name.lower() in user_name.lower():
            found_date = date
            found_name = name
            break

    if found_date:
        zodiac = get_zodiac(found_date)
        if zodiac:
            horoscope = random.choice(HOROSCOPES)
            emoji = ZODIAC_EMOJI.get(zodiac, "🔮")
            await message.answer(
                f"{emoji} <b>{zodiac}</b> — гороскоп для {found_name} на сегодня:\n\n"
                f"{horoscope}",
                reply_markup=MAIN_KB,
            )
            return

    # Если не нашли — просим написать дату
    pending[message.chat.id] = "horoscope"
    await message.answer(
        "🔮 Напиши свою дату рождения чтобы узнать гороскоп:\n\n"
        "Формат: <b>ДД.ММ</b> или <b>ДД.ММ.ГГГГ</b>\n"
        "Пример: <code>05.03</code>",
        reply_markup=ReplyKeyboardRemove(),
    )

@dp.message(F.text == "🎲 Кто сегодня?")
async def btn_who_today(message: types.Message):
    if is_spam(message.chat.id, message.from_user.id):
        await message.answer("не спамь дура, с первого раза поняла 🙄")
        return
    pending.pop(message.chat.id, None)
    group = DATA.get(str(message.chat.id), {})
    if not group:
        await message.answer("📭 Список пуст — некого тыкать 😅", reply_markup=MAIN_KB)
        return
    name = random.choice(list(group.keys()))
    phrases = [
        f"🎲 Сегодня виновник торжества — <b>{name}</b>! 🎉",
        f"🎯 Палец судьбы указывает на <b>{name}</b>! 👆",
        f"⚡ Звёзды выбрали <b>{name}</b> — поздравляем! 🌟",
        f"🎪 Барабанная дробь... 🥁 Сегодня это <b>{name}</b>!",
        f"🃏 Карты говорят — <b>{name}</b> сегодня особенный человек! ✨",
    ]
    await message.answer(random.choice(phrases), reply_markup=MAIN_KB)

@dp.message(F.text == "👤 Об авторе")
async def btn_about(message: types.Message):
    if is_spam(message.chat.id, message.from_user.id):
        await message.answer("не спамь дура, с первого раза поняла 🙄")
        return
    pending.pop(message.chat.id, None)
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Страница ВКонтакте", url="https://vk.ru/elza.abdrakhmanova")]
    ])
    await message.answer(
        "👤 <b>Об авторе</b>\n\n"
        "Этот бот создан <b>Эльзой Абдрахмановой</b> 🎀\n\n"
        "Нажми кнопку ниже чтобы перейти на мою страницу:",
        reply_markup=inline_kb,
    )

@dp.message(F.text)
async def handle_text(message: types.Message):
    chat_id = message.chat.id
    state = pending.get(chat_id)

    if state == "add":
        pending.pop(chat_id, None)
        # Парсим: имя дата [заметка]
        parts = message.text.strip().split()
        if len(parts) < 2:
            await message.answer(
                "❌ Неверный формат.\nПример: <code>Эльза 05.03.2000 духи</code>",
                reply_markup=MAIN_KB,
            )
            return

        # Ищем дату среди слов
        date_idx = None
        for i, p in enumerate(parts):
            if DATE_RE.match(p):
                date_idx = i
                break

        if date_idx is None:
            await message.answer(
                "❌ Не нашёл дату. Формат: <b>ДД.ММ</b> или <b>ДД.ММ.ГГГГ</b>\n"
                "Пример: <code>Эльза 05.03.2000 духи</code>",
                reply_markup=MAIN_KB,
            )
            return

        name = " ".join(parts[:date_idx]).strip()
        date_str = parts[date_idx]
        note = " ".join(parts[date_idx+1:]).strip()

        if not name:
            await message.answer("❌ Имя не может быть пустым.", reply_markup=MAIN_KB)
            return

        try:
            p = date_str.split('.')
            if len(p) == 3:
                datetime.strptime(date_str, "%d.%m.%Y")
            else:
                datetime.strptime(f"{date_str}.2000", "%d.%m.%Y")
        except ValueError:
            await message.answer("❌ Неверная дата. Проверь день и месяц.", reply_markup=MAIN_KB)
            return

        cid = str(chat_id)
        if cid not in DATA:
            DATA[cid] = {}
        DATA[cid][name] = {"date": date_str, "note": note}
        save_data()

        d, is_today = days_until(date_str)
        display = format_date_display(date_str)
        zodiac = get_zodiac(date_str)
        zodiac_str = f" {ZODIAC_EMOJI.get(zodiac, '')} {zodiac}" if zodiac else ""
        note_str = f"\n📝 Заметка: {note}" if note else ""

        if is_today:
            await message.answer(
                f"🎉 Сохранено и сегодня же ДР у <b>{name}</b>! 🎂{zodiac_str}{note_str}",
                reply_markup=MAIN_KB,
            )
        else:
            suffix = f"через {d} дн." if d is not None else ""
            await message.answer(
                f"✅ Добавлено: <b>{name}</b> — {display}{zodiac_str}"
                + (f" ({suffix})" if suffix else "")
                + note_str,
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

    elif state == "horoscope":
        pending.pop(chat_id, None)
        date_str = message.text.strip()
        if not DATE_RE.match(date_str):
            await message.answer(
                "❌ Неверный формат. Используй <b>ДД.ММ</b>\nПример: <code>05.03</code>",
                reply_markup=MAIN_KB,
            )
            return
        zodiac = get_zodiac(date_str)
        if zodiac:
            horoscope = random.choice(HOROSCOPES)
            emoji = ZODIAC_EMOJI.get(zodiac, "🔮")
            await message.answer(
                f"{emoji} <b>{zodiac}</b> — твой гороскоп на сегодня:\n\n{horoscope}",
                reply_markup=MAIN_KB,
            )
        else:
            await message.answer("❌ Не удалось определить знак зодиака.", reply_markup=MAIN_KB)

    else:
        await message.answer("Используй кнопки ниже 👇", reply_markup=MAIN_KB)

# ─── Напоминание и поздравления ───────────────────────────────────────────────
async def reminder_loop():
    congratulated: set = set()
    reminded: set = set()
    while True:
        try:
            now = datetime.now()
            day_key = now.strftime("%Y-%m-%d")

            # В 00:00 — поздравления с гифкой
            if now.hour == 0 and now.minute == 0 and day_key not in congratulated:
                congratulated = {day_key}
                for chat_id, group in DATA.items():
                    for name, info in group.items():
                        date = info.get("date") if isinstance(info, dict) else info
                        _, is_today = days_until(date)
                        if is_today:
                            try:
                                congrats = random.choice(CONGRATS)
                                gif_url = random.choice(BIRTHDAY_GIFS)
                                await bot.send_animation(
                                    int(chat_id),
                                    animation=gif_url,
                                    caption=f"🎉🎂 <b>С ДНЕМ РОЖДЕНИЯ, {name}!</b> 🎂🎉\n\n{congrats}"
                                )
                            except Exception as e:
                                logger.error(f"Ошибка поздравления {chat_id}: {e}")
                                try:
                                    await bot.send_message(
                                        int(chat_id),
                                        f"🎉🎂 <b>С ДНЕМ РОЖДЕНИЯ, {name}!</b> 🎂🎉\n\n{random.choice(CONGRATS)}"
                                    )
                                except:
                                    pass
                await asyncio.sleep(61)
                continue

            # В 01:00 — напоминание о всех ДР
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
