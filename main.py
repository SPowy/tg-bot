#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

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
dp = Dispatcher(storage=MemoryStorage())

BIRTHDAYS_FILE = "birthdays.json"

# ── Button labels ──────────────────────────────────────────────────────────────
BTN_SHOW    = "📅 Показать дни рождения"
BTN_ADD     = "➕ Добавить день рождения"
BTN_REMOVE  = "❌ Удалить день рождения"

# ── FSM states ─────────────────────────────────────────────────────────────────
class BirthdayForm(StatesGroup):
    waiting_for_add    = State()   # expecting "Name DD.MM.YYYY"
    waiting_for_remove = State()   # expecting just a name

# ── Main keyboard ──────────────────────────────────────────────────────────────
def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SHOW)],
            [KeyboardButton(text=BTN_ADD), KeyboardButton(text=BTN_REMOVE)],
        ],
        resize_keyboard=True,
        persistent=True,
    )

# ── Структура: { "chat_id": { "user_id": {"name": "Имя", "date": "ДД.ММ.ГГГГ"} } }
def load_birthdays():
    try:
        if os.path.exists(BIRTHDAYS_FILE):
            with open(BIRTHDAYS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")
        return {}

def save_birthdays(data):
    try:
        with open(BIRTHDAYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

birthdays_data = load_birthdays()

def calculate_days_until(birthday_str):
    """Возвращает (дней_до, is_today)"""
    try:
        parts = birthday_str.split('.')
        if len(parts) == 3:
            birthday = datetime.strptime(birthday_str, "%d.%m.%Y")
        else:
            birthday = datetime.strptime(f"{birthday_str}.2000", "%d.%m.%Y")
        now = datetime.now()
        next_bday = birthday.replace(year=now.year)
        if next_bday.date() < now.date():
            next_bday = next_bday.replace(year=now.year + 1)
        if next_bday.date() == now.date():
            return 0, True
        return (next_bday.date() - now.date()).days, False
    except:
        return None, False

def get_chat_birthdays(chat_id):
    return birthdays_data.get(str(chat_id), {})

def set_user_birthday(chat_id, user_id, name, date_str):
    cid = str(chat_id)
    uid = str(user_id)
    if cid not in birthdays_data:
        birthdays_data[cid] = {}
    birthdays_data[cid][uid] = {"name": name, "date": date_str}
    save_birthdays(birthdays_data)

def remove_birthday_by_name(chat_id, name_query: str) -> bool:
    """Remove the first entry whose name matches (case-insensitive). Returns True on success."""
    cid = str(chat_id)
    if cid not in birthdays_data:
        return False
    for uid, info in list(birthdays_data[cid].items()):
        if info["name"].lower() == name_query.strip().lower():
            del birthdays_data[cid][uid]
            save_birthdays(birthdays_data)
            return True
    return False

# ── Helper: build the birthday list text ──────────────────────────────────────
def build_birthday_list(chat_id) -> str:
    chat_bdays = get_chat_birthdays(chat_id)
    if not chat_bdays:
        return (
            "📭 Пока никто не зарегистрировал свой день рождения.\n\n"
            "Нажми <b>➕ Добавить день рождения</b>, чтобы добавить!"
        )
    entries = []
    for uid, info in chat_bdays.items():
        days, is_today = calculate_days_until(info["date"])
        entries.append((days if days is not None else 999, is_today, info["name"], info["date"]))
    entries.sort(key=lambda x: x[0])

    lines = ["🎂 <b>Дни рождения в группе:</b>\n"]
    for days, is_today, name, date in entries:
        if is_today:
            lines.append(f"🎉 <b>{name}</b> — {date} (СЕГОДНЯ!)")
        elif days == 1:
            lines.append(f"🔥 <b>{name}</b> — {date} (завтра!)")
        elif days is not None:
            lines.append(f"🎈 {name} — {date} (через {days} дн.)")
        else:
            lines.append(f"📅 {name} — {date}")
    return "\n".join(lines)

# ── Welcome when bot is added to a group ──────────────────────────────────────
@dp.message(F.new_chat_members)
async def on_bot_added(message: types.Message):
    bot_info = await bot.get_me()
    for member in message.new_chat_members:
        if member.id == bot_info.id:
            await message.answer(
                "👋 Привет всем! Меня зовут <b>Эльза Абдрахманова</b> 🎀\n\n"
                "Я слежу за днями рождения в этой группе и напоминаю о них каждую ночь в 01:00 🌙\n\n"
                "Используй кнопки ниже для управления днями рождения 👇",
                reply_markup=main_keyboard(),
            )
            return

# ── /start ─────────────────────────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Меня зовут <b>Эльза Абдрахманова</b> 🎀\n\n"
        "Я слежу за днями рождения в этой группе!\n\n"
        "Используй кнопки ниже 👇",
        reply_markup=main_keyboard(),
    )

# ── /help ──────────────────────────────────────────────────────────────────────
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📋 <b>Как пользоваться Эльзой:</b>\n\n"
        "Нажми <b>📅 Показать дни рождения</b> — увидишь список.\n"
        "Нажми <b>➕ Добавить день рождения</b> — введи имя и дату.\n"
        "Нажми <b>❌ Удалить день рождения</b> — введи имя.\n\n"
        "📋 <b>Команды:</b>\n"
        "/add_birthday — добавить день рождения\n"
        "/birthdays — список всех дней рождения\n"
        "/remove_birthday — удалить день рождения\n"
        "/birthday ДД.ММ.ГГГГ — зарегистрировать свой ДР\n\n"
        "Каждую ночь в 01:00 я пишу напоминание 🌙",
        reply_markup=main_keyboard(),
    )

