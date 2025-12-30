from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from keyboards import auth_type_menu, servers_menu
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

def back_button():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )

@router.callback_query(F.data == "add_server")
async def add_server_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Выберите тип аутентификации:", reply_markup=auth_type_menu())
    await state.set_state(ServerAdd.auth_type)

@router.callback_query(F.data.in_(["auth_key", "auth_password"]))
async def process_auth_type(callback: CallbackQuery, state: FSMContext):
    auth_type = "key" if callback.data == "auth_key" else "password"
    await state.update_data(auth_type=auth_type)
    await callback.message.answer("Введите host (IP адрес сервера):", reply_markup=back_button())
    await state.set_state(ServerAdd.host)

@router.message(ServerAdd.host)
async def process_host(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Выберите тип аутентификации:", reply_markup=auth_type_menu())
        await state.set_state(ServerAdd.auth_type)
        return
    
    await state.update_data(host=message.text)
    
    # Кнопки для порта
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="22 (стандартный)")],
            [KeyboardButton(text="Ввести другой порт")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )
    await message.answer("Выберите порт SSH:", reply_markup=markup)
    await state.set_state(ServerAdd.port)

@router.message(ServerAdd.port)
async def process_port(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Введите host (IP адрес сервера):", reply_markup=back_button())
        await state.set_state(ServerAdd.host)
        return
    
    port = 22 if message.text == "22 (стандартный)" else None
    if port is None:
        await message.answer("Введите номер порта:", reply_markup=back_button())
        return
    
    await state.update_data(port=port)
    await message.answer("Введите имя пользователя SSH:", reply_markup=back_button())
    await state.set_state(ServerAdd.username)

@router.message(F.text.regexp(r'^\d+$'), ServerAdd.port)
async def process_custom_port(message: Message, state: FSMContext):
    await state.update_data(port=int(message.text))
    await message.answer("Введите имя пользователя SSH:", reply_markup=back_button())
    await state.set_state(ServerAdd.username)

@router.message(ServerAdd.username)
async def process_username(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Выберите порт SSH:", reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="22 (стандартный)")],
                [KeyboardButton(text="Ввести другой порт")],
                [KeyboardButton(text="⬅️ Назад")]
            ],
            resize_keyboard=True
        ))
        await state.set_state(ServerAdd.port)
        return
    
    await state.update_data(username=message.text)
    data = await state.get_data()
    
    if data.get("auth_type") == "password":
        await message.answer("Введите пароль SSH:", reply_markup=back_button())
        await state.set_state(ServerAdd.password)
    else:
        await message.answer("Отправьте текст SSH ключа (в формате PEM):", reply_markup=back_button())
        await state.set_state(ServerAdd.ssh_key)

@router.message(ServerAdd.password)
async def process_password(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Введите имя пользователя SSH:", reply_markup=back_button())
        await state.set_state(ServerAdd.username)
        return
    
    await state.update_data(password=message.text)
    await finish_server_add(message, state)

@router.message(ServerAdd.ssh_key)
async def process_ssh_key(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Введите имя пользователя SSH:", reply_markup=back_button())
        await state.set_state(ServerAdd.username)
        return
    
    await state.update_data(ssh_key=message.text)
    await finish_server_add(message, state)

async def finish_server_add(message: Message, state: FSMContext):
    data = await state.get_data()
    # Сохранение в БД
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO servers (host, port, username, password, ssh_key, auth_type)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (data['host'], data.get('port', 22), data['username'], 
          data.get('password'), data.get('ssh_key'), data['auth_type']))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Сервер {data['host']} добавлен!", reply_markup=ReplyKeyboardRemove())
    await state.clear()

@router.callback_query(F.data == "list_servers")
async def list_servers(callback: CallbackQuery):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, host, status FROM servers")
    servers = cursor.fetchall()
    conn.close()
    
    if not servers:
        await callback.message.answer("Серверов пока нет.")
        return
    
    text = "📋 Список серверов:\n\n"
    for server in servers:
        text += f"ID: {server[0]}\nХост: {server[1]}\nСтатус: {server[2]}\n\n"
    
    await callback.message.answer(text)

@router.callback_query(F.data == "manage_servers")
async def manage_servers(callback: CallbackQuery):
    await callback.message.answer("Функционал управления серверами в разработке.")