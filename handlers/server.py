from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from keyboards import auth_type_menu, servers_menu
import sqlite3
import asyncio
from utils.ssh_client import SSHClient
from utils.vpn_installer import VPNInstaller
from config import DB_PATH
import os
import tempfile

router = Router()

class ServerAdd(StatesGroup):
    server_name = State()
    auth_type = State()
    host = State()
    port = State()
    username = State()
    password = State()
    ssh_key = State()

class ServerEdit(StatesGroup):
    edit_name = State()
    edit_max_users = State()

def back_button():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )

@router.callback_query(F.data == "add_server")
async def add_server_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите имя для сервера (например: Германия #1):", reply_markup=back_button())
    await state.set_state(ServerAdd.server_name)

@router.message(ServerAdd.server_name)
async def process_server_name(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Управление серверами:", reply_markup=servers_menu())
        await state.clear()
        return
    
    await state.update_data(server_name=message.text)
    await message.answer("Выберите тип аутентификации:", reply_markup=auth_type_menu())
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
        await message.answer("Введите имя для сервера:", reply_markup=back_button())
        await state.set_state(ServerAdd.server_name)
        return
    
    await state.update_data(host=message.text)
    
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
        await message.answer("Отправьте файл с SSH ключом (формат PEM):", reply_markup=back_button())
        await state.set_state(ServerAdd.ssh_key)

@router.message(ServerAdd.password)
async def process_password(message: Message, state: FSMContext, bot):
    if message.text == "⬅️ Назад":
        await message.answer("Введите имя пользователя SSH:", reply_markup=back_button())
        await state.set_state(ServerAdd.username)
        return
    
    await state.update_data(password=message.text)
    await finish_server_add(message, state, bot)

@router.message(F.document, ServerAdd.ssh_key)
async def process_ssh_key_file(message: Message, state: FSMContext, bot):
    if message.document:
        file = await bot.download(message.document)
        key_content = file.read().decode('utf-8')
        await state.update_data(ssh_key=key_content)
        await finish_server_add(message, state, bot)
    else:
        await message.answer("Пожалуйста, отправьте файл с ключом.")

async def finish_server_add(message: Message, state: FSMContext, bot):
    """Сохраняем сервер и запускаем фоновую установку"""
    data = await state.get_data()
    server_name = data.get('server_name', 'Без имени')
    
    # Сохраняем сервер в БД как "устанавливается"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO servers 
        (server_name, host, port, username, password, ssh_key, auth_type, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'installing')
    ''', (
        server_name, 
        data['host'], 
        data.get('port', 22), 
        data['username'],
        data.get('password'), 
        data.get('ssh_key'), 
        data['auth_type']
    ))
    server_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Запускаем установку в фоне
    asyncio.create_task(
        install_vpn_background(server_id, data, message.chat.id, bot, server_name)
    )
    
    await message.answer(
        f"⚙️ Установка сервера '{server_name}' началась в фоне.\n"
        f"Я пришлю уведомление когда всё будет готово.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

async def install_vpn_background(server_id, data, chat_id, bot, server_name):
    """Фоновая установка VPN"""
    ssh = SSHClient(
        data['host'],
        data.get('port', 22),
        data['username'],
        data.get('password'),
        data.get('ssh_key')
    )
    
    connected = await ssh.connect()
    if not connected:
        await bot.send_message(chat_id, f"❌ Не удалось подключиться к серверу '{server_name}'")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE servers SET status='failed' WHERE id=?", (server_id,))
        conn.commit()
        conn.close()
        return
    
    installer = VPNInstaller(ssh, bot, chat_id)
    result = await installer.install_xui()
    
    ssh.close()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if result['success']:
        cursor.execute('''
            UPDATE servers 
            SET panel_url=?, panel_username=?, panel_password=?, status='active'
            WHERE id=?
        ''', (result['panel_url'], result['username'], result['password'], server_id))
        
        await bot.send_message(
            chat_id,
            f"✅ Сервер '{server_name}' готов!\n\n"
            f"Панель: {result['panel_url']}\n"
            f"Логин: {result['username']}\n"
            f"Пароль: {result['password']}\n\n"
            f"IP: {data['host']}"
        )
    else:
        cursor.execute("UPDATE servers SET status='failed' WHERE id=?", (server_id,))
        await bot.send_message(
            chat_id, 
            f"❌ Ошибка установки сервера '{server_name}':\n{result.get('error', 'Неизвестная ошибка')}"
        )
    
    conn.commit()
    conn.close()

@router.callback_query(F.data == "list_servers")
async def list_servers(callback: CallbackQuery):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, server_name, host, current_users, max_users, status FROM servers")
    servers = cursor.fetchall()
    conn.close()
    
    if not servers:
        await callback.message.answer("Серверов пока нет.")
        return
    
    text = "📋 Список серверов:\n\n"
    for server in servers:
        text += (
            f"ID: {server[0]}\n"
            f"Имя: {server[1]}\n"
            f"Хост: {server[2]}\n"
            f"Пользователи: {server[3]}/{server[4]}\n"
            f"Статус: {server[5]}\n\n"
        )
    
    await callback.message.answer(text)

@router.callback_query(F.data.startswith("manage_"))
async def manage_server(callback: CallbackQuery):
    server_id = callback.data.split("_")[1]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Сменить имя", callback_data=f"edit_name_{server_id}")],
        [InlineKeyboardButton(text="👥 Изменить макс. пользователей", callback_data=f"edit_max_{server_id}")],
        [InlineKeyboardButton(text="📡 Пинг сервера", callback_data=f"ping_{server_id}")],
        [InlineKeyboardButton(text="🔗 Получить ссылку на панель", callback_data=f"panel_{server_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="list_servers")]
    ])
    
    await callback.message.answer("Управление сервером:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("edit_name_"))
async def edit_name_start(callback: CallbackQuery, state: FSMContext):
    server_id = callback.data.split("_")[2]
    await state.update_data(server_id=server_id)
    await callback.message.answer("Введите новое имя для сервера:", reply_markup=back_button())
    await state.set_state(ServerEdit.edit_name)

@router.message(ServerEdit.edit_name)
async def process_edit_name(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Управление сервером отменено.")
        await state.clear()
        return
    
    data = await state.get_data()
    server_id = data['server_id']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE servers SET server_name = ? WHERE id = ?", (message.text, server_id))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Имя сервера изменено на: {message.text}")
    await state.clear()

@router.callback_query(F.data.startswith("edit_max_"))
async def edit_max_start(callback: CallbackQuery, state: FSMContext):
    server_id = callback.data.split("_")[2]
    await state.update_data(server_id=server_id)
    await callback.message.answer("Введите новое максимальное количество пользователей:", reply_markup=back_button())
    await state.set_state(ServerEdit.edit_max_users)

@router.message(ServerEdit.edit_max_users)
async def process_edit_max_users(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Управление сервером отменено.")
        await state.clear()
        return
    
    if not message.text.isdigit():
        await message.answer("Введите число!")
        return
    
    data = await state.get_data()
    server_id = data['server_id']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE servers SET max_users = ? WHERE id = ?", (int(message.text), server_id))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Макс. пользователей изменено на: {message.text}")
    await state.clear()

@router.callback_query(F.data.startswith("ping_"))
async def ping_server(callback: CallbackQuery):
    server_id = callback.data.split("_")[1]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT host, port, username, password, ssh_key FROM servers WHERE id = ?", (server_id,))
    server = cursor.fetchone()
    conn.close()
    
    if not server:
        await callback.answer("Сервер не найден!")
        return
    
    host, port, username, password, ssh_key = server
    
    await callback.message.answer("⏳ Проверяю подключение...")
    
    ssh = SSHClient(host, port, username, password, ssh_key)
    connected = await ssh.connect()
    ssh.close()
    
    if connected:
        await callback.message.answer("✅ Сервер доступен!")
    else:
        await callback.message.answer("❌ Сервер недоступен!")

@router.callback_query(F.data.startswith("panel_"))
async def get_panel_link(callback: CallbackQuery):
    server_id = callback.data.split("_")[1]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT panel_url, panel_username, panel_password FROM servers WHERE id = ?", (server_id,))
    panel = cursor.fetchone()
    conn.close()
    
    if panel and panel[0]:
        await callback.message.answer(
            f"🔗 Панель управления:\n"
            f"URL: {panel[0]}\n"
            f"Логин: {panel[1]}\n"
            f"Пароль: {panel[2]}"
        )
    else:
        await callback.message.answer("❌ Данные панели не найдены.")