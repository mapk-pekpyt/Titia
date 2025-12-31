from aiogram import types, Dispatcher
from config import SUPPORT_USERNAME, TRIBUTE_PRODUCTS, ADMIN_ID
import sqlite3
import datetime

async def user_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    
    from keyboards import user_main_kb
    
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (id, username, full_name) 
        VALUES (?, ?, ?)
    ''', (message.from_user.id, message.from_user.username, message.from_user.full_name))
    conn.commit()
    conn.close()
    
    await message.answer(f"Привет! Выберите действие:", reply_markup=user_main_kb)

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
        cursor.execute('''
            INSERT INTO subscriptions (user_id, tariff, status, start_date, end_date)
            VALUES (?, 'trial', 'active', datetime('now'), ?)
        ''', (user_id, end_date))
        
        cursor.execute("UPDATE users SET trial_used=1 WHERE id=?", (user_id,))
        conn.commit()
        
        cursor.execute('''
            SELECT s.host, s.panel_port, s.panel_path 
            FROM servers s 
            WHERE s.status='active' 
            AND s.current_users < s.max_users 
            LIMIT 1
        ''')
        server = cursor.fetchone()
        
        if server:
            panel_url = f"http://{server[0]}:{server[1]}/{server[2]}"
            await message.answer(
                f"🎁 Пробный период активирован на 1 день!\n"
                f"🔗 Панель управления: {panel_url}\n"
                f"👤 Логин: admin\n"
                f"🔑 Пароль: admin12345\n\n"
                f"После входа создайте Reality-подключение:\n"
                f"• Порт: 443\n"
                f"• SNI: www.google.com\n"
                f"• SPX: yass",
                reply_markup=user_main_kb
            )
        else:
            await message.answer("😔 Нет доступных серверов.", reply_markup=user_main_kb)
    else:
        await message.answer("❌ Вы уже использовали пробный период.", reply_markup=user_main_kb)
    
    conn.close()

async def process_payment(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    from keyboards import user_main_kb
    
    tariff_text = message.text
    tariffs = {
        '📅 Неделя - 100₽': 'week',
        '📅 Месяц - 250₽': 'month',
        '📅 2 месяца - 450₽': '2months'
    }
    
    if tariff_text in tariffs:
        tariff = tariffs[tariff_text]
        product = TRIBUTE_PRODUCTS[tariff]
        
        payment_url = f"https://t.me/tribute/app?startapp={product['id']}"
        
        await message.answer(
            f"💳 Оплата тарифа: {tariff_text}\n"
            f"📅 Срок: {product['days']} дней\n\n"
            f"👉 [Оплатить через Tribute]({payment_url})\n\n"
            f"После оплаты подписка активируется автоматически.",
            parse_mode='Markdown',
            disable_web_page_preview=True,
            reply_markup=user_main_kb
        )

async def my_subscription(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    from keyboards import user_main_kb
    
    user_id = message.from_user.id
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.tariff, s.status, s.end_date, se.host
        FROM subscriptions s
        LEFT JOIN servers se ON s.server_id = se.id
        WHERE s.user_id=? AND s.status='active'
        ORDER BY s.end_date DESC LIMIT 1
    ''', (user_id,))
    
    sub = cursor.fetchone()
    conn.close()
    
    if sub:
        tariff, status, end_date, host = sub
        await message.answer(
            f"📄 Ваша подписка:\n"
            f"📅 Тариф: {tariff}\n"
            f"🔐 Статус: {status}\n"
            f"📆 Окончание: {end_date}\n"
            f"🖥 Сервер: {host or 'Не назначен'}",
            reply_markup=user_main_kb
        )
    else:
        await message.answer("❌ У вас нет активной подписки.", reply_markup=user_main_kb)

async def help_command(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    from keyboards import user_main_kb
    
    await message.answer(
        f"🆘 Помощь\n\n"
        f"1. Для получения VPN выберите тариф\n"
        f"2. Оплатите через Tribute\n"
        f"3. После оплаты получите доступ к панели\n"
        f"4. Настройте Reality-подключение\n\n"
        f"Техподдержка: {SUPPORT_USERNAME}",
        reply_markup=user_main_kb
    )

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