# ── /birthday (register own birthday) ─────────────────────────────────────────
@dp.message(Command("birthday"))
async def cmd_set_birthday(message: types.Message):
    try:
        parts = message.text.strip().split()
        if len(parts) < 2:
            await message.reply(
                "❌ Укажи дату!\n"
                "Пример: /birthday 15.07.1995"
            )
            return

        date_str = parts[1].strip()
        days, is_today = calculate_days_until(date_str)

        if days is None:
            await message.reply(
                "❌ Неправильный формат даты!\n"
                "Используй: <b>ДД.ММ.ГГГГ</b>\n"
                "Пример: /birthday 15.07.1995"
            )
            return

        user = message.from_user
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username or "Неизвестно"
        set_user_birthday(message.chat.id, user.id, name, date_str)

        if is_today:
            await message.reply(
                f"🎉 <b>С ДНЕМ РОЖДЕНИЯ, {name}!</b> 🎂\n\n"
                f"Дата сохранена: {date_str} ✅",
                reply_markup=main_keyboard(),
            )
        else:
            await message.reply(
                f"✅ День рождения сохранен!\n\n"
                f"👤 <b>{name}</b>\n"
                f"📅 Дата: {date_str}\n"
                f"⏰ До дня рождения: <b>{days} дней</b>",
                reply_markup=main_keyboard(),
            )

    except Exception as e:
        logger.error(f"Ошибка в cmd_set_birthday: {e}")
        await message.reply("❌ Произошла ошибка, попробуй ещё раз.")

# ── /birthdays command ─────────────────────────────────────────────────────────
@dp.message(Command("birthdays"))
async def cmd_list_birthdays(message: types.Message):
    try:
        await message.reply(build_birthday_list(message.chat.id), reply_markup=main_keyboard())
    except Exception as e:
        logger.error(f"Ошибка в cmd_list_birthdays: {e}")
        await message.reply("❌ Ошибка при загрузке списка.")

# ── /nextbirthday ──────────────────────────────────────────────────────────────
@dp.message(Command("nextbirthday"))
async def cmd_next_birthday(message: types.Message):
    try:
        chat_bdays = get_chat_birthdays(message.chat.id)

        if not chat_bdays:
            await message.reply("📭 Нет зарегистрированных дней рождения.")
            return

        entries = []
        for uid, info in chat_bdays.items():
            days, is_today = calculate_days_until(info["date"])
            if is_today:
                await message.reply(
                    f"🎉 Сегодня день рождения у <b>{info['name']}</b>!\n"
                    f"Поздравляем! 🎂🎊",
                    reply_markup=main_keyboard(),
                )
                return
            if days is not None:
                entries.append((days, info["name"], info["date"]))

        if not entries:
            await message.reply("❌ Не удалось определить следующий ДР.")
            return

        entries.sort()
        days, name, date = entries[0]

        if days == 1:
            await message.reply(
                f"🔥 Завтра день рождения у <b>{name}</b>!\n📅 {date}",
                reply_markup=main_keyboard(),
            )
        else:
            await message.reply(
                f"🎈 Следующий день рождения через <b>{days} дней</b>:\n\n"
                f"👤 <b>{name}</b>\n📅 {date}",
                reply_markup=main_keyboard(),
            )

    except Exception as e:
        logger.error(f"Ошибка в cmd_next_birthday: {e}")
        await message.reply("❌ Ошибка.")

