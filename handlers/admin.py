from aiogram import types, Dispatcher
from config import ADMIN_ID
import sqlite3

async def admin_servers(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    from keyboards import admin_servers_kb
    await message.answer("🖥 Управление серверами", reply_markup=admin_servers_kb)

async def admin_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    from keyboards import admin_users_kb
    await message.answer("👥 Управление пользователями", reply_markup=admin_users_kb)

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
    await message.answer(stats)

async def admin_back(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    from keyboards import admin_main_kb
    await message.answer("👑 Админ-панель", reply_markup=admin_main_kb)

def register_admin_handlers(dp: Dispatcher):
    dp.register_message_handler(admin_servers, text='🖥 Сервера', user_id=ADMIN_ID)
    dp.register_message_handler(admin_users, text='👥 Пользователи', user_id=ADMIN_ID)
    dp.register_message_handler(admin_stats, text='📊 Статистика', user_id=ADMIN_ID)
    dp.register_message_handler(admin_back, text='🔙 Назад', user_id=ADMIN_ID)