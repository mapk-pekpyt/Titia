import sqlite3
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Сервера
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS servers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        host TEXT NOT NULL,
        port INTEGER DEFAULT 22,
        username TEXT,
        password TEXT,
        ssh_key TEXT,
        auth_type TEXT CHECK(auth_type IN ('password', 'key')),
        panel_url TEXT,
        panel_username TEXT,
        panel_password TEXT,
        max_users INTEGER DEFAULT 100,
        current_users INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'active'
    )
    ''')
    
    # Пользователи бота
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        username TEXT,
        full_name TEXT,
        balance REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Подписки
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        server_id INTEGER,
        tariff TEXT,
        payment_amount REAL,
        payment_method TEXT,
        payment_details TEXT,
        payment_status TEXT DEFAULT 'pending',
        config_data TEXT,
        start_date TIMESTAMP,
        end_date TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (server_id) REFERENCES servers (id)
    )
    ''')
    
    # Реквизиты оплаты
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS payment_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_number TEXT,
        phone_number TEXT,
        bank_name TEXT,
        recipient_name TEXT,
        is_active BOOLEAN DEFAULT TRUE
    )
    ''')
    
    # Логи
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id INTEGER,
        action TEXT,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

if __name__ == "__main__":
    init_db()