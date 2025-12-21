import telebot
import os
import random
import string
import subprocess
import json
import time
import sqlite3
import re
import threading
from datetime import datetime
from pathlib import Path

# ========== НАСТРОЙКИ ==========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Нет TELEGRAM_BOT_TOKEN в окружении")

bot = telebot.TeleBot(TOKEN)
ADMIN_ID = "5791171535"
DB_FILE = "/etc/vpn_users.db"
CONFIGS_DIR = "/etc/vpn_configs"
# ===============================

# Создаем директории
Path(CONFIGS_DIR).mkdir(exist_ok=True)

# Глобальное подключение к БД
def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Инициализация БД
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vpn_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_username TEXT UNIQUE,
            vpn_username TEXT UNIQUE,
            vpn_password TEXT,
            device_type TEXT,
            l2tp_psk TEXT,
            config_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Проверка админа
def is_admin(user_id):
    return str(user_id) == ADMIN_ID

# Валидация Telegram username
def validate_telegram_username(username):
    if not username.startswith('@'):
        return False, "Имя пользователя должно начинаться с @"
    
    clean_name = username[1:].strip()
    if len(clean_name) < 3:
        return False, "Имя пользователя слишком короткое (мин. 3 символа)"
    if len(clean_name) > 32:
        return False, "Имя пользователя слишком длинное (макс. 32 символа)"
    
    if not re.match(r'^[a-zA-Z0-9_]+$', clean_name):
        return False, "Используйте только буквы, цифры и подчеркивания"
    
    return True, "OK"

# Экранирование для Markdown
def escape_markdown(text):
    if not text:
        return text
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

# Генерация PSK для L2TP
def generate_psk(length=20):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))

# Получение реального публичного IP
def get_server_ip():
    """Получает реальный публичный IP через несколько сервисов"""
    services = [
        "curl -s --max-time 5 https://api.ipify.org",
        "curl -s --max-time 5 https://icanhazip.com",
        "curl -s --max-time 5 https://checkip.amazonaws.com",
        "curl -s --max-time 5 https://ifconfig.me/ip",
    ]
    
    for service in services:
        try:
            result = subprocess.run(service, shell=True, capture_output=True, text=True, timeout=10)
            ip = result.stdout.strip()
            if ip and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                print(f"Определен IP: {ip}")
                return ip
        except:
            continue
    
    # Если не удалось определить, используем локальный
    try:
        result = subprocess.run("hostname -I | awk '{print $1}'", 
                              shell=True, capture_output=True, text=True)
        ip = result.stdout.strip()
        if ip:
            print(f"Используем локальный IP: {ip}")
            return ip
    except:
        pass
    
    return "ВАШ_IP_СЕРВЕРА"

# Получение активного сетевого интерфейса
def get_active_interface():
    """Получает активный сетевой интерфейс с default маршрутом"""
    try:
        result = subprocess.run(
            "ip route | grep '^default' | head -1 | awk '{print $5}'",
            shell=True, capture_output=True, text=True
        )
        iface = result.stdout.strip()
        if iface:
            print(f"Активный интерфейс: {iface}")
            return iface
    except:
        pass
    
    return "eth0"

# Генерация сильного пароля
def generate_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(random.choice(chars) for _ in range(length))
    
    # Гарантируем разные типы символов
    requirements = [
        (string.digits, any(c.isdigit() for c in password)),
        (string.ascii_uppercase, any(c.isupper() for c in password)),
        (string.ascii_lowercase, any(c.islower() for c in password)),
        ("!@#$%^&*", any(c in "!@#$%^&*" for c in password)),
    ]
    
    for chars_set, has_type in requirements:
        if not has_type:
            password = password[:-1] + random.choice(chars_set)
    
    return password

# Генерация уникального VPN логина
def generate_vpn_username():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for _ in range(30):
        timestamp = int(time.time()) % 1000000
        vpn_user = f"v{timestamp}{random.randint(100, 999)}"
        
        cursor.execute("SELECT 1 FROM vpn_users WHERE vpn_username = ?", (vpn_user,))
        if not cursor.fetchone():
            conn.close()
            return vpn_user
    
    conn.close()
    return f"user{''.join(random.choices(string.ascii_lowercase + string.digits, k=10))}"

# Проверка ОС и выбор менеджера пакетов
def get_package_manager():
    try:
        with open('/etc/os-release', 'r') as f:
            content = f.read().lower()
            if 'oracle' in content or 'ol' in content or 'centos' in content or 'rhel' in content:
                return 'dnf'
            elif 'ubuntu' in content or 'debian' in content:
                return 'apt'
        return 'apt'
    except:
        return 'apt'

