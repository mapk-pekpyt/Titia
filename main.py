import telebot
import os
import random
import string
import subprocess
import json
import re
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Нет TELEGRAM_BOT_TOKEN в окружении")

bot = telebot.TeleBot(TOKEN)
ADMIN_ID = "5791171535"  # Твой ID
# ===============================

# Проверка админа
def is_admin(user_id):
    return str(user_id) == ADMIN_ID

# Генерация пароля
def generate_password(length=10):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# Генерация логина VPN
def generate_vpn_username():
    return f"vpn{random.randint(1000, 9999)}"

# Проверка ОС и выбор менеджера пакетов
def get_package_manager():
    try:
        with open('/etc/os-release', 'r') as f:
            content = f.read().lower()
            if 'oracle' in content or 'ol' in content or 'centos' in content or 'rhel' in content:
                return 'dnf'
            elif 'ubuntu' in content or 'debian' in content:
                return 'apt'
        return 'apt'  # по умолчанию
    except:
        return 'apt'

# Получение сетевого интерфейса
def get_network_interface():
    try:
        result = subprocess.run("ip route | grep default | awk '{print $5}' | head -1", 
                              shell=True, capture_output=True, text=True)
        iface = result.stdout.strip()
        return iface if iface else "eth0"
    except:
        return "eth0"

# Получение IP сервера
def get_server_ip():
    try:
        result = subprocess.run("curl -s ifconfig.me", shell=True, capture_output=True, text=True)
        ip = result.stdout.strip()
        if ip and '.' in ip:
            return ip
        return "YOUR_SERVER_IP"
    except:
        return "YOUR_SERVER_IP"

# Выполнение команды
def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    except:
        return 1, "", "Command failed"

# Проверка установлен ли VPN
def is_vpn_installed():
    return os.path.exists('/etc/ipsec.conf') and os.path.exists('/etc/ipsec.secrets')

# ========== VPN УСТАНОВКА ==========

