import asyncio
import logging
import os
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode, ChatType
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
        try:
            with open(BIRTHDAYS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_birthdays(data):
    try:
        with open(BIRTHDAYS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Save error: {e}")

birthdays = load_birthdays()

@app.route("/")
def home():
    return "OK", 200

def flask_run():
    try:
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
    except:
        pass

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

@dp.my_chat_member()
async def on_bot_added(update: types.ChatMemberUpdated):
    """Срабатывает когда бота добавили в группу"""
    try:
        if update.new_chat_member.status == "member":
            chat_id = update.chat.id
            chat_title = update.chat.title or "группа"
            
            message = (
                f"👋 Привет! Я <b>Эльза Абдрахманова</b>!\n\n"
                f"Я помогаю отслеживать дни рождения в группе.\n\n"
                f"<b>Мои команды:</b>\n"
                f"/add_birthday <имя> <дата> - добавить день рождения\n"
                f"Пример: /add_birthday Иван 15.03\n\n"
                f"/birthdays - показать все дни рождения\n\n"
                f"/remove_birthday <имя> - удалить день рождения\n\n"
                f"Я буду напоминать о днях рождения каждый день в 1:00 ночи! 🎂"
            )
            
            await bot.send_message(chat_id, message)
            logger.info(f"Bot added to group {chat_id}")
    except Exception as e:
        logger.error(f"Error on_bot_added: {e}")

@dp.message(CommandStart())
async def start(msg: types.Message):
    try:
        if msg.chat.type == ChatType.PRIVATE:
            message = (
                "👋 Привет! Я <b>Эльза Абдрахманова</b>\n\n"
                "Я помогаю отслеживать дни рождения в группе!\n\n"
                "<b>Команды:</b>\n"
                "/add_birthday <имя> <дата> - добавить день рождения (формат: 01.01)\n"
                "/birthdays - показать все дни рождения\n"
                "/remove_birthday <имя> - удалить день рождения\n\n"
                "Добавьте меня в группу и я буду напоминать о днях рождения каждый день в 1:00 ночи!"
            )
            await msg.answer(message)
        else:
            message = (
                "👋 Привет! Я <b>Эльза Абдрахманова</b>!\n\n"
                "Я буду напоминать вам о днях рождения каждый день в 1:00 ночи 🎂\n\n"
                "Используйте /add_birthday, /birthdays, /remove_birthday"
            )
            await msg.answer(message)
    except Exception as e:
        logger.error(f"Start error: {e}")

@dp.message(Command("add_birthday"))
async def add_birthday(msg: types.Message):
    try:
        parts = msg.text.split(maxsplit=2)
        if len(parts) < 3:
            await msg.reply("❌ Использование: /add_birthday <имя> <дата>\n\nПример: /add_birthday Иван 15.03")
            return
        
        name = parts[1]
        date = parts[2]
        
        date_parts = date.split(".")
        if len(date_parts) != 2:
            await msg.reply("❌ Неверный формат даты! Используйте ДД.МММ (например: 15.03)")
            return
        
        try:
            day = int(date_parts[0])
            month = int(date_parts[1])
            if day < 1 or day > 31 or month < 1 or month > 12:
                await msg.reply("❌ Неверная дата! День: 1-31, месяц: 1-12")
                return
        except:
            await msg.reply("❌ Неверный формат даты!")
            return
        
        group_id = str(msg.chat.id)
        if group_id not in birthdays:
            birthdays[group_id] = {}
        
        birthdays[group_id][name] = date
        save_birthdays(birthdays)
        
        await msg.reply(f"✅ День рождения <b>{name}</b> ({date}) добавлен!")
        logger.info(f"Added birthday: {name} {date} in group {group_id}")
    except Exception as e:
        logger.error(f"Add birthday error: {e}")
        await msg.reply("❌ Ошибка при добавлении дня рождения")

@dp.message(Command("birthdays"))
async def show_birthdays(msg: types.Message):
    try:
        group_id = str(msg.chat.id)
        text = format_birthdays_list(group_id)
        await msg.reply(text)
        logger.info(f"Showed birthdays for group {group_id}")
    except Exception as e:
        logger.error(f"Show birthdays error: {e}")
        await msg.reply("❌ Ошибка")

@dp.message(Command("remove_birthday"))
async def remove_birthday(msg: types.Message):
    try:
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            await msg.reply("❌ Использование: /remove_birthday <имя>")
            return
        
        name = parts[1]
        group_id = str(msg.chat.id)
        
        if group_id in birthdays and name in birthdays[group_id]:
            del birthdays[group_id][name]
            save_birthdays(birthdays)
            await msg.reply(f"✅ День рождения <b>{name}</b> удален")
            logger.info(f"Removed birthday: {name} from group {group_id}")
        else:
            await msg.reply(f"❌ День рождения <b>{name}</b> не найден")
    except Exception as e:
        logger.error(f"Remove birthday error: {e}")
        await msg.reply("❌ Ошибка")

@dp.message()
async def handle_any_message(msg: types.Message):
    try:
        await msg.reply(
            "Я не понимаю эту команду 😕\n\n"
            "Используйте:\n"
            "/add_birthday <имя> <дата> - добавить день рождения\n"
            "/birthdays - показать все дни рождения\n"
            "/remove_birthday <имя> - удалить день рождения"
        )
    except Exception as e:
        logger.error(f"Handle message error: {e}")

async def daily_reminder():
    """Отправляет напоминание каждый день в 1:00"""
    while True:
        try:
            now = datetime.now()
            if now.hour == 1 and now.minute == 0:
                logger.info("Sending daily reminders...")
                for group_id in list(birthdays.keys()):
                    try:
                        text = format_birthdays_list(int(group_id))
                        message = f"🌙 <b>Напоминание о днях рождения:</b>\n\n{text}"
                        await bot.send_message(int(group_id), message)
                        logger.info(f"Reminder sent to {group_id}")
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
        logger.info("🤖 Bot starting...")
        
        asyncio.create_task(daily_reminder())
        
        logger.info("✅ Bot running!")
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

