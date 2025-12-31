from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from config import ADMIN_ID, BOT_TOKEN
import sqlite3
import os

# Состояния для добавления сервера
class AddServer(StatesGroup):
    host = State()
    ssh_port = State()
    ssh_username = State()
    ssh_method = State()
    ssh_password = State()
    ssh_key = State()

# 1. Кнопка "🖥 Сервера"
async def admin_servers(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    from keyboards import admin_servers_kb
    await message.answer("🖥 Управление серверами", reply_markup=admin_servers_kb)

# 2. Кнопка "➕ Добавить сервер" (начало)
async def add_server_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await AddServer.host.set()
    await message.answer("Введите IP адрес сервера:", reply_markup=types.ReplyKeyboardRemove())

# 3. Кнопка "📋 Список серверов"
async def list_servers(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, host, status, current_users, max_users FROM servers")
    servers = cursor.fetchall()
    conn.close()
    
    if servers:
        text = "📋 Список серверов:\n\n"
        for server in servers:
            text += f"🖥 ID: {server[0]}\n"
            text += f"🌐 IP: {server[1]}\n"
            text += f"📊 Пользователи: {server[3]}/{server[4]}\n"
            text += f"🔧 Статус: {server[2]}\n"
            text += "─" * 20 + "\n"
    else:
        text = "❌ Серверов нет"
    
    from keyboards import admin_servers_kb
    await message.answer(text, reply_markup=admin_servers_kb)

# 4. Кнопка "⚙️ Управление серверами"
async def manage_servers(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Выберите сервер для управления:", reply_markup=types.ReplyKeyboardRemove())
    # Здесь будет выбор сервера из списка

# 5. Кнопка "👥 Пользователи"
async def admin_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    from keyboards import admin_users_kb
    await message.answer("👥 Управление пользователями", reply_markup=admin_users_kb)

# 6. Кнопка "🎁 Выдать VPN"
async def give_vpn(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите ID пользователя для выдачи VPN:", reply_markup=types.ReplyKeyboardRemove())
    # Здесь будет логика выдачи

# 7. Кнопка "🚫 Отключить VPN"
async def disable_vpn(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите ID пользователя для отключения VPN:", reply_markup=types.ReplyKeyboardRemove())
    # Здесь будет логика отключения

# 8. Кнопка "💰 Метод оплаты" - ВЕБХУК
async def payment_method(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    # Генерируем URL вебхука для Tribute
    webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url=https://ваш-сервер.ру/tribute_webhook"
    
    instruction = (
        f"🔗 Вебхук для Tribute:\n\n"
        f"1. URL для настройки вебхука:\n"
        f"`{webhook_url}`\n\n"
        f"2. API ключ Tribute:\n"
        f"`42d4d099-20fd-4f55-a196-d77d9fed`\n\n"
        f"3. Инструкция:\n"
        f"• Зайдите в панель Tribute\n"
        f"• Добавьте этот URL как вебхук\n"
        f"• Укажите API ключ выше\n"
        f"• Бот будет получать уведомления об оплатах"
    )
    
    from keyboards import admin_main_kb
    await message.answer(instruction, parse_mode='Markdown', reply_markup=admin_main_kb)

# 9. Кнопка "📊 Статистика"
async def admin_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM servers WHERE status='active'")
    servers = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE status='active'")
    active_subs = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(amount) FROM payments WHERE status='success'")
    income = cursor.fetchone()[0] or 0
    
    stats = f"📊 Статистика:\n🖥 Серверов: {servers}\n👥 Пользователей: {users}\n📅 Подписок: {active_subs}\n💰 Доход: {income}₽"
    conn.close()
    
    from keyboards import admin_main_kb
    await message.answer(stats, reply_markup=admin_main_kb)

# 10. Кнопка "🔙 Назад" для админа
async def admin_back(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    from keyboards import admin_main_kb
    await message.answer("👑 Админ-панель", reply_markup=admin_main_kb)

# Регистрируем ВСЕ обработчики
def register_admin_handlers(dp: Dispatcher):
    dp.register_message_handler(admin_servers, text='🖥 Сервера', user_id=ADMIN_ID)
    dp.register_message_handler(add_server_start, text='➕ Добавить сервер', user_id=ADMIN_ID)
    dp.register_message_handler(list_servers, text='📋 Список серверов', user_id=ADMIN_ID)
    dp.register_message_handler(manage_servers, text='⚙️ Управление серверами', user_id=ADMIN_ID)
    dp.register_message_handler(admin_users, text='👥 Пользователи', user_id=ADMIN_ID)
    dp.register_message_handler(give_vpn, text='🎁 Выдать VPN', user_id=ADMIN_ID)
    dp.register_message_handler(disable_vpn, text='🚫 Отключить VPN', user_id=ADMIN_ID)
    dp.register_message_handler(payment_method, text='💰 Метод оплаты', user_id=ADMIN_ID)
    dp.register_message_handler(admin_stats, text='📊 Статистика', user_id=ADMIN_ID)
    dp.register_message_handler(admin_back, text='🔙 Назад', user_id=ADMIN_ID)