# Выполнение команды
def run_cmd(cmd, timeout=30):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Таймаут команды"
    except Exception as e:
        return 1, "", str(e)

# Проверка установлен ли VPN
def is_vpn_installed():
    return os.path.exists('/etc/ipsec.conf') and os.path.exists('/etc/ipsec.secrets')

# Проверка работы VPN
def check_vpn_status():
    # Проверяем сервис
    code, out, err = run_cmd("systemctl is-active strongswan")
    if code == 0 and out.strip() == "active":
        return True, "✅ VPN сервис работает"
    
    # Проверяем подключения
    code2, out2, err2 = run_cmd("ipsec status 2>/dev/null || echo 'NO_IPSEC'")
    if "Security Associations" in out2:
        return True, "✅ VPN есть активные подключения"
    
    return False, "❌ VPN не работает"

# Проверка портов
def check_ports():
    commands = [
        "ss -anu | grep -E ':500|:4500|:1701'",
        "netstat -anu | grep -E ':500|:4500|:1701'",
    ]
    
    for cmd in commands:
        code, out, err = run_cmd(cmd)
        if out and ('500' in out or '4500' in out or '1701' in out):
            return True, "✅ Порт 500/4500/1701 открыт"
    
    return False, "⚠️ Порты VPN не слушают"

# ========== VPN УСТАНОВКА (асинхронная) ==========

