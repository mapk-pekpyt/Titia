import telebot
import os
import random
import string
import subprocess
import time
from datetime import datetime

# ========== НАСТРОЙКИ ==========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Нет TELEGRAM_BOT_TOKEN в окружении")

bot = telebot.TeleBot(TOKEN)
ADMIN_ID = "5791171535"  # Замени на свой ID (узнать у @userinfobot)
# ===============================

# Проверка админа
def is_admin(user_id):
    return str(user_id) == ADMIN_ID

# Генерация пароля
def generate_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))

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

# Запуск команды с выводом
def run_cmd(cmd, desc=""):
    if desc:
        print(f"[{desc}] {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

# ========== КОМАНДЫ БОТА ==========

@bot.message_handler(commands=['start'])
def start_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = telebot.types.KeyboardButton("📲 Установить VPN")
    btn2 = telebot.types.KeyboardButton("🔐 Данные для iPhone")
    btn3 = telebot.types.KeyboardButton("📊 Статус VPN")
    markup.add(btn1, btn2, btn3)
    
    bot.reply_to(message,
        "🔐 VPN Бот для iPhone\n\n"
        "Я установлю IKEv2 VPN на этот сервер и дам настройки для подключения.\n\n"
        "Нажми кнопку ниже или используй команды:\n"
        "/install - Установить VPN\n"
        "/details - Данные для подключения\n"
        "/status - Проверить работу\n"
        "/fix - Исправить проблемы\n"
        "/restart - Перезапустить VPN",
        reply_markup=markup
    )

@bot.message_handler(commands=['install'])
def install_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
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
            # Альтернативная установка
            run_cmd("apt-get install -y strongswan strongswan-pki", "Альт установка")
        
        # Шаг 3: Генерация данных
        bot.send_message(message.chat.id, "🔐 Шаг 3/7: Генерирую ключи и пароли...")
        
        server_ip = get_server_ip()
        vpn_user = "iphone"
        vpn_password = generate_password()
        
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
        
        # Конфиг ipsec.secrets
        ipsec_secrets = f""": RSA "server-key.pem"

{vpn_user} : EAP "{vpn_password}"
"""
        
        with open('/etc/ipsec.secrets', 'w') as f:
            f.write(ipsec_secrets)
        
        # Шаг 6: Настройка сети
        bot.send_message(message.chat.id, "🌐 Шаг 6/7: Настраиваю сеть...")
        
        # Включаем форвардинг
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
        
        # Останавливаем если запущен
        run_cmd("systemctl stop strongswan 2>/dev/null || true", "Остановка")
        run_cmd("systemctl stop strongswan-starter 2>/dev/null || true", "Остановка стартера")
        
        # Запускаем
        run_cmd("systemctl enable strongswan-starter", "Включение автозапуска")
        run_cmd("systemctl start strongswan-starter", "Запуск")
        
        # Ждем и проверяем
        time.sleep(3)
        
        code, out, err = run_cmd("systemctl status strongswan-starter --no-pager", "Проверка статуса")
        
        if "active (running)" in out or "active (running)" in err:
            # Успех! Сохраняем данные
            config_data = {
                "server_ip": server_ip,
                "username": vpn_user,
                "password": vpn_password,
                "installed": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open('/etc/vpn_config.json', 'w') as f:
                import json
                json.dump(config_data, f)
            
            # Отправляем инструкции
            instructions = f"""✅ **VPN УСПЕШНО УСТАНОВЛЕН!**

📱 **ДАННЫЕ ДЛЯ iPhone:**
Сервер: {server_ip}
Удаленный ID: {server_ip}
Локальный ID: (оставить пустым)
Тип: IKEv2
Имя пользователя: {vpn_user}
Пароль: {vpn_password}

📋 **КАК ПОДКЛЮЧИТЬ:**
1. iPhone → Настройки → Основные → VPN
2. Нажмите «Добавить конфигурацию VPN»
3. Выберите «Тип: IKEv2»
4. Введите данные выше
5. Нажмите «Готово» и включите VPN

🔧 **Если не подключается:**
- Попробуйте /fix в боте
- Или /restart для перезапуска

⚠️ **СОХРАНИ ЭТИ ДАННЫЕ!**
"""
            
            bot.send_message(message.chat.id, instructions, parse_mode="Markdown")
            
            # Отправляем еще раз для копирования
            bot.send_message(message.chat.id,
                f"📋 **Для быстрого копирования:**\n\n"
                f"Сервер: `{server_ip}`\n"
                f"Удаленный ID: `{server_ip}`\n"
                f"Имя пользователя: `{vpn_user}`\n"
                f"Пароль: `{vpn_password}`",
                parse_mode="Markdown"
            )
            
        else:
            # Пробуем альтернативный запуск
            run_cmd("ipsec start --nofork &", "Альтернативный запуск")
            time.sleep(2)
            
            code2, out2, err2 = run_cmd("ipsec status", "Проверка ipsec")
            
            if "Security Associations" in out2:
                bot.send_message(message.chat.id,
                    f"✅ VPN запущен (альтернативный метод)\n\n"
                    f"Сервер: `{server_ip}`\n"
                    f"Пользователь: `{vpn_user}`\n"
                    f"Пароль: `{vpn_password}`\n\n"
                    f"Используй /fix для нормальной установки сервиса.",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(message.chat.id,
                    f"⚠️ VPN установлен, но не запустился автоматически.\n\n"
                    f"Данные все равно созданы:\n"
                    f"Сервер: `{server_ip}`\n"
                    f"Пользователь: `{vpn_user}`\n"
                    f"Пароль: `{vpn_password}`\n\n"
                    f"Попробуй:\n"
                    f"1. /fix - исправить установку\n"
                    f"2. /restart - перезапустить\n"
                    f"3. Ручная команда: `sudo systemctl start strongswan-starter`",
                    parse_mode="Markdown"
                )
                
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка установки: {str(e)}")

@bot.message_handler(commands=['details'])
def details_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    try:
        # Пробуем прочитать сохраненную конфигурацию
        if os.path.exists('/etc/vpn_config.json'):
            import json
            with open('/etc/vpn_config.json', 'r') as f:
                config = json.load(f)
            
            bot.reply_to(message,
                f"🔐 **Сохраненные данные VPN:**\n\n"
                f"Сервер: `{config.get('server_ip', 'Неизвестно')}`\n"
                f"Имя пользователя: `{config.get('username', 'iphone')}`\n"
                f"Пароль: `{config.get('password', 'Неизвестно')}`\n\n"
                f"Установлен: {config.get('installed', 'Неизвестно')}",
                parse_mode="Markdown"
            )
        elif os.path.exists('/etc/ipsec.secrets'):
            # Читаем из файла
            with open('/etc/ipsec.secrets', 'r') as f:
                content = f.read()
            
            # Ищем данные
            import re
            match = re.search(r'(\w+)\s*:\s*EAP\s*"([^"]+)"', content)
            
            if match:
                username = match.group(1)
                password = match.group(2)
                server_ip = get_server_ip()
                
                bot.reply_to(message,
                    f"📄 **Данные из конфига:**\n\n"
                    f"Сервер: `{server_ip}`\n"
                    f"Имя пользователя: `{username}`\n"
                    f"Пароль: `{password}`",
                    parse_mode="Markdown"
                )
            else:
                bot.reply_to(message,
                    "📁 VPN файлы есть, но не могу найти данные.\n"
                    "Попробуй /install заново или /fix"
                )
        else:
            bot.reply_to(message,
                "❌ VPN не установлен.\n"
                "Используй /install для установки"
            )
            
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")

@bot.message_handler(commands=['status'])
def status_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    # Проверяем все возможные статусы
    checks = [
        ("strongswan-starter", "systemctl status strongswan-starter --no-pager"),
        ("strongswan", "systemctl status strongswan --no-pager"),
        ("ipsec", "ipsec status 2>/dev/null || echo 'ipsec не запущен'")
    ]
    
    results = []
    for name, cmd in checks:
        code, out, err = run_cmd(cmd)
        if "active (running)" in out or "active (running)" in err:
            results.append(f"✅ {name}: работает")
        elif "Security Associations" in out:
            results.append(f"✅ {name}: работает (ipsec)")
        else:
            results.append(f"❌ {name}: не работает")
    
    # Проверяем порты
    code, out, err = run_cmd("netstat -anu | grep -E ':500|:4500'")
    if "500" in out or "4500" in out:
        results.append("✅ Порт 500/4500: открыт")
    else:
        results.append("⚠️ Порт 500/4500: не слушает")
    
    # Собираем сообщение
    status_msg = "📊 **Статус VPN:**\n\n" + "\n".join(results)
    
    # Добавляем рекомендации
    if "не работает" in status_msg:
        status_msg += "\n\n🔧 Попробуй:\n/fix - исправить проблемы\n/restart - перезапустить"
    
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
        ("Проверяю конфиги", "ipsec rereadall 2>/dev/null || true"),
        ("Перезагружаю службу", "systemctl restart strongswan-starter")
    ]
    
    for desc, cmd in fix_commands:
        code, out, err = run_cmd(cmd)
        if code == 0:
            bot.send_message(message.chat.id, f"✓ {desc}")
        else:
            bot.send_message(message.chat.id, f"⚠️ {desc} - проблемы")
        time.sleep(1)
    
    # Проверяем результат
    code, out, err = run_cmd("systemctl status strongswan-starter --no-pager")
    if "active (running)" in out:
        bot.send_message(message.chat.id, "✅ VPN исправлен и запущен!")
    else:
        bot.send_message(message.chat.id,
            "⚠️ Есть проблемы с запуском.\n"
            "Попробуй:\n"
            "1. /restart\n"
            "2. Или установи заново: /install"
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

@bot.message_handler(func=lambda message: message.text == "📲 Установить VPN")
def button_install(message):
    install_command(message)

@bot.message_handler(func=lambda message: message.text == "🔐 Данные для iPhone")
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
    
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = telebot.types.KeyboardButton("📲 Установить VPN")
    btn2 = telebot.types.KeyboardButton("🔐 Данные для iPhone")
    btn3 = telebot.types.KeyboardButton("📊 Статус VPN")
    markup.add(btn1, btn2, btn3)
    
    bot.reply_to(message,
        "🤔 Не понял команду\n\n"
        "Доступные команды:\n"
        "/start - Показать меню\n"
        "/install - Установить VPN\n"
        "/details - Данные для iPhone\n"
        "/status - Проверить VPN\n"
        "/fix - Исправить проблемы\n"
        "/restart - Перезапустить VPN\n\n"
        "Или используй кнопки ниже",
        reply_markup=markup
    )

# ========== ЗАПУСК БОТА ==========
if __name__ == "__main__":
    print("🤖 VPN Бот запускается...")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("📱 Бот ждет команды /start в Telegram")
    
    # Проверяем что ADMIN_ID заменен
    if ADMIN_ID == "ВАШ_ТЕЛЕГРАМ_АЙДИ":
        print("⚠️ ВНИМАНИЕ: Не установлен ADMIN_ID!")
        print("Замени 'ВАШ_ТЕЛЕГРАМ_АЙДИ' на строке 12 на свой Telegram ID")
        print("Узнать ID: напиши /start боту @userinfobot")
    
    # Запускаем бота
    try:
        bot.polling(none_stop=True, interval=1)
    except Exception as e:
        print(f"❌ Ошибка бота: {e}")
        print("Перезапускаю через 5 секунд...")
        time.sleep(5)