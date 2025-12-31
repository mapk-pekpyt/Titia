from aiogram import types, Dispatcher
from config import SUPPORT_USERNAME, TRIBUTE_PRODUCTS, ADMIN_ID
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
        
        cursor.execute('SELECT host, panel_port, panel_path FROM servers WHERE status="active" AND current_users < max_users LIMIT 1')
        server = cursor.fetchone()
        
        if server:
            panel_url = f"http://{server[0]}:{server[1]}/{server[2]}"
            await message.answer(f"🎁 Пробный период активирован на 1 день!\n🔗 Панель: {panel_url}\n👤 Логин: admin\n🔑 Пароль: admin12345\n\nПосле входа создайте Reality-подключение:\n• Порт: 443\n• SNI: www.google.com\n• SPX: yass", reply_markup=user_main_kb)
        else:
            await message.answer("😔 Нет доступных серверов.", reply_markup=user_main_kb)
    else:
        await message.answer("❌ Вы уже использовали пробный период.", reply_markup=user_main_kb)
    
    conn.close()

async def process_payment(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    from keyboards import user_main_kb
    
    tariffs = {
        '📅 Неделя - 100₽': ('week', 'poWz'),
        '📅 Месяц - 250₽': ('month', 'poX4'),
        '📅 2 месяца - 450₽': ('2months', 'poX5')
    }
    
    if message.text in tariffs:
        tariff, product_id = tariffs[message.text]
        product = TRIBUTE_PRODUCTS[tariff]
        payment_url = f"https://t.me/tribute/app?startapp={product_id}"
        
        await message.answer(f"💳 Оплата тарифа: {message.text}\n📅 Срок: {product['days']} дней\n\n👉 [Оплатить через Tribute]({payment_url})\n\nПосле оплаты подписка активируется автоматически.",
                            parse_mode='Markdown', disable_web_page_preview=True, reply_markup=user_main_kb)

async def my_subscription(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    from keyboards import user_main_kb
    
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT tariff, status, end_date FROM subscriptions WHERE user_id=? AND status="active" ORDER BY end_date DESC LIMIT 1',
                  (message.from_user.id,))
    sub = cursor.fetchone()
    conn.close()
    
    if sub:
        await message.answer(f"📄 Ваша подписка:\n📅 Тариф: {sub[0]}\n🔐 Статус: {sub[1]}\n📆 Окончание: {sub[2]}", reply_markup=user_main_kb)
    else:
        await message.answer("❌ У вас нет активной подписки.", reply_markup=user_main_kb)

async def help_command(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    from keyboards import user_main_kb
    await message.answer(f"🆘 Помощь\n\n1. Выберите тариф\n2. Оплатите через Tribute\n3. Получите доступ к панели\n4. Настройте Reality-подключение\n\nТехподдержка: {SUPPORT_USERNAME}", reply_markup=user_main_kb)

async def user_back(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    from keyboards import user_main_kb
    await message.answer("Главное меню:", reply_markup=user_main_kb)

def register_user_handlers(dp: Dispatcher):
    dp.register_message_handler(get_vpn, text='🔑 Получить VPN')
    dp.register_message_handler(process_trial, text='🎁 Пробник (1 день)')
    dp.register_message_handler(process_payment, text=['📅 Неделя - 100₽', '📅 Месяц - 250₽', '📅 2 месяца - 450₽'])
    dp.register_message_handler(my_subscription, text='📄 Моя подписка')
    dp.register_message_handler(help_command, text='🆘 Помощь')
    dp.register_message_handler(user_back, text='🔙 Назад')