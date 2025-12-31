from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from config import ADMIN_ID, ADMIN_CHAT_ID, TRIBUTE_API_KEY
from database import init_db, get_db
import sqlite3
import os

class AddServer(StatesGroup):
    host = State()
    ssh_port = State()
    ssh_username = State()
    ssh_method = State()
    ssh_password = State()
    ssh_key = State()

async def admin_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("👑 Админ-панель", reply_markup=admin_main_kb)

async def admin_servers(message: types.Message):
    await message.answer("🖥 Управление серверами", reply_markup=admin_servers_kb)

async def admin_users(message: types.Message):
    await message.answer("👥 Управление пользователями", reply_markup=admin_users_kb)

async def admin_stats(message: types.Message):
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    
    # Статистика
    cursor.execute("SELECT COUNT(*) FROM servers WHERE status='active'")
    servers = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE status='active'")
    active_subs = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(amount) FROM payments WHERE status='success'")
    income = cursor.fetchone()[0] or 0
    
    stats = (
        f"📊 Статистика:\n"
        f"🖥 Активных серверов: {servers}\n"
        f"👥 Пользователей: {users}\n"
        f"📅 Активных подписок: {active_subs}\n"
        f"💰 Общий доход: {income}₽"
    )
    
    conn.close()
    await message.answer(stats)

async def add_server_start(message: types.Message):
    await AddServer.host.set()
    await message.answer("Введите IP сервера:", reply_markup=back_kb)

async def process_host(message: types.Message, state: FSMContext):
    if message.text == '🔙 Назад':
        await state.finish()
        await message.answer("Отменено", reply_markup=admin_servers_kb)
        return
        
    async with state.proxy() as data:
        data['host'] = message.text
    
    await AddServer.next()
    await message.answer("Введите SSH порт (по умолчанию 22):")

# ... остальные обработчики состояний для добавления сервера

def register_admin_handlers(dp: Dispatcher):
    dp.register_message_handler(admin_start, commands=['admin'], user_id=ADMIN_ID)
    dp.register_message_handler(admin_servers, text='🖥 Сервера', user_id=ADMIN_ID)
    dp.register_message_handler(admin_users, text='👥 Пользователи', user_id=ADMIN_ID)
    dp.register_message_handler(admin_stats, text='📊 Статистика', user_id=ADMIN_ID)
    dp.register_message_handler(add_server_start, text='➕ Добавить сервер', user_id=ADMIN_ID)