def install_vpn_async(chat_id):
    """Асинхронная установка VPN в отдельном потоке"""
    def install():
        try:
            bot.send_message(chat_id, "🔄 Начинаю установку VPN в фоне...")
            
            pm = get_package_manager()
            server_ip = get_server_ip()
            iface = get_active_interface()
            
            bot.send_message(chat_id, f"🖥️ ОС: {pm.upper()}")
            bot.send_message(chat_id, f"🌐 Интерфейс: {iface}")
            bot.send_message(chat_id, f"📡 Сервер: {server_ip}")
            
            # 1. Установка пакетов
            bot.send_message(chat_id, "📦 Устанавливаю пакеты...")
            
            if pm == 'dnf':
                run_cmd("dnf install -y epel-release")
                run_cmd("dnf install -y strongswan strongswan-pki xl2tpd ppp")
            else:
                run_cmd("apt-get update -y")
                run_cmd("apt-get install -y strongswan strongswan-pki xl2tpd ppp")
            
            # 2. Сертификаты для IKEv2
            bot.send_message(chat_id, "🔐 Генерирую сертификаты...")
            run_cmd("mkdir -p /etc/ipsec.d/private /etc/ipsec.d/cacerts /etc/ipsec.d/certs")
            
            # Генерация ключей IKEv2
            ca_key = "/etc/ipsec.d/private/ca-key.pem"
            ca_cert = "/etc/ipsec.d/cacerts/ca-cert.pem"
            server_key = "/etc/ipsec.d/private/server-key.pem"
            server_cert = "/etc/ipsec.d/certs/server-cert.pem"
            
            run_cmd(f"ipsec pki --gen --type rsa --size 4096 --outform pem > {ca_key} 2>/dev/null || true")
            run_cmd(f"ipsec pki --self --ca --lifetime 3650 --in {ca_key} --type rsa --dn 'CN=VPN CA' --outform pem > {ca_cert} 2>/dev/null || true")
            run_cmd(f"ipsec pki --gen --type rsa --size 4096 --outform pem > {server_key} 2>/dev/null || true")
            run_cmd(f"ipsec pki --pub --in {server_key} --type rsa | ipsec pki --issue --lifetime 1825 --cacert {ca_cert} --cakey {ca_key} --dn 'CN={server_ip}' --san {server_ip} --outform pem > {server_cert} 2>/dev/null || true")
            
            # 3. Конфигурация IKEv2
            bot.send_message(chat_id, "⚙️ Настраиваю IKEv2...")
            
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
            
            # Секреты IKEv2
            with open('/etc/ipsec.secrets', 'w') as f:
                f.write(f': RSA "{server_key}"\n\n')
            
            # 4. Конфигурация L2TP/IPSec (будет дополняться пользователями)
            bot.send_message(chat_id, "⚙️ Настраиваю L2TP/IPSec...")
            
            # Дополнительный конфиг для L2TP
            ipsec_l2tp_conf = f"""
conn l2tp-psk
    auto=add
    left=%any
    leftid={server_ip}
    leftsubnet=0.0.0.0/0
    leftprotoport=17/1701
    right=%any
    rightprotoport=17/%any
    rightsubnet=10.10.20.0/24
    forceencaps=yes
    authby=secret
    pfs=no
    type=transport
    ike=aes256-sha2_256-modp2048!
    esp=aes256-sha2_256!
    keyingtries=%forever
    ikelifetime=24h
    lifetime=24h
    keyexchange=ikev1
"""
            
            with open('/etc/ipsec.conf', 'a') as f:
                f.write(ipsec_l2tp_conf)
            
            # Конфиг xl2tpd
            xl2tpd_conf = """[global]
ipsec saref = yes
saref refinfo = 30

[lns default]
ip range = 10.10.20.100-10.10.20.200
local ip = 10.10.20.1
require chap = yes
refuse pap = yes
require authentication = yes
name = l2tpd
ppp debug = no
pppoptfile = /etc/ppp/options.xl2tpd
length bit = yes
"""
            
            with open('/etc/xl2tpd/xl2tpd.conf', 'w') as f:
                f.write(xl2tpd_conf)
            
            # PPP options
            ppp_options = """ipcp-accept-local
ipcp-accept-remote
ms-dns 8.8.8.8
ms-dns 8.8.4.4
noccp
auth
crtscts
idle 1800
mtu 1280
mru 1280
lock
proxyarp
debug
name l2tpd
password-serv
"""
            
            with open('/etc/ppp/options.xl2tpd', 'w') as f:
                f.write(ppp_options)
            
            # Создаем chap-secrets файл
            with open('/etc/ppp/chap-secrets', 'w') as f:
                f.write('# Secrets for authentication using CHAP\n')
                f.write('# client    server  secret          IP addresses\n')
            
            # 5. Настройка сети
            bot.send_message(chat_id, "🌐 Настраиваю сеть...")
            
            run_cmd("sysctl -w net.ipv4.ip_forward=1")
            run_cmd('echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf')
            run_cmd("sysctl -p")
            
            # Безопасные правила iptables (добавляем, не чистим)
            iptables_rules = f'''#!/bin/bash
# IKEv2
iptables -t nat -A POSTROUTING -s 10.10.10.0/24 -o {iface} -j MASQUERADE 2>/dev/null || true
# L2TP
iptables -t nat -A POSTROUTING -s 10.10.20.0/24 -o {iface} -j MASQUERADE 2>/dev/null || true

# Форвардинг
iptables -A FORWARD -s 10.10.10.0/24 -j ACCEPT 2>/dev/null || true
iptables -A FORWARD -s 10.10.20.0/24 -j ACCEPT 2>/dev/null || true
iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true

# Порты
iptables -A INPUT -p udp --dport 500 -j ACCEPT 2>/dev/null || true
iptables -A INPUT -p udp --dport 4500 -j ACCEPT 2>/dev/null || true
iptables -A INPUT -p udp --dport 1701 -j ACCEPT 2>/dev/null || true
'''
            
            with open('/tmp/vpn_firewall.sh', 'w') as f:
                f.write(iptables_rules)
            
            run_cmd("bash /tmp/vpn_firewall.sh")
            
            # 6. Запуск сервисов
            bot.send_message(chat_id, "🚀 Запускаю сервисы...")
            
            run_cmd("systemctl stop strongswan 2>/dev/null || true")
            run_cmd("systemctl stop xl2tpd 2>/dev/null || true")
            
            run_cmd("systemctl start strongswan")
            run_cmd("systemctl start xl2tpd")
            
            run_cmd("systemctl enable strongswan")
            run_cmd("systemctl enable xl2tpd")
            
            time.sleep(3)
            
            # Проверка
            vpn_ok, vpn_msg = check_vpn_status()
            ports_ok, ports_msg = check_ports()
            
            # Сохраняем инфу
            vpn_info = {
                "server_ip": server_ip,
                "interface": iface,
                "installed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "package_manager": pm,
                "has_ikev2": True,
                "has_l2tp": True
            }
            
            with open('/etc/vpn_info.json', 'w') as f:
                json.dump(vpn_info, f, indent=2)
            
            bot.send_message(chat_id,
                f"✅ **VPN УСТАНОВЛЕН!**\n\n"
                f"📡 Сервер: `{server_ip}`\n"
                f"🔐 Поддерживаемые протоколы:\n"
                f"  • IKEv2 (для iPhone)\n"
                f"  • L2TP/IPSec (для Android)\n\n"
                f"{vpn_msg}\n"
                f"{ports_msg}\n\n"
                f"💡 Создать пользователя: /new",
                parse_mode="Markdown"
            )
            
        except Exception as e:
            error_msg = str(e)[:500]
            bot.send_message(chat_id, f"❌ Ошибка установки: {error_msg}")
            print(f"Install error: {e}")
    
    # Запускаем в отдельном потоке
    thread = threading.Thread(target=install)
    thread.daemon = True
    thread.start()

