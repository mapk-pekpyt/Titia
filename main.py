import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from config import BOT_TOKEN, ADMIN_ID
from database import init_db

logging.basicConfig(level=logging.INFO)

if not BOT_TOKEN:
    logging.error("Не указан BOT_TOKEN!")
    exit(1)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

init_db()

@dp.message_handler(commands=['start', 'help'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    
    if user_id == ADMIN_ID:
        # АДМИН меню
        from keyboards import admin_main_kb
        await message.answer("👑 Админ-панель", reply_markup=admin_main_kb)
    else:
        # ПОЛЬЗОВАТЕЛЬ меню
        from keyboards import user_main_kb
        import sqlite3
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (id, username, full_name) VALUES (?, ?, ?)',
                      (user_id, message.from_user.username, message.from_user.full_name))
        conn.commit()
        conn.close()
        await message.answer("Привет! Выберите действие:", reply_markup=user_main_kb)

# Регистрируем остальные обработчики
from handlers import admin, user

async def on_startup(dp):
    admin.register_admin_handlers(dp)
    user.register_user_handlers(dp)
    logging.info("Бот запущен")
    try:
        await bot.send_message(ADMIN_ID, "🤖 Бот запущен!")
    except:
        pass

if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)