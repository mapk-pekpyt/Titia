from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import os
from config import ADMIN_ID, ADMIN_CHAT_ID, DB_PATH, TARIFFS
from keyboards import user_main_menu, tariffs_menu, admin_main_menu
from datetime import datetime, timedelta

router = Router()

class TariffSelection(StatesGroup):
    choose_server = State()
    confirm_payment = State()

@router.message(CommandStart())
async def start_command(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("👨‍💻 Админ-панель", reply_markup=admin_main_menu())
    else:
        await message.answer(
            "🛡️ Добро пожаловать в VPN-сервис!\n"
            "Выберите действие:",
            reply_markup=user_main_menu()
        )

@router.message(F.text == "🛡️ Получить VPN")
async def get_vpn(message: Message):
    await message.answer("Выберите тариф:", reply_markup=tariffs_menu())

@router.message(F.text == "📊 Моя подписка")
async def my_subscription(message: Message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.tariff, s.end_date, se.host
        FROM subscriptions s
        JOIN servers se ON s.server_id = se.id
        WHERE s.user_id = ? AND s.payment_status = 'active'
    ''', (message.from_user.id,))
    sub = cursor.fetchone()
    conn.close()
    
    if sub:
        tariff, end_date, host = sub
        days_left = (datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S") - datetime.now()).days
        await message.answer(
            f"📊 Ваша подписка:\n\n"
            f"Тариф: {tariff}\n"
            f"Сервер: {host}\n"
            f"Дней осталось: {days_left}"
        )
    else:
        await message.answer("У вас нет активной подписки.")

@router.message(F.text == "🆘 Поддержка")
async def support(message: Message):
    await message.answer("По всем вопросам обращайтесь: @vpnhostik")

@router.callback_query(F.data.startswith("tariff_"))
async def process_tariff(callback: CallbackQuery, state: FSMContext):
    tariff = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    # Проверка пробного тарифа
    if tariff == "trial":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM subscriptions 
            WHERE user_id = ? AND tariff = 'trial'
        ''', (user_id,))
        if cursor.fetchone():
            await callback.answer("❌ Пробный тариф уже использован!", show_alert=True)
            conn.close()
            return
        conn.close()
    
    await state.update_data(tariff=tariff, user_id=user_id)
    
    # Для пробного тарифа — автоматическое добавление
    if tariff == "trial":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, server_name FROM servers 
            WHERE current_users < max_users 
            ORDER BY current_users ASC LIMIT 1
        ''')
        server = cursor.fetchone()
        
        if not server:
            await callback.answer("❌ Нет доступных серверов", show_alert=True)
            conn.close()
            return
        
        server_id, server_name = server
        end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('''
            INSERT INTO subscriptions 
            (user_id, server_id, tariff, payment_amount, payment_status, start_date, end_date)
            VALUES (?, ?, ?, 0, 'active', datetime('now'), ?)
        ''', (user_id, server_id, tariff, end_date))
        
        cursor.execute('''
            UPDATE servers SET current_users = current_users + 1 WHERE id = ?
        ''', (server_id,))
        
        conn.commit()
        conn.close()
        
        await callback.message.answer(
            f"✅ Пробный день активирован!\n"
            f"Сервер: {server_name}\n"
            f"Доступ до: {end_date}"
        )
        await state.clear()
        return
    
    # Для платных тарифов — выбор сервера
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, server_name FROM servers 
        WHERE current_users < max_users
    ''')
    servers = cursor.fetchall()
    conn.close()
    
    if not servers:
        await callback.answer("❌ Нет доступных серверов", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for server_id, server_name in servers:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=server_name, callback_data=f"server_{server_id}")
        ])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tariffs")])
    
    tariff_info = TARIFFS[tariff]
    await callback.message.edit_text(
        f"Тариф: {tariff_info['name']}\n"
        f"Цена: {tariff_info['price']}₽\n\n"
        f"Выберите сервер:",
        reply_markup=keyboard
    )
    await state.set_state(TariffSelection.choose_server)

@router.callback_query(F.data.startswith("server_"), TariffSelection.choose_server)
async def choose_server(callback: CallbackQuery, state: FSMContext):
    server_id = callback.data.split("_")[1]
    data = await state.get_data()
    tariff = data['tariff']
    tariff_info = TARIFFS[tariff]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT server_name FROM servers WHERE id = ?', (server_id,))
    server_name = cursor.fetchone()[0]
    conn.close()
    
    await state.update_data(server_id=server_id, server_name=server_name)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_payment")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"tariff_{tariff}")]
    ])
    
    await callback.message.edit_text(
        f"📋 Подтвердите заказ:\n\n"
        f"Тариф: {tariff_info['name']}\n"
        f"Сервер: {server_name}\n"
        f"Сумма: {tariff_info['price']}₽\n\n"
        f"После подтверждения вы получите реквизиты для оплаты.",
        reply_markup=keyboard
    )
    await state.set_state(TariffSelection.confirm_payment)

@router.callback_query(F.data == "confirm_payment", TariffSelection.confirm_payment)
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = data['user_id']
    tariff = data['tariff']
    server_id = data['server_id']
    server_name = data['server_name']
    tariff_info = TARIFFS[tariff]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Получаем реквизиты оплаты
    cursor.execute('SELECT card_number, phone_number FROM payment_details WHERE is_active = TRUE LIMIT 1')
    payment = cursor.fetchone()
    
    if payment:
        card, phone = payment
    else:
        card, phone = "2200 1234 5678 9010", "+79991234567"
    
    # Отправляем в админ-чат
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"admin_confirm_{user_id}_{server_id}_{tariff}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_{user_id}")]
    ])
    
    await callback.bot.send_message(
        ADMIN_CHAT_ID,
        f"💰 Новая оплата:\n\n"
        f"Пользователь: @{callback.from_user.username or 'без юзернейма'}\n"
        f"ID: {user_id}\n"
        f"Тариф: {tariff_info['name']}\n"
        f"Сервер: {server_name}\n"
        f"Сумма: {tariff_info['price']}₽\n\n"
        f"Ожидает подтверждения.",
        reply_markup=admin_keyboard
    )
    
    # Отправляем пользователю реквизиты
    await callback.message.edit_text(
        f"💳 Реквизиты для оплаты:\n\n"
        f"Карта: `{card}`\n"
        f"СБП: {phone}\n\n"
        f"Сумма: {tariff_info['price']}₽\n\n"
        f"После оплаты отправьте скриншот @vpnhostik\n"
        f"Ваш заказ передан администратору.",
        parse_mode="Markdown"
    )
    
    # Сохраняем подписку в ожидании
    cursor.execute('''
        INSERT INTO subscriptions 
        (user_id, server_id, tariff, payment_amount, payment_status)
        VALUES (?, ?, ?, ?, 'pending')
    ''', (user_id, server_id, tariff, tariff_info['price']))
    
    conn.commit()
    conn.close()
    await state.clear()

@router.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Выберите тариф:", reply_markup=tariffs_menu())
    await state.clear()