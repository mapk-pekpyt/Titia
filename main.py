import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

load_dotenv()  # Загружаем .env
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Получаем токен

from config import ADMIN_ID
from database import init_db
from handlers import admin, user, server
from utils.monitoring import start_monitoring

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def main():
    # Инициализация БД
    init_db()
    
    # Инициализация бота
    dp = Dispatcher()
    
    # Регистрация роутеров
    dp.include_router(admin.router)
    dp.include_router(user.router)
    dp.include_router(server.router)
    
    # Запуск мониторинга серверов
    asyncio.create_task(start_monitoring(bot))
    
    # Приветственное сообщение админу
    await bot.send_message(ADMIN_ID, "🤖 VPN Bot запущен и готов к работе!")
    
    # Запуск поллинга
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())