import telebot
import os
import random
import string
import subprocess
import time
import json
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

# ========== НАСТРОЙКИ ==========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Нет TELEGRAM_BOT_TOKEN в окружении")

bot = telebot.TeleBot(TOKEN)
ADMIN_ID = "5791171535"  # Твой ID

# База данных пользователей
DB_FILE = "/etc/vpn_users.db"
# ===============================

# Инициализация БД
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT UNIQUE,
            username TEXT,
            vpn_username TEXT UNIQUE,
            vpn_password TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Проверка админа
def is_admin(user_id):
    return str(user_id) == ADMIN_ID

# Генерация пароля
def generate_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))

# Генерация имени пользователя VPN
def generate_vpn_username(base="user"):
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{base}_{random_part}"

# Получение IP сервера
def get_server_ip():
    try:
        commands = [
            "curl -s ifconfig.me",
            "curl -s icanhazip.com", 
            "hostname -I | awk '{print $1}'",
            "ip addr show | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d/ -f1"
        ]
        
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            ip = result.stdout.strip()
            if ip and len(ip.split('.')) == 4:
                return ip.split()[0] if ' ' in ip else ip
        return "ВАШ_IP_СЕРВЕРА"
    except:
        return "ВАШ_IP_СЕРВЕРА"

# Запуск команды
def run_cmd(cmd, desc=""):
    if desc:
        print(f"[{desc}] {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

# Проверка ОС
def check_os():
    try:
        with open('/etc/os-release', 'r') as f:
            content = f.read()
            if 'Oracle' in content or 'ol' in content:
                return "oracle"
            elif 'Ubuntu' in content:
                return "ubuntu"
            elif 'Debian' in content:
                return "debian"
            elif 'CentOS' in content:
                return "centos"
        return "unknown"
    except:
        return "unknown"

# Проверка установлен ли VPN
def is_vpn_installed():
    return os.path.exists('/etc/ipsec.conf') and os.path.exists('/etc/ipsec.secrets')

# Добавление пользователя в VPN конфиг
def add_vpn_user(username, password):
    try:
        with open('/etc/ipsec.secrets', 'a') as f:
            f.write(f'\n{username} : EAP "{password}"')
        
        # Перезагружаем конфиг
        run_cmd("ipsec rereadsecrets", "Обновление секретов")
        return True
    except:
        return False

# Удаление пользователя из VPN конфига
def remove_vpn_user(username):
    try:
        with open('/etc/ipsec.secrets', 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        for line in lines:
            if not line.strip().startswith(f'{username} :'):
                new_lines.append(line)
        
        with open('/etc/ipsec.secrets', 'w') as f:
            f.writelines(new_lines)
        
        run_cmd("ipsec rereadsecrets", "Обновление секретов")
        return True
    except:
        return False

# БД операции
def add_user_to_db(telegram_id, username, vpn_username, vpn_password):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO users (telegram_id, username, vpn_username, vpn_password, last_seen)
            VALUES (?, ?, ?, ?, ?)
        ''', (telegram_id, username, vpn_username, vpn_password, datetime.now()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_user_last_seen(telegram_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_seen = ? WHERE telegram_id = ?', 
                   (datetime.now(), telegram_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT telegram_id, username, vpn_username, created_at, last_seen, is_active 
        FROM users ORDER BY created_at DESC
    ''')
    users = cursor.fetchall()
    conn.close()
    return users

def delete_user(vpn_username):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE vpn_username = ?', (vpn_username,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def get_user_by_vpn_username(vpn_username):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE vpn_username = ?', (vpn_username,))
    user = cursor.fetchone()
    conn.close()
    return user

# Форматирование времени
def format_time_ago(dt):
    if not dt:
        return "никогда"
    
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
    
    now = datetime.now()
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} дней назад"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} часов назад"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} минут назад"
    else:
        return "только что"

# Проверка онлайна (был в сети менее 5 минут назад)
def is_online(last_seen):
    if not last_seen:
        return False
    if isinstance(last_seen, str):
        last_seen = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
    return (datetime.now() - last_seen).seconds < 300  # 5 минут

# ========== КОМАНДЫ БОТА ==========

