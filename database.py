import sqlite3
from config import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Серверы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host TEXT NOT NULL,
            ssh_port INTEGER DEFAULT 22,
            ssh_username TEXT,
            ssh_password TEXT,
            ssh_key TEXT,
            panel_port INTEGER DEFAULT 54321,
            panel_path TEXT,
            panel_username TEXT DEFAULT 'admin',
            panel_password TEXT,
            max_users INTEGER DEFAULT 50,
            current_users INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Пользователи бота
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            trial_used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Подписки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            server_id INTEGER,
            tariff TEXT,
            status TEXT DEFAULT 'active',
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (server_id) REFERENCES servers (id)
        )
    ''')
    
    # Платежи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            tariff TEXT,
            status TEXT,
            tribute_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    #  servers:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servers (
            ...
            ram_info TEXT,
            cpu_info TEXT,
            disk_info TEXT,
            ...
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db():
    """Получить соединение с БД"""
    return sqlite3.connect(DB_PATH)

if __name__ == '__main__':
    init_db()
    print("База данных инициализирована")