def install_vpn(message):
    try:
        pm = get_package_manager()
        server_ip = get_server_ip()
        iface = get_network_interface()
        
        bot.send_message(message.chat.id, f"🖥️ ОС: {pm.upper()}")
        bot.send_message(message.chat.id, f"🌐 Интерфейс: {iface}")
        bot.send_message(message.chat.id, f"📡 IP сервера: {server_ip}")
        
        # 1. Установка пакетов
        bot.send_message(message.chat.id, "📦 Устанавливаю пакеты...")
        if pm == 'dnf':
            run_cmd("dnf install -y epel-release")
            run_cmd("dnf install -y strongswan strongswan-pki")
        else:
            run_cmd("apt-get update -y")
            run_cmd("apt-get install -y strongswan strongswan-pki")
        
        # 2. Сертификаты
        bot.send_message(message.chat.id, "🔐 Генерирую сертификаты...")
        run_cmd("mkdir -p /etc/ipsec.d/private /etc/ipsec.d/cacerts /etc/ipsec.d/certs")
        
        # CA
        run_cmd('''ipsec pki --gen --type rsa --size 2048 --outform pem > /etc/ipsec.d/private/ca-key.pem 2>/dev/null || \
        openssl genrsa -out /etc/ipsec.d/private/ca-key.pem 2048''')
        
        run_cmd('''ipsec pki --self --ca --lifetime 3650 --in /etc/ipsec.d/private/ca-key.pem \
        --type rsa --dn "CN=VPN CA" --outform pem > /etc/ipsec.d/cacerts/ca-cert.pem 2>/dev/null || \
        openssl req -new -x509 -days 3650 -key /etc/ipsec.d/private/ca-key.pem -subj "/CN=VPN CA" -out /etc/ipsec.d/cacerts/ca-cert.pem''')
        
        # Серверный
        run_cmd(f'''ipsec pki --gen --type rsa --size 2048 --outform pem > /etc/ipsec.d/private/server-key.pem 2>/dev/null || \
        openssl genrsa -out /etc/ipsec.d/private/server-key.pem 2048''')
        
        run_cmd(f'''ipsec pki --pub --in /etc/ipsec.d/private/server-key.pem --type rsa | \
        ipsec pki --issue --lifetime 1825 --cacert /etc/ipsec.d/cacerts/ca-cert.pem \
        --cakey /etc/ipsec.d/private/ca-key.pem --dn "CN={server_ip}" --san {server_ip} \
        --outform pem > /etc/ipsec.d/certs/server-cert.pem 2>/dev/null || \
        openssl req -new -key /etc/ipsec.d/private/server-key.pem -subj "/CN={server_ip}" | \
        openssl x509 -req -days 1825 -CA /etc/ipsec.d/cacerts/ca-cert.pem -CAkey /etc/ipsec.d/private/ca-key.pem -set_serial 01 -out /etc/ipsec.d/certs/server-cert.pem''')
        
        # 3. Конфиг
        bot.send_message(message.chat.id, "⚙️ Настраиваю конфигурацию...")
        
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
        
        # Базовый файл секретов
        with open('/etc/ipsec.secrets', 'w') as f:
            f.write(': RSA "server-key.pem"\n')
        
        # 4. Сеть
        bot.send_message(message.chat.id, "🌐 Настраиваю сеть...")
        
        run_cmd("sysctl -w net.ipv4.ip_forward=1")
        run_cmd('echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf')
        run_cmd("sysctl -p")
        
        # Правила iptables
        iptables_rules = f'''#!/bin/bash
iptables -t nat -A POSTROUTING -s 10.10.10.0/24 -o {iface} -j MASQUERADE
iptables -A FORWARD -s 10.10.10.0/24 -j ACCEPT
iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A INPUT -p udp --dport 500 -j ACCEPT
iptables -A INPUT -p udp --dport 4500 -j ACCEPT
'''
        
        with open('/tmp/vpn_firewall.sh', 'w') as f:
            f.write(iptables_rules)
        
        run_cmd("bash /tmp/vpn_firewall.sh")
        
        # 5. Запуск
        bot.send_message(message.chat.id, "🚀 Запускаю VPN...")
        
        run_cmd("systemctl stop strongswan 2>/dev/null || true")
        run_cmd("systemctl start strongswan")
        run_cmd("systemctl enable strongswan")
        
        time.sleep(2)
        
        # Проверка
        code, out, err = run_cmd("systemctl status strongswan --no-pager")
        
        if "active (running)" in out:
            # Сохраняем инфу
            vpn_info = {
                "server_ip": server_ip,
                "interface": iface,
                "installed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "package_manager": pm
            }
            
            with open('/etc/vpn_info.json', 'w') as f:
                json.dump(vpn_info, f)
            
            # Создаем первого пользователя
            first_user = "admin"
            first_pass = generate_password()
            
            with open('/etc/ipsec.secrets', 'a') as f:
                f.write(f'\n{first_user} : EAP "{first_pass}"')
            
            run_cmd("ipsec rereadall 2>/dev/null || true")
            
            bot.send_message(message.chat.id,
                f"✅ **VPN установлен!**\n\n"
                f"📡 Сервер: `{server_ip}`\n"
                f"🔐 Тип: IKEv2\n\n"
                f"👤 **Первый пользователь:**\n"
                f"Логин: `{first_user}`\n"
                f"Пароль: `{first_pass}`\n\n"
                f"📱 Для iPhone:\n"
                f"- Сервер: {server_ip}\n"
                f"- Удаленный ID: {server_ip}\n"
                f"- Локальный ID: (оставить пустым)\n"
                f"- Тип: IKEv2\n\n"
                f"💡 Создать еще: /new @username",
                parse_mode="Markdown"
            )
            
        else:
            bot.send_message(message.chat.id,
                f"⚠️ Установлен, но не запущен.\n"
                f"IP: `{server_ip}`\n"
                f"Запусти: `sudo systemctl start strongswan`",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

# ========== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ==========

def get_users_list():
    """Получить список пользователей из ipsec.secrets"""
    users = []
    if os.path.exists('/etc/ipsec.secrets'):
        with open('/etc/ipsec.secrets', 'r') as f:
            for line in f:
                line = line.strip()
                if 'EAP' in line and ':' in line:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        username = parts[0].strip()
                        if username and not username.startswith('#'):
                            users.append(username)
    return users

def add_vpn_user(username, password):
    """Добавить пользователя в VPN"""
    try:
        with open('/etc/ipsec.secrets', 'a') as f:
            f.write(f'\n{username} : EAP "{password}"')
        run_cmd("ipsec rereadall 2>/dev/null || true")
        return True
    except:
        return False

def remove_vpn_user(username):
    """Удалить пользователя из VPN"""
    try:
        with open('/etc/ipsec.secrets', 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        for line in lines:
            if not line.strip().startswith(f'{username} :'):
                new_lines.append(line)
        
        with open('/etc/ipsec.secrets', 'w') as f:
            f.writelines(new_lines)
        
        run_cmd("ipsec rereadall 2>/dev/null || true")
        return True
    except:
        return False

# ========== КОМАНДЫ БОТА ==========

@bot.message_handler(commands=['start'])
def start_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    bot.reply_to(message,
        "🔐 VPN Бот\n\n"
        "Команды:\n"
        "/install - Установить VPN\n"
        "/new @username - Создать пользователя\n"
        "/users - Список пользователей\n"
        "/del username - Удалить пользователя\n"
        "/status - Статус VPN\n"
        "/restart - Перезапустить VPN"
    )

@bot.message_handler(commands=['install'])
def install_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    if is_vpn_installed():
        bot.reply_to(message, "✅ VPN уже установлен\nИспользуй /new для создания пользователей")
        return
    
    bot.reply_to(message, "⚠️ Установка займет 2-3 минуты...")
    install_vpn(message)

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
        bot.reply_to(message, "ℹ️ Использование: /new username\nПример: /new ivanov")
        return
    
    tg_username = args[1].replace('@', '').strip()
    if not tg_username:
        bot.reply_to(message, "❌ Укажите имя")
        return
    
    # Генерируем VPN данные
    vpn_user = generate_vpn_username()
    vpn_pass = generate_password()
    
    if add_vpn_user(vpn_user, vpn_pass):
        server_ip = get_server_ip()
        bot.reply_to(message,
            f"✅ **Пользователь создан!**\n\n"
            f"👤 Имя: @{tg_username}\n"
            f"🔐 VPN логин: `{vpn_user}`\n"
            f"🔑 VPN пароль: `{vpn_pass}`\n\n"
            f"📱 Для iPhone:\n"
            f"- Сервер: `{server_ip}`\n"
            f"- Удаленный ID: `{server_ip}`\n"
            f"- Логин: `{vpn_user}`\n"
            f"- Пароль: `{vpn_pass}`",
            parse_mode="Markdown"
        )
    else:
        bot.reply_to(message, "❌ Ошибка создания")

@bot.message_handler(commands=['users'])
def users_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    users = get_users_list()
    
    if not users or len(users) == 0:
        bot.reply_to(message, "📭 Нет пользователей")
        return
    
    server_ip = get_server_ip()
    response = f"👥 **Пользователи VPN**\n\n"
    response += f"📡 Сервер: `{server_ip}`\n"
    response += f"👤 Всего: {len(users)}\n\n"
    
    # Показываем только VPN логины
    for i, user in enumerate(users[:20], 1):  # максимум 20
        response += f"{i}. `{user}`\n"
    
    if len(users) > 20:
        response += f"\n... и еще {len(users)-20} пользователей"
    
    response += "\n📋 Удалить: /del username"
    
    bot.reply_to(message, response, parse_mode="Markdown")

@bot.message_handler(commands=['del'])
def delete_user_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "ℹ️ Использование: /del username\nПример: /del vpn1234")
        return
    
    vpn_username = args[1].strip()
    users = get_users_list()
    
    if vpn_username not in users:
        bot.reply_to(message, f"❌ Пользователь `{vpn_username}` не найден")
        return
    
    if remove_vpn_user(vpn_username):
        bot.reply_to(message, f"✅ Пользователь `{vpn_username}` удален")
    else:
        bot.reply_to(message, f"❌ Ошибка удаления")

@bot.message_handler(commands=['status'])
def status_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    code, out, err = run_cmd("systemctl status strongswan --no-pager")
    
    if "active (running)" in out:
        status = "✅ VPN работает"
        users = get_users_list()
        user_count = len(users)
        
        # Проверяем порты
        code2, out2, err2 = run_cmd("ss -anu | grep -E ':500|:4500'")
        ports = "✅ Порт 500/4500 открыт" if "500" in out2 or "4500" in out2 else "⚠️ Порты не слушают"
        
        bot.reply_to(message,
            f"{status}\n"
            f"👥 Пользователей: {user_count}\n"
            f"{ports}\n\n"
            f"💡 /users - список пользователей",
            parse_mode="Markdown"
        )
    else:
        bot.reply_to(message, "❌ VPN не работает\nИспользуй /install или /restart")

@bot.message_handler(commands=['restart'])
def restart_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    run_cmd("systemctl restart strongswan")
    time.sleep(1)
    
    code, out, err = run_cmd("systemctl status strongswan --no-pager")
    if "active (running)" in out:
        bot.reply_to(message, "✅ VPN перезапущен")
    else:
        bot.reply_to(message, "⚠️ VPN не запустился. Проверь /status")

@bot.message_handler(func=lambda message: True)
def handle_all(message):
    if is_admin(message.from_user.id):
        bot.reply_to(message,
            "🤔 Не понял команду\n\n"
            "Доступные команды:\n"
            "/install - Установить VPN\n"
            "/new username - Создать пользователя\n"
            "/users - Список пользователей\n"
            "/del username - Удалить пользователя\n"
            "/status - Статус VPN\n"
            "/restart - Перезапустить VPN"
        )

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("🤖 VPN Бот запущен")
    print(f"👑 Админ: {ADMIN_ID}")
    bot.polling(none_stop=True, interval=0)