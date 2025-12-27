import os, sqlite3, paramiko, asyncio, logging, json, re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
import subprocess

# Конфигурация
ADMIN_ID = 5791171535
ADMIN_CHAT_ID = -1003542769962
BOT_TOKEN = os.getenv("BOT_TOKEN")
PROVIDER_TOKEN = "5775769170:LIVE:TG_ADz_HW287D54Wfd3pqBi_BQA"  # Для карт
SUPPORT_USERNAME = "@vpnhostik"
DB_NAME = "vpn_bot.db"
SSH_KEYS_DIR = "ssh_keys"

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация БД
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY,
            host TEXT UNIQUE,
            ssh_user TEXT,
            ssh_key_path TEXT,
            public_key TEXT,
            private_key TEXT,
            installed BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            subscribed_until TIMESTAMP,
            active_server_id INTEGER,
            uuid TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (active_server_id) REFERENCES servers(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY,
            tg_id INTEGER,
            amount INTEGER,
            currency TEXT,
            provider TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# SSH функции
async def execute_ssh_command(host, user, key_path, command):
    """Выполняет команду на сервере через SSH"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=host, username=user, key_filename=key_path)
        
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        ssh.close()
        return output, error
    except Exception as e:
        logger.error(f"SSH ошибка: {e}")
        return None, str(e)

async def setup_server(host, user, key_path):
    """Установка и настройка XRay на сервере"""
    # 1. Обновление системы
    await execute_ssh_command(host, user, key_path, "apt update && apt upgrade -y")
    
    # 2. Установка XRay
    install_cmds = [
        "apt install curl -y",
        "bash -c \"$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)\" @ install"
    ]
    for cmd in install_cmds:
        await execute_ssh_command(host, user, key_path, cmd)
    
    # 3. Генерация ключей
    output, _ = await execute_ssh_command(host, user, key_path, "xray x25519")
    private_key = re.search(r"PrivateKey:\s*([A-Za-z0-9_-]+)", output).group(1)
    public_key = re.search(r"PublicKey:\s*([A-Za-z0-9_-]+)", output).group(1)
    
    # 4. Конфигурация XRay
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "tag": "proxy",
            "port": 443,
            "protocol": "vless",
            "settings": {
                "clients": [],
                "decryption": "none"
            },
            "streamSettings": {
                "network": "tcp",
                "security": "reality",
                "realitySettings": {
                    "dest": "google.com:443",
                    "serverNames": ["google.com"],
                    "privateKey": private_key,
                    "shortIds": ["aabbccdd"]
                }
            }
        }],
        "outbounds": [{"protocol": "freedom", "tag": "direct"}]
    }
    
    # Загрузка конфига на сервер
    config_json = json.dumps(config, indent=2)
    upload_cmd = f"echo '{config_json}' > /usr/local/etc/xray/config.json"
    await execute_ssh_command(host, user, key_path, upload_cmd)
    
    # Создание файла пользователей
    await execute_ssh_command(host, user, key_path, 
        "echo '{}' > /usr/local/etc/xray/users.json")
    
    # Запуск XRay
    await execute_ssh_command(host, user, key_path,
        "systemctl enable xray && systemctl restart xray")
    
    return public_key, private_key

# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Регистрация пользователя
    cur.execute("INSERT OR IGNORE INTO users (tg_id, username) VALUES (?, ?)",
                (user.id, user.username))
    
    # Проверка подписки
    cur.execute("SELECT subscribed_until FROM users WHERE tg_id = ?", (user.id,))
    result = cur.fetchone()
    conn.close()
    
    if user.id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("➕ Добавить сервер", callback_data="add_server")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("🎁 Выдать подписку", callback_data="grant_sub")],
            [InlineKeyboardButton("💰 Настроить оплату", callback_data="setup_payment")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🛒 Купить подписку", callback_data="buy_sub")],
            [InlineKeyboardButton("📱 Мой VPN", callback_data="my_vpn")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
    
    await update.message.reply_text(
        f"Привет, {user.first_name}!\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def add_server_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление нового сервера"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    await update.callback_query.message.reply_text(
        "Отправьте SSH ключ в формате .key файла\n"
        "После отправки ключа введите данные сервера в формате:\n"
        "IP_адрес|ssh_пользователь"
    )
    context.user_data['awaiting_server_data'] = True

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка загрузки SSH ключа"""
    if not context.user_data.get('awaiting_server_data'):
        return
    
    document = update.message.document
    if not document.file_name.endswith('.key'):
        await update.message.reply_text("❌ Файл должен быть с расширением .key")
        return
    
    # Сохранение ключа
    os.makedirs(SSH_KEYS_DIR, exist_ok=True)
    key_path = os.path.join(SSH_KEYS_DIR, document.file_name)
    
    file = await context.bot.get_file(document.file_id)
    await file.download_to_drive(key_path)
    
    os.chmod(key_path, 0o600)  # Безопасные права
    
    context.user_data['ssh_key_path'] = key_path
    await update.message.reply_text(
        "✅ Ключ сохранен. Теперь отправьте данные сервера:\n"
        "IP_адрес|ssh_пользователь"
    )

async def handle_server_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка данных сервера"""
    if 'ssh_key_path' not in context.user_data:
        return
    
    try:
        host, ssh_user = update.message.text.split('|')
        key_path = context.user_data['ssh_key_path']
        
        # Тестирование подключения
        await update.message.reply_text("🔧 Настройка сервера...")
        
        # Установка XRay
        public_key, private_key = await setup_server(host, ssh_user, key_path)
        
        # Сохранение в БД
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO servers (host, ssh_user, ssh_key_path, public_key, private_key, installed)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (host, ssh_user, key_path, public_key, private_key))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ Сервер {host} успешно настроен!\n"
            f"Public Key: {public_key[:20]}..."
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        context.user_data.clear()

async def buy_subscription_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню покупки подписки"""
    query = update.callback_query
    keyboard = [
        [
            InlineKeyboardButton("7 дней - 50 звёзд", callback_data="sub_7day"),
            InlineKeyboardButton("30 дней - 150 звёзд", callback_data="sub_30day")
        ],
        [InlineKeyboardButton("💳 Оплата картой", callback_data="pay_card")],
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    
    await query.edit_message_text(
        "Выберите тариф:\n\n"
        "⭐ Звёзды - оплата через Telegram\n"
        "💳 Карта - свяжитесь с поддержкой",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def process_stars_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка оплаты звёздами"""
    query = update.callback_query
    tariff = query.data.split("_")[1]
    
    prices = {
        "7day": 50,
        "30day": 150
    }
    
    if tariff in prices:
        # Создание инвойса для звёзд
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=f"VPN на {tariff}",
            description="Доступ к защищенному VPN",
            payload=f"stars_{tariff}_{update.effective_user.id}",
            provider_token=PROVIDER_TOKEN,
            currency="XTR",  # Telegram Stars
            prices=[LabeledPrice("Stars", prices[tariff])]
        )

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка успешной оплаты"""
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    user_id = update.effective_user.id
    
    if payload.startswith("stars_"):
        _, tariff, paid_user_id = payload.split("_")
        
        # Назначение подписки
        days = 7 if tariff == "7day" else 30
        subscribed_until = datetime.now() + timedelta(days=days)
        
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        
        # Находим свободный сервер
        cur.execute("SELECT id, host, ssh_user, ssh_key_path FROM servers WHERE installed = 1")
        server = cur.fetchone()
        
        if server:
            server_id, host, ssh_user, key_path = server
            
            # Генерация UUID для пользователя
            output, _ = await execute_ssh_command(host, ssh_user, key_path, "xray uuid")
            uuid = output.strip()
            
            # Добавление пользователя на сервер
            add_user_cmd = f"""
                cat <<EOF > /tmp/user_config.json
                {{
                    "id": "{uuid}",
                    "flow": "xtls-rprx-vision"
                }}
                EOF
                
                # Обновление конфига XRay (добавление клиента)
                jq '.inbounds[0].settings.clients += [input]' /usr/local/etc/xray/config.json /tmp/user_config.json > /tmp/new_config.json
                mv /tmp/new_config.json /usr/local/etc/xray/config.json
                
                # Добавление в users.json
                jq '. + {{"{uuid}": "{user_id}"}}' /usr/local/etc/xray/users.json > /tmp/new_users.json
                mv /tmp/new_users.json /usr/local/etc/xray/users.json
                
                systemctl restart xray
            """
            
            await execute_ssh_command(host, ssh_user, key_path, add_user_cmd)
            
            # Обновление БД
            cur.execute("""
                UPDATE users 
                SET subscribed_until = ?, active_server_id = ?, uuid = ?
                WHERE tg_id = ?
            """, (subscribed_until, server_id, uuid, user_id))
            
            conn.commit()
            
            # Отправка конфига пользователю
            cur.execute("SELECT public_key FROM servers WHERE id = ?", (server_id,))
            public_key = cur.fetchone()[0]
            
            vless_link = f"vless://{uuid}@{host}:443?security=reality&sni=google.com&alpn=h2&fp=chrome&pbk={public_key}&sid=aabbccdd&type=tcp&flow=xtls-rprx-vision&encryption=none#{user_id}"
            
            await update.message.reply_text(
                f"✅ Подписка активирована до {subscribed_until.strftime('%d.%m.%Y')}\n\n"
                f"Ваша ссылка:\n`{vless_link}`\n\n"
                f"За 24 часа до окончания вы получите уведомление.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("❌ Нет доступных серверов. Обратитесь к администратору.")
        
        conn.close()

async def grant_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ: выдача подписки пользователю"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    query = update.callback_query
    await query.message.reply_text(
        "Введите ID пользователя и срок подписки в днях через пробел:\n"
        "Пример: 123456789 30"
    )
    context.user_data['awaiting_grant'] = True

async def setup_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройка оплаты"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    keyboard = [
        [InlineKeyboardButton("⚙️ Указать цену в звёздах", callback_data="set_stars_price")],
        [InlineKeyboardButton("📋 Текст для оплаты картой", callback_data="set_card_text")],
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    
    await update.callback_query.message.reply_text(
        "Настройка оплаты:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def check_subscriptions(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневная проверка подписок"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Проверка подписок, заканчивающихся через 24 часа
    cur.execute("""
        SELECT tg_id, subscribed_until FROM users 
        WHERE subscribed_until BETWEEN datetime('now') AND datetime('now', '+1 day')
    """)
    
    for user_id, exp_date in cur.fetchall():
        try:
            await context.bot.send_message(
                user_id,
                f"⚠️ Ваша подписка закончится {exp_date.split()[0]}!\n"
                f"Продлите заранее для непрерывного доступа."
            )
        except:
            pass
    
    # Удаление просроченных подписок
    cur.execute("""
        SELECT u.tg_id, u.uuid, s.host, s.ssh_user, s.ssh_key_path 
        FROM users u
        LEFT JOIN servers s ON u.active_server_id = s.id
        WHERE u.subscribed_until < datetime('now')
    """)
    
    for tg_id, uuid, host, ssh_user, key_path in cur.fetchall():
        if uuid and host:
            # Удаление пользователя с сервера
            remove_cmd = f"""
                jq 'del(.["{uuid}"])' /usr/local/etc/xray/users.json > /tmp/new_users.json
                mv /tmp/new_users.json /usr/local/etc/xray/users.json
                
                # Удаление из конфига
                jq '.inbounds[0].settings.clients |= map(select(.id != "{uuid}"))' /usr/local/etc/xray/config.json > /tmp/new_config.json
                mv /tmp/new_config.json /usr/local/etc/xray/config.json
                
                systemctl restart xray
            """
            await execute_ssh_command(host, ssh_user, key_path, remove_cmd)
            
            # Очистка данных в БД
            cur.execute("UPDATE users SET uuid = NULL, active_server_id = NULL WHERE tg_id = ?", (tg_id,))
            
            try:
                await context.bot.send_message(tg_id, "❌ Ваша подписка закончилась. Доступ к VPN отключен.")
            except:
                pass
    
    conn.commit()
    conn.close()

def main():
    # Инициализация
    init_db()
    os.makedirs(SSH_KEYS_DIR, exist_ok=True)
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(buy_subscription_menu, pattern="^buy_sub$"))
    application.add_handler(CallbackQueryHandler(process_stars_payment, pattern="^sub_"))
    application.add_handler(CallbackQueryHandler(add_server_handler, pattern="^add_server$"))
    application.add_handler(CallbackQueryHandler(grant_subscription, pattern="^grant_sub$"))
    application.add_handler(CallbackQueryHandler(setup_payment, pattern="^setup_payment$"))
    
    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_server_data))
    
    # Оплата
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    # Планировщик для проверки подписок
    job_queue = application.job_queue
    job_queue.run_repeating(check_subscriptions, interval=3600, first=10)  # Каждый час
    
    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()