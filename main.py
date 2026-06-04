#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
import json
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logger.error("BOT_TOKEN не найден!")
    sys.exit(1)

ADMIN_IDS = [6114745287, 1301888151]

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

SUBSCRIBERS_FILE = "subscribers.json"
BIRTHDAYS_FILE = "birthdays.json"

def load_subscribers():
    try:
        if os.path.exists(SUBSCRIBERS_FILE):
            with open(SUBSCRIBERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get('users', [])), data.get('last_reminder', None)
        return set(), None
    except Exception as e:
        logger.error(f"Ошибка загрузки подписчиков: {e}")
        return set(), None

def save_subscribers():
    try:
        with open(SUBSCRIBERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'users': list(subscribed_users), 'last_reminder': last_reminder_date}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения подписчиков: {e}")

subscribed_users, last_reminder_date = load_subscribers()

def load_birthdays():
    try:
        if os.path.exists(BIRTHDAYS_FILE):
            with open(BIRTHDAYS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Ошибка загрузки дней рождения: {e}")
        return {}

def save_birthdays(data):
    try:
        with open(BIRTHDAYS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения дней рождения: {e}")

birthdays_data = load_birthdays()

def calculate_days_until_birthday(birthday_str):
    try:
        if len(birthday_str.split('.')) == 3:
            birthday = datetime.strptime(birthday_str, "%d.%m.%Y")
        else:
            birthday = datetime.strptime(f"{birthday_str}.2000", "%d.%m.%Y")
        now = datetime.now()
        next_birthday = birthday.replace(year=now.year)
        if next_birthday < now:
            next_birthday = next_birthday.replace(year=now.year + 1)
        if now.date() == next_birthday.date():
            return 0, 24 - now.hour, True
        time_until = next_birthday - now
        return time_until.days, time_until.seconds // 3600, False
    except Exception as e:
        logger.error(f"Ошибка расчета дней до ДР: {e}")
        return None, None, False

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Подписаться"), KeyboardButton(text="❌ Отписаться")],
        [KeyboardButton(text="📊 Статус"), KeyboardButton(text="👤 Об авторе")],
        [KeyboardButton(text="🎂 День рождения"), KeyboardButton(text="✉️ Анонимка")],
    ],
    resize_keyboard=True
)

BUTTON_TEXTS = [
    "✅ Подписаться", "❌ Отписаться", "📊 Статус",
    "👤 Об авторе", "🥰 Чернопопый", "🎂 День рождения", "✉️ Анонимка"
]

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    try:
        await message.answer(
            "👋 Привет! Я бот для анонимных сообщений.\n\n"
            "🔸 Можешь подписаться на уведомления о подарках\n"
            "🔸 Написать анонимное сообщение администратору\n"
            "🔸 Узнать информацию об авторе\n\n"
            "Просто выбери действие из меню ниже 👇",
            reply_markup=keyboard
        )
        logger.info(f"Пользователь {message.from_user.id} запустил бота")
    except Exception as e:
        logger.error(f"Ошибка в cmd_start: {e}")

