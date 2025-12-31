from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_ID, BOT_TOKEN, ADMIN_CHAT_ID
import sqlite3
import re
import os
import tempfile
from utils.ssh_client import SSHClient
from utils.vpn_installer import install_xui, get_server_info

# Состояния для добавления сервера
class AddServer(StatesGroup):
    host = State()
    ssh_port = State()
    ssh_username = State()
    ssh_method = State()
    ssh_password = State()
    ssh_key_file = State()

# 1. Кнопка "🖥 Сервера"
async def admin_servers(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    from keyboards import admin_servers_kb
    await message.answer("🖥 Управление серверами", reply_markup=admin_servers_kb)

# 2. Кнопка "➕ Добавить сервер" (начало)
async def add_server_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await AddServer.host.set()
    await message.answer("Введите IP адрес сервера:", reply_markup=back_kb())

# Обработка хоста
async def process_host(message: types.Message, state: FSMContext):
    if message.text == '🔙 Назад':
        await state.finish()
        from keyboards import admin_servers_kb
        await message.answer("Отменено", reply_markup=admin_servers_kb)
        return
    
    ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
    if not re.match(ip_pattern, message.text):
        await message.answer("❌ Неверный IP. Введите корректный IP:", reply_markup=back_kb())
        return
    
    async with state.proxy() as data:
        data['host'] = message.text
    
    port_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    port_kb.add(KeyboardButton('Стандарт 22'), KeyboardButton('Выбрать порт'), KeyboardButton('🔙 Назад'))
    
    await AddServer.next()
    await message.answer("Выберите SSH порт:", reply_markup=port_kb)

# Обработка порта
async def process_ssh_port(message: types.Message, state: FSMContext):
    if message.text == '🔙 Назад':
        await AddServer.host.set()
        await message.answer("Введите IP адрес сервера:", reply_markup=back_kb())
        return
    
    async with state.proxy() as data:
        if message.text == 'Стандарт 22':
            data['ssh_port'] = 22
            await AddServer.next()
            await message.answer("Введите имя пользователя SSH (обычно root или ubuntu):", reply_markup=back_kb())
        elif message.text == 'Выбрать порт':
            await message.answer("Введите номер порта SSH:", reply_markup=back_kb())
        else:
            try:
                port = int(message.text)
                if port < 1 or port > 65535:
                    await message.answer("❌ Порт должен быть от 1 до 65535:", reply_markup=back_kb())
                    return
                data['ssh_port'] = port
                await AddServer.next()
                await message.answer("Введите имя пользователя SSH:", reply_markup=back_kb())
            except:
                await message.answer("❌ Неверный формат порта:", reply_markup=back_kb())

# Обработка имени пользователя
async def process_ssh_username(message: types.Message, state: FSMContext):
    if message.text == '🔙 Назад':
        port_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        port_kb.add(KeyboardButton('Стандарт 22'), KeyboardButton('Выбрать порт'), KeyboardButton('🔙 Назад'))
        await AddServer.ssh_port.set()
        await message.answer("Выберите SSH порт:", reply_markup=port_kb)
        return
    
    async with state.proxy() as data:
        data['ssh_username'] = message.text
    
    method_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    method_kb.add(KeyboardButton('Пароль'), KeyboardButton('SSH ключ (файл)'), KeyboardButton('🔙 Назад'))
    
    await AddServer.next()
    await message.answer("Выберите метод аутентификации:", reply_markup=method_kb)

# Обработка метода аутентификации
async def process_ssh_method(message: types.Message, state: FSMContext):
    if message.text == '🔙 Назад':
        await AddServer.ssh_username.set()
        await message.answer("Введите имя пользователя SSH:", reply_markup=back_kb())
        return
    
    async with state.proxy() as data:
        data['ssh_method'] = message.text
    
    if message.text == 'Пароль':
        await AddServer.next()
        await message.answer("Введите пароль SSH:", reply_markup=back_kb())
    elif message.text == 'SSH ключ (файл)':
        await AddServer.ssh_key_file.set()
        await message.answer("Отправьте файл SSH ключа (.pem или .key):", reply_markup=back_kb())

# Обработка пароля
async def process_ssh_password(message: types.Message, state: FSMContext):
    if message.text == '🔙 Назад':
        method_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        method_kb.add(KeyboardButton('Пароль'), KeyboardButton('SSH ключ (файл)'), KeyboardButton('🔙 Назад'))
        await AddServer.ssh_method.set()
        await message.answer("Выберите метод аутентификации:", reply_markup=method_kb)
        return
    
    async with state.proxy() as data:
        data['ssh_password'] = message.text
    
    await connect_and_install(message, state)

# Обработка SSH ключа (файл)
async def process_ssh_key_file(message: types.Message, state: FSMContext):
    if message.text == '🔙 Назад':
        method_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        method_kb.add(KeyboardButton('Пароль'), KeyboardButton('SSH ключ (файл)'), KeyboardButton('🔙 Назад'))
        await AddServer.ssh_method.set()
        await message.answer("Выберите метод аутентификации:", reply_markup=method_kb)
        return
    
    if not message.document:
        await message.answer("❌ Отправьте файл SSH ключа:", reply_markup=back_kb())
        return
    
    # Скачиваем файл
    file = await message.document.get_file()
    
    # Создаем временный файл
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem') as tmp:
        file_content = await file.download_as_bytearray()
        decoded_content = file_content.decode('utf-8', errors='ignore')
        tmp.write(decoded_content)
        tmp_path = tmp.name
    
    # Читаем содержимое
    with open(tmp_path, 'r') as f:
        key_content = f.read()
    
    # Удаляем временный файл
    import os
    os.unlink(tmp_path)
    
    async with state.proxy() as data:
        data['ssh_key'] = key_content
    
    await connect_and_install(message, state)
# Подключение и установка
async def connect_and_install(message: types.Message, state: FSMContext):
    from keyboards import admin_main_kb
    bot = message.bot
    
    async with state.proxy() as data:
        host = data['host']
        port = data.get('ssh_port', 22)
        username = data['ssh_username']
        password = data.get('ssh_password')
        ssh_key = data.get('ssh_key')
    
    # 1. Пытаемся подключиться
    await message.answer(f"🔗 Подключаюсь к {host}:{port}...")
    
    try:
        ssh_client = SSHClient(host, port, username, password, ssh_key)
        
        # 2. Получаем характеристики сервера
        await message.answer("📊 Получаю характеристики сервера...")
        server_info = await get_server_info(ssh_client)
        
        if not server_info['success']:
            await message.answer(f"❌ Не удалось получить характеристики: {server_info.get('error')}", reply_markup=admin_main_kb)
            await state.finish()
            return
        
        # Показываем характеристики
        info_msg = (
            f"✅ Подключение успешно!\n\n"
            f"📊 Характеристики сервера:\n"
            f"• 🖥 ОС: {server_info['os']}\n"
            f"• ⚡ CPU: {server_info['cpu']}\n"
            f"• 💾 RAM: {server_info['ram']}\n"
            f"• 💿 Диск: {server_info['disk']}\n"
            f"• ⏱ Uptime: {server_info['uptime']}\n\n"
            f"🚀 Начинаю установку VPN..."
        )
        await message.answer(info_msg)
        
        # 3. Устанавливаем VPN
        success, panel_url, logs = await install_xui(ssh_client, bot)
        
        if success:
            # Сохраняем сервер в БД
            conn = sqlite3.connect('vpn_bot.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO servers (host, ssh_port, ssh_username, ssh_password, ssh_key, 
                                   panel_path, panel_password, ram_info, cpu_info, disk_info)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (host, port, username, password, ssh_key, 
                  panel_url.split('/')[-1], 'admin12345',
                  server_info['ram'], server_info['cpu'], server_info['disk']))
            conn.commit()
            conn.close()
            
            # Отправляем результат
            result_msg = (
                f"✅ VPN успешно установлен!\n\n"
                f"🔗 Панель управления: {panel_url}\n"
                f"👤 Логин: admin\n"
                f"🔑 Пароль: admin12345\n\n"
                f"🔧 Порты открыты: 54321, 443, 2096"
            )
            await message.answer(result_msg, reply_markup=admin_main_kb)
            
            # Логи в админ чат
            await bot.send_message(ADMIN_CHAT_ID, f"✅ Новый сервер добавлен: {host}\n{panel_url}")
            
        else:
            await message.answer(f"❌ Ошибка установки:\n{logs[-500:]}", reply_markup=admin_main_kb)
    
    except Exception as e:
        await message.answer(f"❌ Ошибка подключения: {str(e)}", reply_markup=admin_main_kb)
    
    await state.finish()

