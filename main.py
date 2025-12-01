import os
import telebot
import importlib
import pkgutil

TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# -------- ПОДГРУЗКА ПЛАГИНОВ --------
def load_plugins():
    import plugins
    for loader, module_name, is_pkg in pkgutil.iter_modules(plugins.__path__):
        module = importlib.import_module(f"plugins.{module_name}")
        if hasattr(module, "register"):
            module.register(bot)
            print(f"[PLUGIN LOADED] {module_name}")

load_plugins()

# -------- СТАРТ БОТА --------
if __name__ == "__main__":
    print("Bot started.")
    bot.infinity_polling(skip_pending=True)