@dp.message(lambda m: m.text == "✅ Подписаться")
async def subscribe(message: types.Message):
    try:
        subscribed_users.add(message.chat.id)
        save_subscribers()
        await message.answer("🎉 Теперь ты будешь получать уведомления!", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в subscribe: {e}")

@dp.message(lambda m: m.text == "❌ Отписаться")
async def unsubscribe(message: types.Message):
    try:
        subscribed_users.discard(message.chat.id)
        save_subscribers()
        await message.answer("❌ Ты отписался от уведомлений.", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в unsubscribe: {e}")

@dp.message(lambda m: m.text == "📊 Статус")
async def status(message: types.Message):
    try:
        user_status = "✅ Подписан" if message.chat.id in subscribed_users else "❌ Не подписан"
        await message.answer(f"🟢 Бот работает!\nВаш статус: {user_status}", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в status: {e}")

@dp.message(lambda m: m.text == "👤 Об авторе")
async def about(message: types.Message):
    try:
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Написать автору", url="tg://resolve?domain=evenchee")]
        ])
        await message.answer("Об авторе\nДолбаеб: @evenchee", reply_markup=inline_kb)
    except Exception as e:
        logger.error(f"Ошибка в about: {e}")

@dp.message(lambda m: m.text == "🎂 День рождения")
async def birthday_handler(message: types.Message):
    try:
        user_id = str(message.from_user.id)
        if user_id in birthdays_data:
            birthday_str = birthdays_data[user_id]
            days_until, hours_until, is_today = calculate_days_until_birthday(birthday_str)
            if is_today:
                text = f"🎉 <b>С ДНЕМ РОЖДЕНИЯ!</b> 🎂\n\nТвой день рождения: {birthday_str}"
            elif days_until is not None:
                time_text = f"{days_until} дней {hours_until} часов" if days_until > 1 else f"1 день {hours_until} часов" if days_until == 1 else f"менее {24-(hours_until or 0)} часов"
                text = (
                    f"🎂 <b>Твой день рождения</b>\n\n"
                    f"📅 Дата: {birthday_str}\n"
                    f"⏰ До дня рождения: <b>{time_text}</b>\n\n"
                    f"Чтобы изменить дату, напиши новую в формате ДД.ММ.ГГГГ"
                )
            else:
                text = "❌ Ошибка в формате даты. Напиши заново в формате ДД.ММ.ГГГГ"
        else:
            text = (
                "🎂 <b>Система дня рождения</b>\n\n"
                "📝 <b>Формат даты:</b>\n"
                "• <b>ДД.ММ.ГГГГ</b> (например: 15.07.1995)\n"
                "• <b>ДД.ММ</b> (например: 15.07)\n\n"
                "Напиши свой день рождения следующим сообщением 👇"
            )
        await message.answer(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в birthday_handler: {e}")

@dp.message(lambda m: m.text == "✉️ Анонимка")
async def ask_anonymous(message: types.Message):
    try:
        await message.answer("✏️ Напиши сообщение", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка в ask_anonymous: {e}")

@dp.message(lambda m: m.from_user and m.from_user.id in ADMIN_IDS and m.text == "/stats")
async def admin_stats(message: types.Message):
    try:
        await message.answer(
            f"📊 Статистика бота:\n\n"
            f"👥 Подписчиков: {len(subscribed_users)}\n"
            f"🎂 Дней рождения: {len(birthdays_data)}\n"
            f"🤖 Бот работает!"
        )
    except Exception as e:
        logger.error(f"Ошибка в admin_stats: {e}")

@dp.message()
async def handle_all_messages(message: types.Message):
    try:
        if not message.text or not message.from_user:
            return
        if message.text in BUTTON_TEXTS:
            return
        if message.from_user.id in ADMIN_IDS:
            return

        # Проверяем дату рождения
        if '.' in message.text:
            parts = message.text.strip().split('.')
            if len(parts) in [2, 3] and all(p.isdigit() for p in parts):
                birthday_str = message.text.strip()
                days_until, hours_until, is_today = calculate_days_until_birthday(birthday_str)
                if days_until is not None:
                    user_id = str(message.from_user.id)
                    birthdays_data[user_id] = birthday_str
                    save_birthdays(birthdays_data)
                    if is_today:
                        resp = f"🎉 <b>С ДНЕМ РОЖДЕНИЯ!</b>\n✅ Дата сохранена: {birthday_str}"
                    else:
                        time_text = f"{days_until} дней {hours_until} часов"
                        resp = f"✅ <b>День рождения сохранен!</b>\n📅 Дата: {birthday_str}\n⏰ До дня рождения: <b>{time_text}</b>"
                    await message.answer(resp, reply_markup=keyboard)
                    return
                else:
                    await message.answer("❌ Неправильный формат даты!\n\nИспользуй: <b>ДД.ММ.ГГГГ</b> или <b>ДД.ММ</b>", reply_markup=keyboard)
                    return

        # Пересылаем анонимное сообщение админам
        username = f"@{message.from_user.username}" if message.from_user.username else "без username"
        user_id = message.from_user.id
        full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
        text = str(message.text)[:4000]

        info_text = (
            f"📩 <b>Новое анонимное сообщение:</b>\n\n"
            f"<i>{text}</i>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>От:</b> {username}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"📝 <b>Имя:</b> {full_name}"
        )
        forward_text = f"📤 <b>Анонимное сообщение:</b>\n\n{text}"

        delivered = 0
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=info_text)
                await asyncio.sleep(0.3)
                await bot.send_message(chat_id=admin_id, text=forward_text)
                delivered += 1
            except Exception as e:
                logger.error(f"Ошибка отправки админу {admin_id}: {e}")

        if delivered > 0:
            await message.answer("✅ Сообщение доставлено!", reply_markup=keyboard)
        else:
            await message.answer("⚠️ Сообщение принято, могут быть задержки.", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Критическая ошибка в handle_all_messages: {e}")
        try:
            await message.answer("✅ Сообщение принято!", reply_markup=keyboard)
        except:
            pass

async def birthday_loop():
    """Фоновая задача для поздравлений и напоминаний"""
    while True:
        try:
            now = datetime.now()
            bdays = load_birthdays()

            if now.hour == 0 and now.minute == 0:
                for uid, bday in bdays.items():
                    try:
                        _, _, is_today = calculate_days_until_birthday(bday)
                        if is_today:
                            await bot.send_message(
                                int(uid),
                                "🎉🎂 <b>С ДНЕМ РОЖДЕНИЯ!</b> 🎂🎉\n\nЖелаем счастья, здоровья и исполнения всех желаний! ✨",
                                reply_markup=keyboard
                            )
                    except Exception as e:
                        logger.error(f"Ошибка поздравления {uid}: {e}")
                await asyncio.sleep(61)

            elif now.hour == 6 and now.minute == 0:
                for uid, bday in bdays.items():
                    try:
                        days, hours, is_today = calculate_days_until_birthday(bday)
                        if not is_today and days is not None:
                            time_text = f"{days} дней {hours} часов"
                            await bot.send_message(
                                int(uid),
                                f"🎂 Доброе утро! ☀️\n\n📅 Твой день рождения: {bday}\n⏰ До праздника: <b>{time_text}</b>",
                                reply_markup=keyboard
                            )
                    except Exception as e:
                        logger.error(f"Ошибка напоминания {uid}: {e}")
                await asyncio.sleep(61)
            else:
                await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Ошибка в birthday_loop: {e}")
            await asyncio.sleep(60)

async def main():
    logger.info("🚀 Бот запускается...")
    logger.info(f"🔧 Админы: {ADMIN_IDS}")

    bot_info = await bot.get_me()
    logger.info(f"✅ Подключено: @{bot_info.username}")

    asyncio.create_task(birthday_loop())

    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