# ========== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ==========

def add_vpn_user_to_config(vpn_user, vpn_pass, l2tp_psk, device_type):
    """Добавить пользователя в конфиг в зависимости от устройства"""
    try:
        if device_type == "iphone":
            # IKEv2 - в ipsec.secrets
            with open('/etc/ipsec.secrets', 'a') as f:
                f.write(f'{vpn_user} : EAP "{vpn_pass}"\n')
        else:  # android
            # L2TP - PSK в ipsec.secrets
            with open('/etc/ipsec.secrets', 'a') as f:
                f.write(f'{vpn_user} : PSK "{l2tp_psk}"\n')
            
            # L2TP - логин/пароль в chap-secrets
            with open('/etc/ppp/chap-secrets', 'a') as f:
                f.write(f'"{vpn_user}" l2tpd "{vpn_pass}" *\n')
        
        run_cmd("ipsec rereadall 2>/dev/null || true")
        return True
    except Exception as e:
        print(f"Add to config error: {e}")
        return False

def remove_vpn_user_from_config(vpn_user, device_type):
    """Удалить пользователя из конфига"""
    try:
        # Удаляем из ipsec.secrets
        if os.path.exists('/etc/ipsec.secrets'):
            with open('/etc/ipsec.secrets', 'r') as f:
                lines = f.readlines()
            
            new_lines = []
            pattern_ikev2 = re.compile(rf'^\s*{re.escape(vpn_user)}\s*:\s*EAP\s*"')
            pattern_l2tp = re.compile(rf'^\s*{re.escape(vpn_user)}\s*:\s*PSK\s*"')
            
            for line in lines:
                if not pattern_ikev2.match(line.strip()) and not pattern_l2tp.match(line.strip()):
                    new_lines.append(line)
            
            with open('/etc/ipsec.secrets', 'w') as f:
                f.writelines(new_lines)
        
        # Удаляем из chap-secrets для Android
        if device_type == "android" and os.path.exists('/etc/ppp/chap-secrets'):
            with open('/etc/ppp/chap-secrets', 'r') as f:
                lines = f.readlines()
            
            new_lines = []
            pattern = re.compile(rf'^\s*"{re.escape(vpn_user)}"')
            
            for line in lines:
                if not pattern.match(line.strip()):
                    new_lines.append(line)
            
            with open('/etc/ppp/chap-secrets', 'w') as f:
                f.writelines(new_lines)
        
        run_cmd("ipsec rereadall 2>/dev/null || true")
        return True
    except Exception as e:
        print(f"Remove from config error: {e}")
        return False

