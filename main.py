import telebot
import os
import random
import string
import subprocess
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Нет TELEGRAM_BOT_TOKEN в окружении")

bot = telebot.TeleBot(TOKEN)
ADMIN_ID = "ВАШ_ТЕЛЕГРАМ_АЙДИ"  # Замените на ваш ID

# Проверка админа
def is_admin(user_id):
    return str(user_id) == ADMIN_ID

# Генерация пароля
def generate_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%^"
    return ''.join(random.choice(chars) for _ in range(length))

# Получение IP сервера
def get_server_ip():
    try:
        result = subprocess.run("curl -s ifconfig.me", 
                              shell=True, 
                              capture_output=True, 
                              text=True)
        return result.stdout.strip()
    except:
        return "ВАШ_IP_СЕРВЕРА"

@bot.message_handler(commands=['start'])
def start_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    bot.reply_to(message,
        "🔐 VPN Setup Bot\n\n"
        "Я помогу создать IKEv2 VPN на этом сервере.\n\n"
        "📋 Команды:\n"
        "/install - Установить IKEv2 VPN\n"
        "/details - Получить данные для iPhone\n"
        "/status - Статус VPN\n"
        "/restart - Перезапустить VPN"
    )

@bot.message_handler(commands=['install'])
def install_vpn(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    # Создаем кнопку подтверждения
    markup = telebot.types.InlineKeyboardMarkup()
    btn_yes = telebot.types.InlineKeyboardButton(
        "✅ Да, установить VPN", 
        callback_data="install_confirm"
    )
    btn_no = telebot.types.InlineKeyboardButton(
        "❌ Нет, отмена", 
        callback_data="install_cancel"
    )
    markup.add(btn_yes, btn_no)
    
    bot.send_message(
        message.chat.id,
        "⚠️ Это установит IKEv2 VPN на сервер.\n"
        "Продолжить?",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('install_'))
def handle_install_callback(call):
    if call.data == "install_confirm":
        bot.edit_message_text(
            "🔄 Начинаю установку VPN...",
            call.message.chat.id,
            call.message.message_id
        )
        
        try:
            # 1. Обновляем пакеты
            bot.send_message(call.message.chat.id, "📦 Обновляю пакеты...")
            os.system("apt-get update -y > /tmp/vpn_install.log 2>&1")
            
            # 2. Устанавливаем StrongSwan
            bot.send_message(call.message.chat.id, "📥 Устанавливаю StrongSwan...")
            os.system("apt-get install -y strongswan strongswan-pki > /tmp/vpn_install.log 2>&1")
            
            # 3. Генерируем данные
            server_ip = get_server_ip()
            vpn_user = "iphone_user"
            vpn_password = generate_password()
            
            # 4. Создаем сертификаты
            bot.send_message(call.message.chat.id, "🔐 Генерирую сертификаты...")
            
            cert_dir = "/etc/ipsec.d"
            os.system(f"mkdir -p {cert_dir}/private {cert_dir}/cacerts {cert_dir}/certs")
            
            # CA ключ и сертификат
            os.system(f"ipsec pki --gen --type rsa --size 4096 --outform pem > {cert_dir}/private/ca-key.pem")
            os.system(f"ipsec pki --self --ca --lifetime 3650 --in {cert_dir}/private/ca-key.pem --type rsa --dn 'CN=VPN CA' --outform pem > {cert_dir}/cacerts/ca-cert.pem")
            
            # Серверный ключ и сертификат
            os.system(f"ipsec pki --gen --type rsa --size 4096 --outform pem > {cert_dir}/private/server-key.pem")
            os.system(f"ipsec pki --pub --in {cert_dir}/private/server-key.pem --type rsa | ipsec pki --issue --lifetime 1825 --cacert {cert_dir}/cacerts/ca-cert.pem --cakey {cert_dir}/private/ca-key.pem --dn 'CN={server_ip}' --san {server_ip} --outform pem > {cert_dir}/certs/server-cert.pem")
            
            # 5. Создаем конфигурацию ipsec.conf
            bot.send_message(call.message.chat.id, "⚙️ Создаю конфигурацию...")
            
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
    eap_identity=%identity"""
            
            # Записываем в файл
            with open("/etc/ipsec.conf", "w") as f:
                f.write(ipsec_conf)
            
            # 6. Создаем файл с секретами
            ipsec_secrets = f"""# This file holds shared secrets or RSA private keys for authentication.

# RSA private key for this host, authenticating it to any other host
# which knows the public part.
: RSA "server-key.pem"

# Pre-shared key authentication
{vpn_user} : EAP "{vpn_password}"
"""
            
            with open("/etc/ipsec.secrets", "w") as f:
                f.write(ipsec_secrets)
            
            # 7. Включаем IP форвардинг
            os.system("sysctl -w net.ipv4.ip_forward=1")
            os.system('echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf')
            os.system("sysctl -p")
            
            # 8. Создаем простой фаервол
            firewall_rules = f"""#!/bin/bash
iptables -t nat -A POSTROUTING -s 10.10.10.0/24 -o eth0 -j MASQUERADE
iptables -A FORWARD -s 10.10.10.0/24 -j ACCEPT
iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A INPUT -p udp --dport 500 -j ACCEPT
iptables -A INPUT -p udp --dport 4500 -j ACCEPT"""
            
            with open("/tmp/iptables_rules.sh", "w") as f:
                f.write(firewall_rules)
            
            os.system("bash /tmp/iptables_rules.sh")
            
            # 9. Запускаем VPN
            bot.send_message(call.message.chat.id, "🚀 Запускаю VPN...")
            os.system("systemctl stop strongswan 2>/dev/null || true")
            os.system("systemctl start strongswan")
            os.system("systemctl enable strongswan")
            
            # 10. Проверяем
            result = os.popen("systemctl status strongswan").read()
            
            if "active (running)" in result:
                # Создаем файл с инструкциями
                instructions = f"""📱 ДАННЫЕ ДЛЯ ПОДКЛЮЧЕНИЯ НА IPHONE:

Сервер: {server_ip}
Удаленный ID: {server_ip}
Тип: IKEv2
Имя пользователя: {vpn_user}
Пароль: {vpn_password}

ИНСТРУКЦИЯ:
1. На iPhone: Настройки → Основные → VPN
2. Нажмите «Добавить конфигурацию VPN»
3. Выберите «Тип: IKEv2»
4. Заполните:
   - Описание: Мой VPN
   - Сервер: {server_ip}
   - Удаленный ID: {server_ip}
   - Локальный ID: (оставить пустым)
5. Введите имя пользователя и пароль
6. Нажмите «Готово»
7. Включите переключатель VPN

Дата установки: {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
                
                # Сохраняем инструкции в файл
                with open("/tmp/vpn_instructions.txt", "w") as f:
                    f.write(instructions)
                
                # Отправляем инструкции
                bot.send_message(call.message.chat.id, 
                    "✅ VPN успешно установлен!\n\n"
                    "📄 Отправляю инструкции для подключения..."
                )
                
                # Отправляем как документ
                with open("/tmp/vpn_instructions.txt", "rb") as f:
                    bot.send_document(call.message.chat.id, f)
                
                # И текстом для быстрого копирования
                bot.send_message(call.message.chat.id,
                    f"📋 **Быстрое копирование:**\n\n"
                    f"Сервер: `{server_ip}`\n"
                    f"Удаленный ID: `{server_ip}`\n"
                    f"Имя пользователя: `{vpn_user}`\n"
                    f"Пароль: `{vpn_password}`\n\n"
                    f"⚠️ Сохраните эти данные!",
                    parse_mode="Markdown"
                )
                
            else:
                bot.send_message(call.message.chat.id,
                    "⚠️ VPN установлен, но есть проблемы с запуском.\n"
                    "Проверьте: systemctl status strongswan"
                )
                
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Ошибка: {str(e)}")
            
    elif call.data == "install_cancel":
        bot.edit_message_text(
            "❌ Установка отменена",
            call.message.chat.id,
            call.message.message_id
        )

@bot.message_handler(commands=['details'])
def get_details(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    # Проверяем, установлен ли VPN
    if not os.path.exists("/etc/ipsec.secrets"):
        bot.reply_to(message, 
            "❌ VPN не установлен.\n"
            "Используйте /install для установки"
        )
        return
    
    # Читаем данные из файла
    try:
        with open("/etc/ipsec.secrets", "r") as f:
            content = f.read()
            
        # Ищем логин и пароль
        lines = content.split('\n')
        user = "iphone_user"
        password = ""
        
        for line in lines:
            if "EAP" in line and '"' in line:
                parts = line.split(':')
                if len(parts) > 1:
                    user = parts[0].strip()
                    # Извлекаем пароль из кавычек
                    if '"' in parts[1]:
                        start = parts[1].find('"') + 1
                        end = parts[1].find('"', start)
                        password = parts[1][start:end]
                        break
        
        server_ip = get_server_ip()
        
        if password:
            bot.reply_to(message,
                f"🔐 **Данные для подключения:**\n\n"
                f"Сервер: `{server_ip}`\n"
                f"Удаленный ID: `{server_ip}`\n"
                f"Имя пользователя: `{user}`\n"
                f"Пароль: `{password}`\n\n"
                f"📱 На iPhone:\n"
                f"1. Настройки → VPN\n"
                f"2. Добавить конфигурацию VPN\n"
                f"3. Тип: IKEv2\n"
                f"4. Используйте данные выше",
                parse_mode="Markdown"
            )
        else:
            bot.reply_to(message, 
                "Не удалось найти данные в конфигурации.\n"
                "Попробуйте переустановить VPN: /install"
            )
            
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")

@bot.message_handler(commands=['status'])
def check_status(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    # Проверяем статус StrongSwan
    result = os.popen("systemctl status strongswan 2>/dev/null || echo 'Сервис не найден'").read()
    
    if "active (running)" in result:
        # Проверяем активные соединения
        connections = os.popen("ipsec status 2>/dev/null || echo 'Нет активных соединений'").read()
        
        bot.reply_to(message,
            f"✅ VPN работает\n\n"
            f"Статус:\n```\n{result[:500]}\n```\n"
            f"Соединения:\n```\n{connections[:500]}\n```",
            parse_mode="Markdown"
        )
    else:
        bot.reply_to(message,
            f"❌ VPN не работает\n\n"
            f"Статус:\n```\n{result}\n```\n"
            f"Попробуйте: /install",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['restart'])
def restart_vpn(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    os.system("systemctl restart strongswan")
    
    # Проверяем
    result = os.popen("systemctl status strongswan").read()
    
    if "active (running)" in result:
        bot.reply_to(message, "✅ VPN перезапущен")
    else:
        bot.reply_to(message, 
            "⚠️ VPN перезапущен, но есть проблемы\n"
            "Подробности:\n```\n" + result + "\n```",
            parse_mode="Markdown"
        )

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    if is_admin(message.from_user.id):
        bot.reply_to(message,
            "Неизвестная команда\n\n"
            "Доступные команды:\n"
            "/start - Начать\n"
            "/install - Установить VPN\n"
            "/details - Данные для подключения\n"
            "/status - Статус VPN\n"
            "/restart - Перезапустить VPN"
        )
    else:
        bot.reply_to(message, "❌ Доступ запрещен!")

if __name__ == "__main__":
    print("🤖 VPN Setup Bot запущен...")
    print("👉 Отправьте /start в Telegram")
    bot.polling(none_stop=True)