@bot.message_handler(commands=['start'])
def start_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = telebot.types.KeyboardButton("📲 Установить VPN")
    btn2 = telebot.types.KeyboardButton("👥 Пользователи")
    btn3 = telebot.types.KeyboardButton("🔐 Мои данные")
    btn4 = telebot.types.KeyboardButton("📊 Статус VPN")
    markup.add(btn1, btn2, btn3, btn4)
    
    bot.reply_to(message,
        "🔐 VPN Бот с управлением пользователями\n\n"
        "Основные команды:\n"
        "/install - Установить VPN\n"
        "/new @username - Новый пользователь\n"
        "/users - Список пользователей\n"
        "/del @username - Удалить пользователя\n"
        "/status - Статус VPN\n"
        "/fix - Исправить проблемы",
        reply_markup=markup
    )

@bot.message_handler(commands=['install'])
def install_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    # Проверяем ОС
    os_type = check_os()
    bot.send_message(message.chat.id, f"🖥️ Обнаружена ОС: {os_type.upper()}")
    
    if os_type not in ["oracle", "ubuntu", "debian"]:
        bot.send_message(message.chat.id,
            "⚠️ Неподдерживаемая ОС. Поддерживаются: Oracle Linux, Ubuntu, Debian\n"
            "Продолжить установку? (может не сработать)"
        )
    
    markup = telebot.types.InlineKeyboardMarkup()
    btn_yes = telebot.types.InlineKeyboardButton("✅ Да, устанавливай!", callback_data="install_now")
    btn_no = telebot.types.InlineKeyboardButton("❌ Нет, отмена", callback_data="cancel")
    markup.add(btn_yes, btn_no)
    
    bot.send_message(message.chat.id,
        "⚠️ **ВНИМАНИЕ!**\n\n"
        "Сейчас на сервере будет установлен IKEv2 VPN.\n"
        "Это займет 2-3 минуты.\n\n"
        "Продолжить?",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "install_now":
        bot.edit_message_text("🔄 Начинаю установку VPN...", 
                            call.message.chat.id, 
                            call.message.message_id)
        install_vpn(call.message)
    elif call.data == "cancel":
        bot.edit_message_text("❌ Установка отменена", 
                            call.message.chat.id, 
                            call.message.message_id)

def install_vpn(message):
    try:
        # Шаг 1: Обновление системы
        bot.send_message(message.chat.id, "🔄 Шаг 1/7: Обновляю пакеты...")
        code, out, err = run_cmd("apt-get update -y && apt-get upgrade -y -qq", "Обновление")
        
        # Шаг 2: Установка StrongSwan
        bot.send_message(message.chat.id, "📦 Шаг 2/7: Устанавливаю StrongSwan...")
        
        # Устанавливаем все нужные пакеты
        packages = [
            "strongswan", 
            "strongswan-pki", 
            "libcharon-extra-plugins",
            "libstrongswan-extra-plugins",
            "strongswan-charon",
            "strongswan-starter",
            "iptables-persistent",
            "net-tools"
        ]
        
        install_cmd = f"apt-get install -y {' '.join(packages)}"
        code, out, err = run_cmd(install_cmd, "Установка пакетов")
        
        if code != 0:
            bot.send_message(message.chat.id, 
                f"⚠️ Проблема с установкой. Пробую другой способ...")
            run_cmd("apt-get install -y strongswan strongswan-pki", "Альт установка")
        
        # Шаг 3: Генерация данных
        bot.send_message(message.chat.id, "🔐 Шаг 3/7: Генерирую ключи и пароли...")
        
        server_ip = get_server_ip()
        
        # Создаем директории
        run_cmd("mkdir -p /etc/ipsec.d/private /etc/ipsec.d/cacerts /etc/ipsec.d/certs", "Создание директорий")
        
        # Генерация CA сертификата
        bot.send_message(message.chat.id, "📄 Шаг 4/7: Создаю SSL сертификаты...")
        
        ca_cmd = '''
        ipsec pki --gen --type rsa --size 4096 --outform pem > /etc/ipsec.d/private/ca-key.pem 2>/dev/null || \
        openssl genrsa -out /etc/ipsec.d/private/ca-key.pem 4096
        '''
        run_cmd(ca_cmd, "Генерация CA ключа")
        
        ca_cert_cmd = f'''
        ipsec pki --self --ca --lifetime 3650 --in /etc/ipsec.d/private/ca-key.pem \
        --type rsa --dn "CN=VPN Root CA" --outform pem > /etc/ipsec.d/cacerts/ca-cert.pem 2>/dev/null || \
        openssl req -new -x509 -days 3650 -key /etc/ipsec.d/private/ca-key.pem \
        -subj "/CN=VPN Root CA" -out /etc/ipsec.d/cacerts/ca-cert.pem
        '''
        run_cmd(ca_cert_cmd, "Создание CA сертификата")
        
        # Генерация серверного сертификата
        server_key_cmd = '''
        ipsec pki --gen --type rsa --size 4096 --outform pem > /etc/ipsec.d/private/server-key.pem 2>/dev/null || \
        openssl genrsa -out /etc/ipsec.d/private/server-key.pem 4096
        '''
        run_cmd(server_key_cmd, "Генерация серверного ключа")
        
        server_cert_cmd = f'''
        ipsec pki --pub --in /etc/ipsec.d/private/server-key.pem --type rsa | \
        ipsec pki --issue --lifetime 1825 --cacert /etc/ipsec.d/cacerts/ca-cert.pem \
        --cakey /etc/ipsec.d/private/ca-key.pem --dn "CN={server_ip}" --san {server_ip} \
        --flag serverAuth --flag ikeIntermediate --outform pem > /etc/ipsec.d/certs/server-cert.pem 2>/dev/null || \
        openssl req -new -key /etc/ipsec.d/private/server-key.pem -subj "/CN={server_ip}" | \
        openssl x509 -req -days 1825 -CA /etc/ipsec.d/cacerts/ca-cert.pem -CAkey /etc/ipsec.d/private/ca-key.pem -set_serial 01 -out /etc/ipsec.d/certs/server-cert.pem
        '''
        run_cmd(server_cert_cmd, "Создание серверного сертификата")
        
        # Шаг 5: Конфигурация
        bot.send_message(message.chat.id, "⚙️ Шаг 5/7: Настраиваю конфиги...")
        
        # Конфиг ipsec.conf
        ipsec_conf = f"""config setup
    charondebug="ike 1, knl 1, cfg 0"
    uniqueids=no

conn ikev2-vpn
    auto=add
    compress=no
    type=tunnel
    keyexchange=ikev2
    fragmentation=yes
    forceencaps=yes
    dpdaction=clear
    dpddelay=300s
    rekey=no
    left=%any
    leftid={server_ip}
    leftcert=server-cert.pem
    leftsendcert=always
    leftsubnet=0.0.0.0/0
    right=%any
    rightid=%any
    rightauth=eap-mschapv2
    rightsourceip=10.10.10.0/24
    rightdns=8.8.8.8,8.8.4.4
    rightsendcert=never
    eap_identity=%identity
"""
        
        with open('/etc/ipsec.conf', 'w') as f:
            f.write(ipsec_conf)
        
        # Создаем базовый файл secrets
        ipsec_secrets = f""": RSA "server-key.pem"
"""
        
        with open('/etc/ipsec.secrets', 'w') as f:
            f.write(ipsec_secrets)
        
        # Шаг 6: Настройка сети
        bot.send_message(message.chat.id, "🌐 Шаг 6/7: Настраиваю сеть...")
        
        run_cmd("sysctl -w net.ipv4.ip_forward=1", "IP форвардинг")
        run_cmd('echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf', "Сохранение настроек")
        run_cmd("sysctl -p", "Применение настроек")
        
        # Простые правила iptables
        iptables_cmd = f'''#!/bin/bash
iptables -t nat -A POSTROUTING -s 10.10.10.0/24 -o eth0 -j MASQUERADE 2>/dev/null || true
iptables -t nat -A POSTROUTING -s 10.10.10.0/24 -o ens3 -j MASQUERADE 2>/dev/null || true
iptables -t nat -A POSTROUTING -s 10.10.10.0/24 -o enp0s3 -j MASQUERADE 2>/dev/null || true
iptables -A FORWARD -s 10.10.10.0/24 -j ACCEPT
iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A INPUT -p udp --dport 500 -j ACCEPT
iptables -A INPUT -p udp --dport 4500 -j ACCEPT
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
'''
        
        with open('/tmp/setup_iptables.sh', 'w') as f:
            f.write(iptables_cmd)
        
        run_cmd("bash /tmp/setup_iptables.sh", "Настройка iptables")
        run_cmd("iptables-save > /etc/iptables.rules 2>/dev/null || true", "Сохранение правил")
        
        # Шаг 7: Запуск
        bot.send_message(message.chat.id, "🚀 Шаг 7/7: Запускаю VPN...")
        
        run_cmd("systemctl stop strongswan 2>/dev/null || true", "Остановка")
        run_cmd("systemctl stop strongswan-starter 2>/dev/null || true", "Остановка стартера")
        
        run_cmd("systemctl enable strongswan-starter", "Включение автозапуска")
        run_cmd("systemctl start strongswan-starter", "Запуск")
        
        time.sleep(3)
        
        code, out, err = run_cmd("systemctl status strongswan-starter --no-pager", "Проверка статуса")
        
        if "active (running)" in out or "active (running)" in err:
            # Успех!
            config_data = {
                "server_ip": server_ip,
                "installed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "os": check_os()
            }
            
            with open('/etc/vpn_config.json', 'w') as f:
                json.dump(config_data, f)
            
            instructions = f"""✅ **VPN УСПЕШНО УСТАНОВЛЕН!**

📡 **ДАННЫЕ СЕРВЕРА:**
Сервер: {server_ip}
Удаленный ID: {server_ip}
Локальный ID: (оставить пустым)
Тип: IKEv2

📋 **Теперь создай пользователей:**
1. /new @username - создать нового
2. /users - список всех

⚠️ **VPN установлен, но нет пользователей!**
Создай первого: /new @имя_пользователя"""
            
            bot.send_message(message.chat.id, instructions, parse_mode="Markdown")
            
        else:
            run_cmd("ipsec start --nofork &", "Альтернативный запуск")
            bot.send_message(message.chat.id,
                f"⚠️ VPN установлен, но сервис не запустился.\n"
                f"IP сервера: `{server_ip}`\n"
                f"Попробуй /fix или /restart",
                parse_mode="Markdown"
            )
                
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка установки: {str(e)}")

@bot.message_handler(commands=['new'])
def new_user_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    if not is_vpn_installed():
        bot.reply_to(message, "❌ VPN не установлен. Сначала /install")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "ℹ️ Использование: /new @username\nПример: /new @ivanov")
        return
    
    username = args[1].replace('@', '').strip()
    if not username:
        bot.reply_to(message, "❌ Укажите имя пользователя")
        return
    
    # Генерируем уникальные данные для VPN
    vpn_username = generate_vpn_username()
    vpn_password = generate_password()
    
    # Добавляем в конфиг VPN
    if add_vpn_user(vpn_username, vpn_password):
        # Сохраняем в БД
        if add_user_to_db(str(message.from_user.id), username, vpn_username, vpn_password):
            bot.reply_to(message,
                f"✅ **Пользователь создан!**\n\n"
                f"👤 TG: @{username}\n"
                f"🔐 VPN логин: `{vpn_username}`\n"
                f"🔑 VPN пароль: `{vpn_password}`\n\n"
                f"📱 **Для iPhone:**\n"
                f"Сервер: `{get_server_ip()}`\n"
                f"Удаленный ID: `{get_server_ip()}`\n"
                f"Тип: IKEv2",
                parse_mode="Markdown"
            )
        else:
            # Откатываем добавление в VPN если не удалось в БД
            remove_vpn_user(vpn_username)
            bot.reply_to(message, "❌ Ошибка сохранения пользователя")
    else:
        bot.reply_to(message, "❌ Ошибка создания VPN пользователя")