# 3. Кнопка "📋 Список серверов"
async def list_servers(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, host, status, current_users, max_users, ram_info, cpu_info FROM servers")
    servers = cursor.fetchall()
    conn.close()
    
    if servers:
        text = "📋 Список серверов:\n\n"
        for server in servers:
            text += f"🖥 ID: {server[0]}\n"
            text += f"🌐 IP: {server[1]}\n"
            text += f"👥 Пользователи: {server[3]}/{server[4]}\n"
            text += f"💾 RAM: {server[5] or '—'}\n"
            text += f"⚡ CPU: {server[6] or '—'}\n"
            text += f"🔧 Статус: {server[2]}\n"
            text += "─" * 20 + "\n"
        
        # Добавляем кнопку управления
        kb = InlineKeyboardMarkup()
        for server in servers[:5]:  # Первые 5 серверов
            kb.add(InlineKeyboardButton(f"⚙️ Управлять {server[1]}", callback_data=f"manage_{server[0]}"))
        
        from keyboards import admin_servers_kb
        await message.answer(text, reply_markup=admin_servers_kb)
    else:
        from keyboards import admin_servers_kb
        await message.answer("❌ Серверов нет", reply_markup=admin_servers_kb)

# 4. Кнопка "⚙️ Управление серверами" - показывает inline кнопки
async def manage_servers(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, host FROM servers WHERE status='active'")
    servers = cursor.fetchall()
    conn.close()
    
    if not servers:
        from keyboards import admin_servers_kb
        await message.answer("❌ Нет активных серверов", reply_markup=admin_servers_kb)
        return
    
    kb = InlineKeyboardMarkup(row_width=1)
    for server in servers:
        kb.add(InlineKeyboardButton(f"🖥 {server[1]}", callback_data=f"server_{server[0]}"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_servers"))
    
    await message.answer("Выберите сервер для управления:", reply_markup=kb)

# Inline обработчик выбора сервера
async def process_server_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    data = callback.data
    
    if data == "back_to_servers":
        from keyboards import admin_servers_kb
        await callback.message.edit_text("🖥 Управление серверами")
        await callback.message.edit_reply_markup(admin_servers_kb)
        return
    
    if data.startswith("server_"):
        server_id = data.split("_")[1]
        
        conn = sqlite3.connect('vpn_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT host, panel_path FROM servers WHERE id=?", (server_id,))
        server = cursor.fetchone()
        conn.close()
        
        if server:
            host, panel_path = server
            panel_url = f"http://{host}:54321/{panel_path}"
            
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(
                InlineKeyboardButton("🔄 Переустановить VPN", callback_data=f"reinstall_{server_id}"),
                InlineKeyboardButton("📡 Пинг сервера", callback_data=f"ping_{server_id}"),
                InlineKeyboardButton("👥 Изменить лимит", callback_data=f"limit_{server_id}"),
                InlineKeyboardButton("🚫 Выключить", callback_data=f"disable_{server_id}"),
                InlineKeyboardButton("🔙 Назад", callback_data="back_to_list")
            )
            
            await callback.message.edit_text(
                f"⚙️ Управление сервером:\n\n"
                f"🌐 IP: {host}\n"
                f"🔗 Панель: {panel_url}\n\n"
                f"Выберите действие:",
                reply_markup=kb
            )
    
    elif data.startswith("reinstall_"):
        server_id = data.split("_")[1]
        await callback.answer("Функция переустановки в разработке", show_alert=True)

# 5. Кнопка "👥 Пользователи"
async def admin_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    from keyboards import admin_users_kb
    await message.answer("👥 Управление пользователями", reply_markup=admin_users_kb)

# 6. Кнопка "🎁 Выдать VPN"
async def give_vpn(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите ID пользователя для выдачи VPN:", reply_markup=back_kb())

# 7. Кнопка "🚫 Отключить VPN"
async def disable_vpn(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите ID пользователя для отключения VPN:", reply_markup=back_kb())

# 8. Кнопка "💰 Метод оплаты"
async def payment_method(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url=https://ваш-сервер.ру/tribute_webhook"
    
    instruction = (
        f"🔗 Вебхук для Tribute:\n\n"
        f"1. URL для вебхука:\n"
        f"`{webhook_url}`\n\n"
        f"2. API ключ:\n"
        f"`42d4d099-20fd-4f55-a196-d77d9fed`\n\n"
        f"3. Инструкция:\n"
        f"• Добавьте URL в настройки Tribute\n"
        f"• Укажите API ключ\n"
        f"• Бот будет получать уведомления об оплатах"
    )
    
    from keyboards import admin_main_kb
    await message.answer(instruction, parse_mode='Markdown', reply_markup=admin_main_kb)

# 9. Кнопка "📊 Статистика"
async def admin_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('vpn_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM servers WHERE status='active'")
    servers = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE status='active'")
    active_subs = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(amount) FROM payments WHERE status='success'")
    income = cursor.fetchone()[0] or 0
    
    stats = (
        f"📊 Статистика:\n"
        f"🖥 Серверов: {servers}\n"
        f"👥 Пользователей: {users}\n"
        f"📅 Активных подписок: {active_subs}\n"
        f"💰 Общий доход: {income}₽"
    )
    conn.close()
    
    from keyboards import admin_main_kb
    await message.answer(stats, reply_markup=admin_main_kb)

# 10. Кнопка "🔙 Назад"
async def admin_back(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    from keyboards import admin_main_kb
    await message.answer("👑 Админ-панель", reply_markup=admin_main_kb)

# Вспомогательная функция для кнопки "Назад"
def back_kb():
    return ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton('🔙 Назад'))

# Регистрируем ВСЕ обработчики
def register_admin_handlers(dp: Dispatcher):
    # Основные кнопки
    dp.register_message_handler(admin_servers, text='🖥 Сервера', user_id=ADMIN_ID)
    dp.register_message_handler(add_server_start, text='➕ Добавить сервер', user_id=ADMIN_ID)
    dp.register_message_handler(list_servers, text='📋 Список серверов', user_id=ADMIN_ID)
    dp.register_message_handler(admin_users, text='👥 Пользователи', user_id=ADMIN_ID)
    dp.register_message_handler(give_vpn, text='🎁 Выдать VPN', user_id=ADMIN_ID)
    dp.register_message_handler(disable_vpn, text='🚫 Отключить VPN', user_id=ADMIN_ID)
    dp.register_message_handler(payment_method, text='💰 Метод оплаты', user_id=ADMIN_ID)
    dp.register_message_handler(admin_stats, text='📊 Статистика', user_id=ADMIN_ID)
    dp.register_message_handler(admin_back, text='🔙 Назад', user_id=ADMIN_ID)
    
    # Обработчики состояний
    dp.register_message_handler(process_host, state=AddServer.host)
    dp.register_message_handler(process_ssh_port, state=AddServer.ssh_port)
    dp.register_message_handler(process_ssh_username, state=AddServer.ssh_username)
    dp.register_message_handler(process_ssh_method, state=AddServer.ssh_method)
    dp.register_message_handler(process_ssh_password, state=AddServer.ssh_password)
    dp.register_message_handler(process_ssh_key_file, content_types=['document', 'text'], state=AddServer.ssh_key_file)
    
    # Inline обработчики
    dp.register_callback_query_handler(process_server_callback, lambda c: c.data.startswith(('server_', 'back_', 'reinstall_', 'ping_', 'limit_', 'disable_')), user_id=ADMIN_ID)