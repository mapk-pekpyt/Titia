import os
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
        from handlers.admin import admin_start
        await admin_start(message)
    else:
        from handlers.user import user_start
        await user_start(message)

async def on_startup(dp):
    admin_handlers.register_admin_handlers(dp)
    user_handlers.register_user_handlers(dp)
    
    logging.info("Бот запущен")
    try:
        await bot.send_message(ADMIN_ID, "🤖 Бот запущен!")
    except:
        pass

async def on_shutdown(dp):
    logging.info("Бот остановлен")

if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)