@bot.message_handler(commands=['users', 'list'])
def users_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    users = get_all_users()
    
    if not users:
        bot.reply_to(message, "📭 Нет пользователей")
        return
    
    server_ip = get_server_ip()
    response = f"👥 **ПОЛЬЗОВАТЕЛИ VPN**\n\n"
    response += f"📡 Сервер: `{server_ip}`\n"
    response += f"👑 Всего: {len(users)} пользователей\n\n"
    
    for user in users:
        telegram_id, tg_username, vpn_user, created_at, last_seen, is_active = user
        
        # Статус онлайна
        online_status = "🟢 В сети" if is_online(last_seen) else f"⚫ Был: {format_time_ago(last_seen)}"
        
        # Дней с создания
        if isinstance(created_at, str):
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            created = created_at
        days = (datetime.now() - created).days
        
        response += f"👤 @{tg_username or 'нет'}\n"
        response += f"   VPN: `{vpn_user}`\n"
        response += f"   Дней: {days}\n"
        response += f"   {online_status}\n"
        response += f"   Создан: {created.strftime('%d.%m.%Y')}\n"
        response += "   ─────\n"
    
    response += "\n📋 Команды:\n"
    response += "/new @username - добавить\n"
    response += "/del @username - удалить\n"
    response += "ℹ️ Удаление по Telegram username"
    
    bot.reply_to(message, response, parse_mode="Markdown")

