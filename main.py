import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ParseMode
from aiogram.utils import executor
from aiogram.dispatcher.filters import Command
from config import BOT_TOKEN, ADMIN_ID
from database import init_db
import handlers.admin as admin_handlers
import handlers.user as user_handlers

logging.basicConfig(level=logging.INFO)

if not BOT_TOKEN:
    logging.error("Не указан BOT_TOKEN!")
    exit(1)

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

init_db()

@dp.message_handler(Command('start', 'help'))
async def global_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        from keyboards import admin_main_kb
        await message.answer("👑 Админ-панель", reply_markup=admin_main_kb)
    else:
        from keyboards import user_main_kb
        conn = __import__('sqlite3').connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (id, username, full_name) VALUES (?, ?, ?)',
                      (message.from_user.id, message.from_user.username, message.from_user.full_name))
        conn.commit()
        conn.close()
        await message.answer("Привет! Выберите действие:", reply_markup=user_main_kb)

async def on_startup(dp):
    admin_handlers.register_admin_handlers(dp)
    user_handlers.register_user_handlers(dp)
    logging.info("Бот запущен")
    try:
        await bot.send_message(ADMIN_ID, "🤖 Бот запущен!")
    except:
        pass

if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup)