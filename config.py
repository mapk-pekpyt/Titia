import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 5791171535
ADMIN_CHAT_ID = -1003542769962
SUPPORT_USERNAME = "@vpnhostik"

# Пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "database.db")

# Создаём папку data
os.makedirs(DATA_DIR, exist_ok=True)

# Тарифы (в рублях)
TARIFFS = {
    "trial": {"name": "Пробный день", "price": 0, "days": 1},
    "week": {"name": "Неделя", "price": 100, "days": 7},
    "month": {"name": "Месяц", "price": 250, "days": 30},
    "2months": {"name": "2 месяца", "price": 450, "days": 60}
}