def get_all_users_from_db():
    """Получить всех пользователей из БД"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT telegram_username, vpn_username, vpn_password, device_type, l2tp_psk, config_file, created_at 
            FROM vpn_users 
            ORDER BY created_at DESC
        ''')
        users = cursor.fetchall()
        return [dict(user) for user in users] if users else []
    except Exception as e:
        print(f"DB fetch error: {e}")
        return []
    finally:
        conn.close()

# ========== ГЕНЕРАЦИЯ КОНФИГОВ ==========

def generate_config_file(tg_username, vpn_user, vpn_pass, l2tp_psk, device_type, server_ip):
    """Генерирует конфигурационный файл для пользователя"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_name = tg_username[1:] if tg_username.startswith('@') else tg_username
    filename = f"{clean_name}_{device_type}_{timestamp}"
    
    if device_type == "iphone":
        # Генерируем .mobileconfig для iPhone (исправленная версия)
        config_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>IKEv2</key>
            <dict>
                <key>AuthenticationMethod</key>
                <string>Username</string>
                <key>DeadPeerDetectionRate</key>
                <string>Medium</string>
                <key>DisableRedirect</key>
                <true/>
                <key>EnablePFS</key>
                <integer>1</integer>
                <key>ExtendedAuthEnabled</key>
                <integer>1</integer>
                <key>LocalIdentifier</key>
                <string>{vpn_user}</string>
                <key>LocalIdentifierType</key>
                <string>KeyID</string>
                <key>PayloadCertificateUUID</key>
                <string>00000000-0000-0000-0000-000000000000</string>
                <key>RemoteAddress</key>
                <string>{server_ip}</string>
                <key>RemoteIdentifier</key>
                <string>{server_ip}</string>
                <key>RemoteIdentifierType</key>
                <string>Address</string>
                <key>ServerCertificateIssuerCommonName</key>
                <string>VPN CA</string>
                <key>UseConfigurationAttributeInternalIPSubnet</key>
                <integer>0</integer>
                <key>IKESecurityAssociationParameters</key>
                <dict>
                    <key>DiffieHellmanGroup</key>
                    <integer>14</integer>
                    <key>EncryptionAlgorithm</key>
                    <string>AES-256</string>
                    <key>IntegrityAlgorithm</key>
                    <string>SHA2-256</string>
                </dict>
                <key>ChildSecurityAssociationParameters</key>
                <dict>
                    <key>DiffieHellmanGroup</key>
                    <integer>14</integer>
                    <key>EncryptionAlgorithm</key>
                    <string>AES-256</string>
                    <key>IntegrityAlgorithm</key>
                    <string>SHA2-256</string>
                </dict>
            </dict>
            <key>IPv4</key>
            <dict>
                <key>OverridePrimary</key>
                <integer>1</integer>
            </dict>
            <key>PPP</key>
            <dict>
                <key>AuthName</key>
                <string>{vpn_user}</string>
                <key>AuthPassword</key>
                <string>{vpn_pass}</string>
                <key>CommRemoteAddress</key>
                <string>{server_ip}</string>
            </dict>
            <key>PayloadDescription</key>
            <string>Настройки VPN IKEv2 для {tg_username}</string>
            <key>PayloadDisplayName</key>
            <string>VPN {server_ip}</string>
            <key>PayloadIdentifier</key>
            <string>com.apple.vpn.managed.{filename}</string>
            <key>PayloadType</key>
            <string>com.apple.vpn.managed</string>
            <key>PayloadUUID</key>
            <string>{str(random.getrandbits(128))}</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
            <key>Proxies</key>
            <dict/>
            <key>UserDefinedName</key>
            <string>VPN {server_ip}</string>
            <key>VPNType</key>
            <string>IKEv2</string>
        </dict>
    </array>
    <key>PayloadDescription</key>
    <string>VPN профиль IKEv2 для {tg_username}</string>
    <key>PayloadDisplayName</key>
    <string>VPN Конфигурация ({server_ip})</string>
    <key>PayloadIdentifier</key>
    <string>com.vpn.profile.{filename}</string>
    <key>PayloadOrganization</key>
    <string>VPN Сервис</string>
    <key>PayloadRemovalDisallowed</key>
    <false/>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>{str(random.getrandbits(128))}</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>"""
        
        filepath = f"{CONFIGS_DIR}/{filename}.mobileconfig"
        with open(filepath, 'w') as f:
            f.write(config_content)
        
        return filepath, ".mobileconfig"
    
    else:  # android
        # Генерируем инструкцию для Android L2TP/IPSec
        config_content = f"""# L2TP/IPSec VPN конфигурация для {tg_username}
# Сервер: {server_ip}
# Имя пользователя: {vpn_user}
# Пароль: {vpn_pass}
# PSK (Pre-Shared Key): {l2tp_psk}
# Тип: L2TP/IPSec PSK

ИНСТРУКЦИЯ ДЛЯ ANDROID:

1. Настройки → Сеть и интернет → VPN
2. Нажмите "+" или "Добавить VPN"
3. Заполните:
   - Имя: VPN {server_ip}
   - Тип: L2TP/IPSec PSK
   - Адрес сервера: {server_ip}
   - IPSec identifier: (оставить пустым)
   - IPSec pre-shared key: {l2tp_psk}
   - Имя пользователя: {vpn_user}
   - Пароль: {vpn_pass}
4. Сохраните и подключитесь

АЛЬТЕРНАТИВНЫЙ СПОСОБ:
1. Установите приложение "StrongSwan VPN Client"
2. Создайте новый профиль:
   - Gateway: {server_ip}
   - Type: L2TP/IPSec PSK
   - Username: {vpn_user}
   - Password: {vpn_pass}
   - PSK: {l2tp_psk}
3. Подключитесь