@bot.message_handler(commands=['del', 'delete'])
def delete_user_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "ℹ️ Использование: /del @username\nПример: /del @ivanov")
        return
    
    username = args[1].replace('@', '').strip()
    
    # Ищем пользователя по Telegram username
    users = get_all_users()
    user_to_delete = None
    
    for user in users:
        tg_username = user[1]  # username из БД
        vpn_username = user[2]  # vpn_username из БД
        
        if tg_username == username:
            user_to_delete = vpn_username
            break
    
    if not user_to_delete:
        bot.reply_to(message, f"❌ Пользователь @{username} не найден")
        return
    
    # Удаляем из VPN конфига
    if remove_vpn_user(user_to_delete):
        # Удаляем из БД
        if delete_user(user_to_delete):
            bot.reply_to(message, f"✅ Пользователь @{username} удален")
        else:
            bot.reply_to(message, f"⚠️ Удален из VPN, но ошибка БД")
    else:
        bot.reply_to(message, f"❌ Ошибка удаления пользователя")

@bot.message_handler(commands=['details', 'my'])
def details_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    server_ip = get_server_ip()
    
    if not is_vpn_installed():
        bot.reply_to(message,
            "❌ VPN не установлен\n"
            "Используй /install для установки"
        )
        return
    
    config_info = f"📡 **ИНФОРМАЦИЯ О VPN**\n\n"
    config_info += f"🖥️ ОС: {check_os().upper()}\n"
    config_info += f"🌐 IP сервера: `{server_ip}`\n"
    config_info += f"🔐 Тип: IKEv2/IPsec\n"
    config_info += f"📊 Пользователей: {len(get_all_users())}\n\n"
    
    if os.path.exists('/etc/vpn_config.json'):
        with open('/etc/vpn_config.json', 'r') as f:
            config = json.load(f)
        config_info += f"📅 Установлен: {config.get('installed', 'неизвестно')}\n"
    
    bot.reply_to(message, config_info, parse_mode="Markdown")

