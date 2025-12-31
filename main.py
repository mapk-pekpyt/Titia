import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ParseMode
from aiogram.utils import executor
from config import BOT_TOKEN, ADMIN_ID, TRIBUTE_WEBHOOK_PATH
from database import init_db
import handlers.admin as admin_handlers
import handlers.user as user_handlers

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Проверка токена
if not BOT_TOKEN:
    logging.error("Не указан BOT_TOKEN в переменных окружения!")
    exit(1)

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Регистрация обработчиков
admin_handlers.register_admin_handlers(dp)
user_handlers.register_user_handlers(dp)

# Инициализация БД при старте
init_db()

async def on_startup(dp):
    logging.info("Бот запущен")
    
    # Уведомление админу
    try:
        await bot.send_message(ADMIN_ID, "🤖 Бот запущен и готов к работе!")
    except:
        pass

async def on_shutdown(dp):
    logging.info("Бот остановлен")

if __name__ == '__main__':
    # Для локального запуска (без вебхука)
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)