# ══════════════════════════════════════════════════════════════════════════════
# BUTTON HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

# ── 📅 Show birthdays button ───────────────────────────────────────────────────
@dp.message(F.text == BTN_SHOW)
async def btn_show_birthdays(message: types.Message, state: FSMContext):
    await state.clear()
    try:
        await message.answer(build_birthday_list(message.chat.id), reply_markup=main_keyboard())
    except Exception as e:
        logger.error(f"Ошибка в btn_show_birthdays: {e}")
        await message.answer("❌ Ошибка при загрузке списка.")

# ── ➕ Add birthday button — step 1: ask for input ────────────────────────────
@dp.message(F.text == BTN_ADD)
async def btn_add_birthday(message: types.Message, state: FSMContext):
    await state.set_state(BirthdayForm.waiting_for_add)
    await message.answer(
        "✏️ Введи имя и дату рождения в формате:\n\n"
        "<b>Имя ДД.ММ.ГГГГ</b>\n\n"
        "Пример: <code>Анна 15.07.1995</code>\n\n"
        "Или нажми /cancel для отмены.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🚫 Отмена")]],
            resize_keyboard=True,
        ),
    )

# ── ➕ Add birthday — step 2: process "Name DD.MM.YYYY" ───────────────────────
@dp.message(BirthdayForm.waiting_for_add)
async def process_add_birthday(message: types.Message, state: FSMContext):
    text = message.text.strip()

    # Allow cancellation via button or command
    if text in ("🚫 Отмена", "/cancel"):
        await state.clear()
        await message.answer("❌ Добавление отменено.", reply_markup=main_keyboard())
        return

    parts = text.rsplit(" ", 1)  # split on last space so names with spaces work
    if len(parts) != 2:
        await message.answer(
            "❌ Неверный формат. Введи <b>Имя ДД.ММ.ГГГГ</b>\n"
            "Пример: <code>Анна 15.07.1995</code>"
        )
        return

    name, date_str = parts[0].strip(), parts[1].strip()
    days, is_today = calculate_days_until(date_str)

    if days is None:
        await message.answer(
            "❌ Неправильный формат даты!\n"
            "Используй: <b>ДД.ММ.ГГГГ</b>\n"
            "Пример: <code>Анна 15.07.1995</code>"
        )
        return

    # Use a synthetic user_id based on name so multiple people can be added
    synthetic_uid = abs(hash(name)) % (10 ** 9)
    set_user_birthday(message.chat.id, synthetic_uid, name, date_str)
    await state.clear()

    if is_today:
        await message.answer(
            f"🎉 <b>С ДНЕМ РОЖДЕНИЯ, {name}!</b> 🎂\n\n"
            f"Дата сохранена: {date_str} ✅",
            reply_markup=main_keyboard(),
        )
    else:
        await message.answer(
            f"✅ День рождения добавлен!\n\n"
            f"👤 <b>{name}</b>\n"
            f"📅 Дата: {date_str}\n"
            f"⏰ До дня рождения: <b>{days} дней</b>",
            reply_markup=main_keyboard(),
        )

# ── ❌ Remove birthday button — step 1: ask for name ──────────────────────────
@dp.message(F.text == BTN_REMOVE)
async def btn_remove_birthday(message: types.Message, state: FSMContext):
    chat_bdays = get_chat_birthdays(message.chat.id)
    if not chat_bdays:
        await message.answer(
            "📭 Список дней рождения пуст — нечего удалять.",
            reply_markup=main_keyboard(),
        )
        return

    await state.set_state(BirthdayForm.waiting_for_remove)
    names = [info["name"] for info in chat_bdays.values()]
    names_list = "\n".join(f"• {n}" for n in names)
    await message.answer(
        f"🗑 Введи имя человека, чей день рождения нужно удалить:\n\n{names_list}\n\n"
        "Или нажми /cancel для отмены.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🚫 Отмена")]],
            resize_keyboard=True,
        ),
    )

