from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
import sqlite3
from config import ADMIN_ID, ADMIN_CHAT_ID, DB_PATH
from keyboards import admin_main_menu, servers_menu, payment_confirm_menu

router = Router()

# Проверка админа
def is_admin(user_id):
    return user_id == ADMIN_ID

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён")
        return
    await message.answer("👨‍💻 Админ-панель", reply_markup=admin_main_menu())

@router.message(F.text == "🖥️ Серверы")
async def servers_management(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Управление серверами:", reply_markup=servers_menu())

@router.message(F.text == "💰 Реквизиты оплаты")
async def payment_details(message: Message):
    if not is_admin(message.from_user.id):
        return
    # Добавление реквизитов (упрощённая версия)
    await message.answer("Отправьте номер карты в формате:\n`2200 1234 5678 9010`")

@router.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    sub_id = callback.data.split("_")[1]
    # Логика активации подписки
    await callback.answer("Подписка активирована!")
    await callback.message.edit_reply_markup(reply_markup=None)