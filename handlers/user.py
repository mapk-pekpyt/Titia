from aiogram import types, Dispatcher
from config import SUPPORT_USERNAME, ADMIN_ID
import sqlite3
import datetime

async def get_vpn(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    from keyboards import tariffs_kb
    await message.answer("Выберите тариф:", reply_markup=tariffs_kb)

async def process_trial(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    from keyboards import user_main_kb
    
    user_id = message.from_user.id
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT trial_used FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()
    
    if not user or user[0] == 0:
        end_date = datetime.datetime.now() + datetime.timedelta(days=1)
        cursor.execute('INSERT INTO subscriptions (user_id, tariff, status, start_date, end_date) VALUES (?, "trial", "active", datetime("now"), ?)',
                      (user_id, end_date))
        cursor.execute("UPDATE users SET trial_used=1 WHERE id=?", (user_id,))
        conn.commit()
        await message.answer("🎁 Пробный период активирован на 1 день! Ожидайте данные от администратора.", reply_markup=user_main_kb)
    else:
        await message.answer("❌ Вы уже использовали пробный период.", reply_markup=user_main_kb)
    
    conn.close()

async def my_subscription(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    from keyboards import user_main_kb
    await message.answer("📄 Ваша подписка будет здесь", reply_markup=user_main_kb)

async def help_command(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    from keyboards import user_main_kb
    await message.answer(f"🆘 Помощь\n\nТехподдержка: {SUPPORT_USERNAME}", reply_markup=user_main_kb)

async def user_back(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    from keyboards import user_main_kb
    await message.answer("Главное меню:", reply_markup=user_main_kb)

def register_user_handlers(dp: Dispatcher):
    dp.register_message_handler(get_vpn, text='🔑 Получить VPN')
    dp.register_message_handler(process_trial, text='🎁 Пробник (1 день)')
    dp.register_message_handler(my_subscription, text='📄 Моя подписка')
    dp.register_message_handler(help_command, text='🆘 Помощь')
    dp.register_message_handler(user_back, text='🔙 Назад')