# ── ❌ Remove birthday — step 2: process name ─────────────────────────────────
@dp.message(BirthdayForm.waiting_for_remove)
async def process_remove_birthday(message: types.Message, state: FSMContext):
    text = message.text.strip()

    if text in ("🚫 Отмена", "/cancel"):
        await state.clear()
        await message.answer("❌ Удаление отменено.", reply_markup=main_keyboard())
        return

    if remove_birthday_by_name(message.chat.id, text):
        await state.clear()
        await message.answer(
            f"✅ День рождения <b>{text}</b> удалён.",
            reply_markup=main_keyboard(),
        )
    else:
        await message.answer(
            f"❌ Имя «{text}» не найдено в списке.\n"
            "Проверь написание и попробуй ещё раз, или нажми /cancel для отмены."
        )

# ── /add_birthday command (mirrors button flow) ────────────────────────────────
@dp.message(Command("add_birthday"))
async def cmd_add_birthday(message: types.Message, state: FSMContext):
    await btn_add_birthday(message, state)

# ── /remove_birthday command (mirrors button flow) ─────────────────────────────
@dp.message(Command("remove_birthday"))
async def cmd_remove_birthday(message: types.Message, state: FSMContext):
    await btn_remove_birthday(message, state)

# ── /cancel ────────────────────────────────────────────────────────────────────
@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.", reply_markup=main_keyboard())

# ══════════════════════════════════════════════════════════════════════════════
# DAILY REMINDER LOOP
# ══════════════════════════════════════════════════════════════════════════════

async def birthday_loop():
    congratulated_today = set()
    reminded_today = set()

    while True:
        try:
            now = datetime.now()
            day_key = now.strftime("%Y-%m-%d")

            # В 00:00 — поздравления
            if now.hour == 0 and now.minute == 0:
                if day_key not in congratulated_today:
                    congratulated_today = {day_key}
                    data = load_birthdays()
                    for chat_id, users in data.items():
                        for uid, info in users.items():
                            _, is_today = calculate_days_until(info["date"])
                            if is_today:
                                try:
                                    await bot.send_message(
                                        int(chat_id),
                                        f"🎉🎂 <b>С ДНЕМ РОЖДЕНИЯ, {info['name']}!</b> 🎂🎉\n\n"
                                        f"Желаем счастья, здоровья и всего самого лучшего! ✨🥳"
                                    )
                                except Exception as e:
                                    logger.error(f"Ошибка поздравления чат {chat_id}: {e}")
                await asyncio.sleep(61)
                continue

            # В 01:00 — напоминание о всех ДР
            if now.hour == 1 and now.minute == 0:
                if day_key not in reminded_today:
                    reminded_today = {day_key}
                    data = load_birthdays()
                    for chat_id, users in data.items():
                        try:
                            if not users:
                                continue

                            entries = []
                            for uid, info in users.items():
                                days, is_today = calculate_days_until(info["date"])
                                if not is_today and days is not None:
                                    entries.append((days, info["name"], info["date"]))

                            entries.sort()

                            if not entries:
                                continue

                            lines = ["🌙 <b>Напоминание о днях рождения:</b>\n"]
                            for days, name, date in entries:
                                if days == 1:
                                    lines.append(f"🔥 <b>{name}</b> — завтра! ({date})")
                                elif days <= 7:
                                    lines.append(f"⚠️ <b>{name}</b> — через {days} дн. ({date})")
                                else:
                                    lines.append(f"🎈 {name} — через {days} дн. ({date})")

                            await bot.send_message(int(chat_id), "\n".join(lines))
                        except Exception as e:
                            logger.error(f"Ошибка напоминания чат {chat_id}: {e}")

                await asyncio.sleep(61)
                continue

            await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"Ошибка в birthday_loop: {e}")
            await asyncio.sleep(60)

async def main():
    logger.info("🚀 Эльза Абдрахманова запускается...")
    bot_info = await bot.get_me()
    logger.info(f"✅ Бот запущен: @{bot_info.username}")
    asyncio.create_task(birthday_loop())
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