ТЕХНИЧЕСКИЕ ДАННЫЕ:
• Сервер: {server_ip}
• Протокол: L2TP/IPSec
• Порт: 1701 (L2TP), 500/4500 (IPSec)
• Шифрование: AES-256
• Аутентификация: MS-CHAPv2
"""
        
        filepath = f"{CONFIGS_DIR}/{filename}.txt"
        with open(filepath, 'w') as f:
            f.write(config_content)
        
        return filepath, ".txt"

# ========== КОМАНДЫ БОТА ==========

def send_main_menu(chat_id, message_text="Выберите действие:"):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📲 Установить VPN", "👥 Пользователи", "📊 Статус VPN")
    bot.send_message(chat_id, message_text, reply_markup=markup)

@bot.message_handler(commands=['start', 'menu'])
def start_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    send_main_menu(message.chat.id,
        "🔐 VPN Бот с поддержкой iPhone/Android\n\n"
        "📱 Поддерживаемые протоколы:\n"
        "• iPhone → IKEv2 (современный, безопасный)\n"
        "• Android → L2TP/IPSec (универсальный)\n\n"
        "📋 Команды:\n"
        "/install - Установить VPN\n"
        "/new - Создать пользователя\n"
        "/users - Список пользователей\n"
        "/del @user - Удалить\n"
        "/status - Статус VPN"
    )

@bot.message_handler(commands=['install'])
def install_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    if is_vpn_installed():
        bot.reply_to(message, "✅ VPN уже установлен\nИспользуй /new для создания пользователей")
        return
    
    # Запускаем асинхронную установку
    bot.reply_to(message, "🔄 Запускаю установку в фоне...\nЭто займет 2-3 минуты.")
    install_vpn_async(message.chat.id)

@bot.message_handler(commands=['new'])
def new_user_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    if not is_vpn_installed():
        bot.reply_to(message, "❌ VPN не установлен. Сначала /install")
        return
    
    # Запрашиваем имя пользователя
    msg = bot.reply_to(message, "Введите Telegram username (например: @ivanov):")
    bot.register_next_step_handler(msg, ask_device_type)

def ask_device_type(message):
    """Спрашиваем тип устройства"""
    tg_username = message.text.strip()
    
    is_valid, validation_msg = validate_telegram_username(tg_username)
    if not is_valid:
        bot.reply_to(message, f"❌ {validation_msg}")
        send_main_menu(message.chat.id)
        return
    
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📱 iPhone (IKEv2)", "🤖 Android (L2TP)")
    msg = bot.reply_to(message, f"Выберите устройство для {tg_username}:", reply_markup=markup)
    bot.register_next_step_handler(msg, lambda m: process_device_choice(m, tg_username))

def process_device_choice(message, tg_username):
    """Обрабатываем выбор устройства"""
    choice = message.text.lower()
    
    if "iphone" in choice:
        device_type = "iphone"
    elif "android" in choice:
        device_type = "android"
    else:
        bot.reply_to(message, "❌ Неверный выбор. Используйте кнопки.")
        send_main_menu(message.chat.id)
        return
    
    send_main_menu(message.chat.id)
    create_user(message, tg_username, device_type)

def create_user(message, tg_username, device_type):
    """Создаем нового пользователя"""
    # Генерируем уникальные VPN данные
    vpn_user = generate_vpn_username()
    vpn_pass = generate_password()
    l2tp_psk = generate_psk() if device_type == "android" else None
    server_ip = get_server_ip()
    
    # Добавляем в конфиг
    if add_vpn_user_to_config(vpn_user, vpn_pass, l2tp_psk, device_type):
        # Генерируем конфиг файл
        config_file, config_ext = generate_config_file(tg_username, vpn_user, vpn_pass, l2tp_psk, device_type, server_ip)
        
        # Сохраняем в БД
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO vpn_users (telegram_username, vpn_username, vpn_password, device_type, l2tp_psk, config_file)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (tg_username, vpn_user, vpn_pass, device_type, l2tp_psk, config_file))
            conn.commit()
            
            # Отправляем данные
            if device_type == "iphone":
                protocol_info = "IKEv2 (iPhone)"
                setup_info = "📱 **Для iPhone:**\n1. Откройте файл .mobileconfig\n2. Разрешите установку профиля\n3. Перейдите в Настройки → Основные → VPN\n4. Активируйте подключение\n\n"
                config_note = "Файл .mobileconfig содержит все настройки для автоматической установки."
            else:
                protocol_info = "L2TP/IPSec (Android)"
                setup_info = "🤖 **Для Android:**\n1. Настройки → Сеть и интернет → VPN\n2. Добавьте новое подключение L2TP/IPSec PSK\n3. Используйте данные ниже\n\n"
                config_note = "Файл .txt содержит инструкцию для ручной настройки."
            
            # Основное сообщение с данными
            response = f"✅ **Пользователь создан!**\n\n"
            response += f"👤 TG: {tg_username}\n"
            response += f"📱 Устройство: {device_type.upper()}\n"
            response += f"🔐 Протокол: {protocol_info}\n"
            response += f"🌐 Сервер: `{server_ip}`\n"
            response += f"👤 VPN логин: `{vpn_user}`\n"
            response += f"🔑 VPN пароль: `{escape_markdown(vpn_pass)}`\n"
            
            if device_type == "android":
                response += f"🔐 PSK ключ: `{escape_markdown(l2tp_psk)}`\n"
            
            response += f"\n{setup_info}"
            response += f"📋 **Ручная настройка:**\n"
            response += f"• Тип: {'IKEv2' if device_type == 'iphone' else 'L2TP/IPSec PSK'}\n"
            response += f"• Сервер: {server_ip}\n"
            response += f"• Имя пользователя: {vpn_user}\n"
            response += f"• Пароль: {vpn_pass}\n"
            
            if device_type == "android":
                response += f"• PSK: {l2tp_psk}\n"
            
            response += f"• Удаленный ID: {server_ip}\n"
            
            bot.send_message(message.chat.id, response, parse_mode="Markdown")
            
            # Отправляем конфиг файл
            try:
                with open(config_file, 'rb') as f:
                    caption = f"📁 Конфигурация для {tg_username} ({device_type})"
                    if device_type == "iphone":
                        bot.send_document(message.chat.id, f, caption=caption)
                    else:
                        bot.send_document(message.chat.id, f, caption=caption)
            except Exception as e:
                print(f"Error sending config: {e}")
                bot.send_message(message.chat.id, f"⚠️ Файл конфигурации сохранен на сервере: {config_file}")
            
        except sqlite3.IntegrityError:
            bot.reply_to(message, f"❌ Пользователь {tg_username} уже существует")
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка: {str(e)[:100]}")
        finally:
            conn.close()
    else:
        bot.reply_to(message, "❌ Ошибка добавления пользователя в VPN конфиг")

@bot.message_handler(commands=['users'])
def users_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    users = get_all_users_from_db()
    
    if not users:
        bot.reply_to(message, "📭 Нет пользователей")
        return
    
    server_ip = get_server_ip()
    response = f"👥 **ПОЛЬЗОВАТЕЛИ VPN**\n\n"
    response += f"📡 Сервер: `{server_ip}`\n"
    response += f"📊 Всего: {len(users)} пользователей\n\n"
    
    ikev2_count = sum(1 for u in users if u['device_type'] == 'iphone')
    l2tp_count = sum(1 for u in users if u['device_type'] == 'android')
    
    response += f"📱 IKEv2 (iPhone): {ikev2_count}\n"
    response += f"🤖 L2TP (Android): {l2tp_count}\n\n"
    
    for i, user in enumerate(users[:15], 1):  # Показываем первые 15
        tg_user = user['telegram_username']
        vpn_user = user['vpn_username']
        device = user['device_type']
        created_at = user['created_at']
        
        # Иконка устройства
        icon = "📱" if device == "iphone" else "🤖"
        
        # Форматируем дату
        try:
            if isinstance(created_at, str):
                created = datetime.fromisoformat(created_at.replace('Z', '+00:00')).strftime('%d.%m')
            else:
                created = created_at.strftime('%d.%m')
        except:
            created = str(created_at)[5:10]
        
        response += f"{i}. {icon} {tg_user}\n"
        response += f"   Логин: `{vpn_user}`\n"
        response += f"   Устройство: {device}\n"
        response += f"   Создан: {created}\n"
        if i < len(users[:15]):
            response += "   ─────\n"
    
    if len(users) > 15:
        response += f"\n... и еще {len(users)-15} пользователей"
    
    response += f"\n📋 Команды:\n"
    response += "/new - добавить\n"
    response += "/del @user - удалить"
    
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
    
    tg_username = args[1].strip()
    if not tg_username.startswith('@'):
        tg_username = '@' + tg_username
    
    # Ищем пользователя в БД
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT vpn_username, device_type, config_file FROM vpn_users WHERE telegram_username = ?', (tg_username,))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        bot.reply_to(message, f"❌ Пользователь {tg_username} не найден")
        return
    
    vpn_username = result['vpn_username']
    device_type = result['device_type']
    config_file = result['config_file']
    
    # Удаляем из конфига
    if remove_vpn_user_from_config(vpn_username, device_type):
        # Удаляем из БД
        cursor.execute('DELETE FROM vpn_users WHERE telegram_username = ?', (tg_username,))
        conn.commit()
        conn.close()
        
        # Удаляем конфиг файл
        if config_file and os.path.exists(config_file):
            try:
                os.remove(config_file)
            except:
                pass
        
        bot.reply_to(message, f"✅ Пользователь {tg_username} удален")
    else:
        conn.close()
        bot.reply_to(message, f"❌ Ошибка удаления пользователя {tg_username}")

@bot.message_handler(commands=['status'])
def status_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    vpn_ok, vpn_msg = check_vpn_status()
    ports_ok, ports_msg = check_ports()
    
    if is_vpn_installed():
        users = get_all_users_from_db()
        user_count = len(users)
        
        response = f"📊 **СТАТУС VPN**\n\n"
        response += f"{vpn_msg}\n"
        response += f"{ports_msg}\n"
        response += f"👥 Пользователей: {user_count}\n"
        
        # Информация о сервере
        try:
            if os.path.exists('/etc/vpn_info.json'):
                with open('/etc/vpn_info.json', 'r') as f:
                    info = json.load(f)
                response += f"📡 IP: `{info.get('server_ip', '?')}`\n"
                if info.get('has_ikev2'):
                    response += "📱 IKEv2: ✅\n"
                if info.get('has_l2tp'):
                    response += "🤖 L2TP: ✅\n"
        except:
            pass
        
        response += f"\n💡 Команды:\n"
        response += "/users - список\n"
        response += "/new - добавить\n"
        response += "/restart - перезапустить"
        
        bot.reply_to(message, response, parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ VPN не установлен\nИспользуй /install для установки")

@bot.message_handler(commands=['restart'])
def restart_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    bot.reply_to(message, "🔄 Перезапускаю VPN...")
    
    run_cmd("systemctl restart strongswan")
    run_cmd("systemctl restart xl2tpd")
    time.sleep(2)
    
    vpn_ok, vpn_msg = check_vpn_status()
    
    if vpn_ok:
        bot.reply_to(message, "✅ VPN перезапущен и работает")
    else:
        bot.reply_to(message, f"⚠️ VPN перезапущен, но {vpn_msg}")

# Обработчики кнопок
@bot.message_handler(func=lambda message: message.text in ["📲 Установить VPN", "👥 Пользователи", "📊 Статус VPN"])
def handle_buttons(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    if message.text == "📲 Установить VPN":
        install_command(message)
    elif message.text == "👥 Пользователи":
        users_command(message)
    elif message.text == "📊 Статус VPN":
        status_command(message)

@bot.message_handler(func=lambda message: True)
def handle_all(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Доступ запрещен!")
        return
    
    send_main_menu(message.chat.id,
        "🤔 Не понял команду\n\n"
        "📋 **Основные команды:**\n"
        "/install - Установить VPN\n"
        "/new - Создать пользователя\n"
        "/users - Список пользователей\n"
        "/del @user - Удалить пользователя\n"
        "/status - Статус VPN\n"
        "/restart - Перезапустить VPN"
    )

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("=" * 50)
    print("🤖 VPN Бот запущен")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print(f"💾 База данных: {DB_FILE}")
    print(f"📁 Конфиги: {CONFIGS_DIR}")
    print("=" * 50)
    
    # Проверяем права (должны быть root)
    if os.geteuid() != 0:
        print("⚠️ ВНИМАНИЕ: Бот должен запускаться от root!")
        print("Запустите: sudo python bot.py")
        exit(1)
    
    if is_vpn_installed():
        print("✅ VPN уже установлен")
        vpn_ok, vpn_msg = check_vpn_status()
        print(f"   Статус: {vpn_msg}")
    else:
        print("⚠️ VPN не установлен. Используйте /install")
    
    print("📱 Бот ожидает команд...")
    
    try:
        bot.polling(none_stop=True, interval=0, timeout=30)
    except Exception as e:
        print(f"❌ Ошибка бота: {e}")
        print("Перезапуск через 10 секунд...")
        time.sleep(10)