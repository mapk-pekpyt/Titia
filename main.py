# main.py  — финальный ядро, НЕ МЕНЯТЬ
from telebot import TeleBot
from config import TOKEN
from utils.db import init_db, get_db_utils
from plugins.loader import load_plugins

bot = TeleBot(TOKEN, parse_mode="HTML")

# инициализация базы (создаст файл и таблицы)
init_db()

# получаем утилиты и загружаем плагины (plugins/*.py)
utils = get_db_utils()
load_plugins(bot, utils)

print("Bot started (plugins loaded).")
bot.infinity_polling(skip_pending=True)