@bot.message_handler(commands=['status'])
def status_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    checks = [
        ("strongswan-starter", "systemctl status strongswan-starter --no-pager"),
        ("ipsec", "ipsec status 2>/dev/null || echo 'ipsec не запущен'")
    ]
    
    results = []
    for name, cmd in checks:
        code, out, err = run_cmd(cmd)
        if "active (running)" in out or "active (running)" in err:
            results.append(f"✅ {name}: работает")
        elif "Security Associations" in out:
            results.append(f"✅ {name}: работает")
        else:
            results.append(f"❌ {name}: не работает")
    
    # Проверяем порты
    code, out, err = run_cmd("netstat -anu | grep -E ':500|:4500'")
    if "500" in out or "4500" in out:
        results.append("✅ Порт 500/4500: открыт")
    else:
        results.append("⚠️ Порт 500/4500: не слушает")
    
    status_msg = "📊 **Статус VPN:**\n\n" + "\n".join(results)
    status_msg += f"\n\n👥 Пользователей: {len(get_all_users())}"
    
    bot.reply_to(message, status_msg, parse_mode="Markdown")

@bot.message_handler(commands=['fix'])
def fix_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    bot.reply_to(message, "🔧 Исправляю проблемы с VPN...")
    
    fix_commands = [
        ("Обновляю пакеты", "apt-get update -y"),
        ("Переустанавливаю StrongSwan", "apt-get install --reinstall -y strongswan strongswan-starter"),
        ("Включаю автозапуск", "systemctl enable strongswan-starter"),
        ("Запускаю VPN", "systemctl start strongswan-starter"),
        ("Обновляю конфиги", "ipsec rereadall 2>/dev/null || true"),
        ("Перезагружаю службу", "systemctl restart strongswan-starter")
    ]
    
    for desc, cmd in fix_commands:
        code, out, err = run_cmd(cmd)
        time.sleep(1)
    
    code, out, err = run_cmd("systemctl status strongswan-starter --no-pager")
    if "active (running)" in out:
        bot.send_message(message.chat.id, "✅ VPN исправлен и запущен!")
    else:
        bot.send_message(message.chat.id,
            "⚠️ Есть проблемы с запуском.\n"
            "Попробуй /restart или переустанови: /install"
        )

