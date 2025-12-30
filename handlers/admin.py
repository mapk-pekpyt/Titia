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