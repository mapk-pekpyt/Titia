import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 5791171535))
ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID', -1003542769962))
SUPPORT_USERNAME = os.getenv('SUPPORT_USERNAME', '@vpnhostik')

# Настройки Tribute
TRIBUTE_API_KEY = '42d4d099-20fd-4f55-a196-d77d9fed'
TRIBUTE_WEBHOOK_PATH = '/tribute_webhook'
TRIBUTE_PRODUCTS = {
    'week': {'id': 'poWz', 'price': 100, 'days': 7},
    'month': {'id': 'poX4', 'price': 250, 'days': 30},
    '2months': {'id': 'poX5', 'price': 450, 'days': 60}
}

# Пути
DB_PATH = 'vpn_bot.db'