@bot.message_handler(commands=['restart'])
def restart_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    bot.reply_to(message, "🔄 Перезапускаю VPN...")
    
    run_cmd("systemctl stop strongswan-starter 2>/dev/null || true")
    time.sleep(1)
    run_cmd("systemctl start strongswan-starter")
    time.sleep(2)
    
    code, out, err = run_cmd("systemctl status strongswan-starter --no-pager")
    if "active (running)" in out:
        bot.reply_to(message, "✅ VPN перезапущен и работает!")
    else:
        bot.reply_to(message, "❌ VPN не запустился. Попробуй /fix")

# Обработчики кнопок
@bot.message_handler(func=lambda message: message.text == "📲 Установить VPN")
def button_install(message):
    install_command(message)

@bot.message_handler(func=lambda message: message.text == "👥 Пользователи")
def button_users(message):
    users_command(message)

@bot.message_handler(func=lambda message: message.text == "🔐 Мои данные")
def button_details(message):
    details_command(message)

@bot.message_handler(func=lambda message: message.text == "📊 Статус VPN")
def button_status(message):
    status_command(message)

@bot.message_handler(func=lambda message: True)
def handle_all(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    # Обновляем время последней активности
    update_user_last_seen(str(message.from_user.id))
    
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = telebot.types.KeyboardButton("📲 Установить VPN")
    btn2 = telebot.types.KeyboardButton("👥 Пользователи")
    btn3 = telebot.types.KeyboardButton("🔐 Мои данные")
    btn4 = telebot.types.KeyboardButton("📊 Статус VPN")
    markup.add(btn1, btn2, btn3, btn4)
    
    bot.reply_to(message,
        "🤔 Не понял команду\n\n"
        "📋 **Основные команды:**\n"
        "/install - Установить VPN\n"
        "/new @username - Создать пользователя\n"
        "/users - Список пользователей\n"
        "/del @username - Удалить пользователя\n"
        "/status - Статус VPN\n"
        "/fix - Исправить проблемы\n\n"
        "Или используй кнопки ниже",
        reply_markup=markup
    )

# ========== ЗАПУСК БОТА ==========
if __name__ == "__main__":
    print("🤖 VPN Бот с управлением пользователями запускается...")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print(f"💾 База данных: {DB_FILE}")
    print("📱 Бот ждет команды /start в Telegram")
    
    # Проверяем что VPN установлен
    if is_vpn_installed():
        print("✅ VPN уже установлен")
    else:
        print("⚠️ VPN не установлен. Используй /install")
    
    # Запускаем бота
    try:
        bot.polling(none_stop=True, interval=1)
    except Exception as e:
        print(f"❌ Ошибка бота: {e}")
        print("Перезапускаю через 5 секунд...")
        time.sleep(5)