from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import auth_type_menu
import sqlite3
from config import DB_PATH

router = Router()

class ServerAdd(StatesGroup):
    auth_type = State()
    host = State()
    port = State()
    username = State()
    password = State()
    ssh_key = State()

@router.callback_query(F.data == "add_server")
async def add_server_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Выберите тип аутентификации:", reply_markup=auth_type_menu())
    await state.set_state(ServerAdd.auth_type)

@router.callback_query(F.data.in_(["auth_key", "auth_password"]))
async def process_auth_type(callback: CallbackQuery, state: FSMContext):
    auth_type = "key" if callback.data == "auth_key" else "password"
    await state.update_data(auth_type=auth_type)
    await callback.message.answer("Введите host (IP адрес сервера):")
    await state.set_state(ServerAdd.host)

@router.message(ServerAdd.host)
async def process_host(message: Message, state: FSMContext):
    await state.update_data(host=message.text)
    await message.answer("Введите порт SSH (по умолчанию 22):")
    await state.set_state(ServerAdd.port)

# ... остальные шаги добавления сервера