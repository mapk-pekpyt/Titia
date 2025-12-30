from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import sqlite3
from config import ADMIN_ID, ADMIN_CHAT_ID, DB_PATH
from keyboards import admin_main_menu, servers_menu, payment_confirm_menu

router = Router()
router.message.filter(lambda msg: msg.from_user.id == ADMIN_ID)
router.callback_query.filter(lambda cb: cb.from_user.id == ADMIN_ID)

class PaymentDetails(StatesGroup):
    card_number = State()
    phone_number = State()
    bank_name = State()
    recipient_name = State()

@router.message(Command("admin"))
async def admin_panel(message: Message):
    await message.answer("👨‍💻 Админ-панель", reply_markup=admin_main_menu())

@router.message(F.text == "📊 Статистика")
async def statistics(message: Message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM servers")
    servers_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE payment_status='active'")
    active_subs = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(payment_amount) FROM subscriptions WHERE payment_status='active'")
    total_revenue = cursor.fetchone()[0] or 0
    
    conn.close()
    
    text = (
        f"📊 Статистика:\n\n"
        f"Серверов: {servers_count}\n"
        f"Пользователей: {users_count}\n"
        f"Активных подписок: {active_subs}\n"
        f"Общий доход: {total_revenue}₽"
    )
    await message.answer(text)

@router.message(F.text == "🖥️ Серверы")
async def servers_management(message: Message):
    await message.answer("Управление серверами:", reply_markup=servers_menu())

@router.message(F.text == "💰 Реквизиты оплаты")
async def payment_details_start(message: Message, state: FSMContext):
    await message.answer("Отправьте номер карты в формате:\n`2200 1234 5678 9010`")
    await state.set_state(PaymentDetails.card_number)

@router.message(PaymentDetails.card_number)
async def process_card_number(message: Message, state: FSMContext):
    await state.update_data(card_number=message.text)
    await message.answer("Введите номер телефона для СБП:")
    await state.set_state(PaymentDetails.phone_number)

@router.message(PaymentDetails.phone_number)
async def process_phone_number(message: Message, state: FSMContext):
    await state.update_data(phone_number=message.text)
    await message.answer("Введите название банка:")
    await state.set_state(PaymentDetails.bank_name)

@router.message(PaymentDetails.bank_name)
async def process_bank_name(message: Message, state: FSMContext):
    await state.update_data(bank_name=message.text)
    await message.answer("Введите имя и фамилию получателя:")
    await state.set_state(PaymentDetails.recipient_name)

@router.message(PaymentDetails.recipient_name)
async def process_recipient_name(message: Message, state: FSMContext):
    await state.update_data(recipient_name=message.text)
    data = await state.get_data()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE payment_details SET is_active = FALSE
    ''')
    cursor.execute('''
        INSERT INTO payment_details (card_number, phone_number, bank_name, recipient_name)
        VALUES (?, ?, ?, ?)
    ''', (data['card_number'], data['phone_number'], data['bank_name'], data['recipient_name']))
    conn.commit()
    conn.close()
    
    await message.answer("✅ Реквизиты сохранены!")
    await state.clear()

@router.message(F.text == "📝 Логи")
async def show_logs(message: Message):
    try:
        with open("bot.log", "r", encoding="utf-8") as f:
            logs = f.read()[-4000:]  # Последние 4000 символов
        if logs:
            await message.answer(f"📝 Последние логи:\n\n```\n{logs}\n```", parse_mode="Markdown")
        else:
            await message.answer("Логи пусты.")
    except FileNotFoundError:
        await message.answer("Файл логов не найден.")

@router.message(F.text == "👤 Пользователи")
async def show_users(message: Message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, full_name FROM users")
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        await message.answer("Пользователей пока нет.")
        return
    
    text = "👤 Пользователи:\n\n"
    for user in users:
        text += f"ID: {user[0]}\nИмя: {user[2]}\nЮзернейм: @{user[1] or 'нет'}\n\n"
    
    await message.answer(text[:4000])  # Ограничение Telegram

@router.message(F.text == "🆘 Поддержка")
async def support(message: Message):
    await message.answer("Поддержка: @vpnhostik")

@router.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(callback: CallbackQuery):
    sub_id = callback.data.split("_")[1]
    await callback.answer("Подписка активирована!")
    await callback.message.edit_reply_markup(reply_markup=None)
    # обнова

@router.callback_query(F.data.startswith("admin_confirm_"))
async def admin_confirm_payment(callback: CallbackQuery):
    data = callback.data.split("_")
    user_id = data[2]
    server_id = data[3]
    tariff = data[4]
    
    tariff_info = TARIFFS[tariff]
    days = tariff_info['days']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Активируем подписку
    end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        UPDATE subscriptions 
        SET payment_status = 'active', start_date = datetime('now'), end_date = ?
        WHERE user_id = ? AND server_id = ? AND tariff = ?
    ''', (end_date, user_id, server_id, tariff))
    
    # Увеличиваем счетчик пользователей
    cursor.execute('''
        UPDATE servers SET current_users = current_users + 1 WHERE id = ?
    ''', (server_id,))
    
    # Получаем данные сервера для уведомления пользователя
    cursor.execute('SELECT server_name FROM servers WHERE id = ?', (server_id,))
    server_name = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    # Уведомляем пользователя
    await callback.bot.send_message(
        user_id,
        f"✅ Ваша подписка активирована!\n\n"
        f"Тариф: {tariff_info['name']}\n"
        f"Сервер: {server_name}\n"
        f"Доступ до: {end_date}\n\n"
        f"Для получения конфигурации нажмите 'Моя подписка'."
    )
    
    await callback.message.edit_text(
        f"✅ Оплата подтверждена!\n"
        f"Пользователь: {user_id}\n"
        f"Тариф: {tariff}\n"
        f"Сервер: {server_name}"
    )

@router.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_payment(callback: CallbackQuery):
    user_id = callback.data.split("_")[2]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions WHERE user_id = ? AND payment_status = 'pending'", (user_id,))
    conn.commit()
    conn.close()
    
    await callback.bot.send_message(user_id, "❌ Ваш заказ был отклонен администратором.")
    await callback.message.edit_text(f"❌ Заказ пользователя {user_id} отклонен.")