from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from config import ADMIN_ID, BOT_TOKEN, ADMIN_CHAT_ID
import sqlite3
import re
from utils.ssh_client import SSHClient
from utils.vpn_installer import install_xui

# Состояния для добавления сервера
class AddServer(StatesGroup):
    host = State()
    ssh_port = State()
    ssh_username = State()
    ssh_method = State()
    ssh_password = State()
    ssh_key = State()

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
    await message.answer("Введите IP адрес сервера:", reply_markup=types.ReplyKeyboardRemove())

# Обработка хоста
async def process_host(message: types.Message, state: FSMContext):
    if message.text == '🔙 Назад':
        await state.finish()
        from keyboards import admin_servers_kb
        await message.answer("Отменено", reply_markup=admin_servers_kb)
        return
    
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', message.text):
        await message.answer("❌ Неверный IP адрес. Введите корректный IP:")
        return
    
    async with state.proxy() as data:
        data['host'] = message.text
    
    # Создаем клавиатуру выбора порта
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    port_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    port_kb.add(KeyboardButton('Стандарт 22'), KeyboardButton('Выбрать порт'), KeyboardButton('🔙 Назад'))
    
    await AddServer.next()
    await message.answer("Выберите SSH порт:", reply_markup=port_kb)

# Обработка порта
async def process_ssh_port(message: types.Message, state: FSMContext):
    if message.text == '🔙 Назад':
        await AddServer.host.set()
        await message.answer("Введите IP адрес сервера:")
        return
    
    async with state.proxy() as data:
        if message.text == 'Стандарт 22':
            data['ssh_port'] = 22
        elif message.text == 'Выбрать порт':
            await message.answer("Введите номер порта SSH:", reply_markup=types.ReplyKeyboardRemove())
            return
        else:
            try:
                port = int(message.text)
                if port < 1 or port > 65535:
                    await message.answer("❌ Порт должен быть от 1 до 65535. Введите снова:")
                    return
                data['ssh_port'] = port
            except:
                await message.answer("❌ Неверный формат порта. Введите число:")
                return
    
    await AddServer.next()
    await message.answer("Введите имя пользователя SSH (обычно root):", reply_markup=types.ReplyKeyboardRemove())

# Обработка имени пользователя
async def process_ssh_username(message: types.Message, state: FSMContext):
    if message.text == '🔙 Назад':
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        port_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        port_kb.add(KeyboardButton('Стандарт 22'), KeyboardButton('Выбрать порт'), KeyboardButton('🔙 Назад'))
        await AddServer.ssh_port.set()
        await message.answer("Выберите SSH порт:", reply_markup=port_kb)
        return
    
    async with state.proxy() as data:
        data['ssh_username'] = message.text
    
    # Клавиатура выбора метода аутентификации
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    method_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    method_kb.add(KeyboardButton('Пароль'), KeyboardButton('SSH ключ'), KeyboardButton('🔙 Назад'))
    
    await AddServer.next()
    await message.answer("Выберите метод аутентификации:", reply_markup=method_kb)

# Обработка метода аутентификации
async def process_ssh_method(message: types.Message, state: FSMContext):
    if message.text == '🔙 Назад':
        await AddServer.ssh_username.set()
        await message.answer("Введите имя пользователя SSH (обычно root):")
        return
    
    async with state.proxy() as data:
        data['ssh_method'] = message.text
    
    if message.text == 'Пароль':
        await AddServer.next()
        await message.answer("Введите пароль SSH:", reply_markup=types.ReplyKeyboardRemove())
    elif message.text == 'SSH ключ':
        await AddServer.ssh_key.set()
        await message.answer("Отправьте SSH приватный ключ (текстом):", reply_markup=types.ReplyKeyboardRemove())

# Обработка пароля
async def process_ssh_password(message: types.Message, state: FSMContext):
    if message.text == '🔙 Назад':
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        method_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        method_kb.add(KeyboardButton('Пароль'), KeyboardButton('SSH ключ'), KeyboardButton('🔙 Назад'))
        await AddServer.ssh_method.set()
        await message.answer("Выберите метод аутентификации:", reply_markup=method_kb)
        return
    
    async with state.proxy() as data:
        data['ssh_password'] = message.text
    
    await install_vpn(message, state)

# Обработка SSH ключа
async def process_ssh_key(message: types.Message, state: FSMContext):
    if message.text == '🔙 Назад':
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        method_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        method_kb.add(KeyboardButton('Пароль'), KeyboardButton('SSH ключ'), KeyboardButton('🔙 Назад'))
        await AddServer.ssh_method.set()
        await message.answer("Выберите метод аутентификации:", reply_markup=method_kb)
        return
    
    async with state.proxy() as data:
        data['ssh_key'] = message.text
    
    await install_vpn(message, state)

# Основная функция установки VPN
async def install_vpn(message: types.Message, state: FSMContext):
    from keyboards import admin_main_kb
    from aiogram import Bot
    import asyncio
    
    bot = Bot.get_current()
    
    async with state.proxy() as data:
        host = data['host']
        port = data['ssh_port']
        username = data['ssh_username']
        password = data.get('ssh_password')
        ssh_key = data.get('ssh_key')
    
    # Логируем начало установки админу
    await bot.send_message(ADMIN_CHAT_ID, f"🚀 Начинаю установку VPN на сервер {host}:{port}")
    
    try:
        # Создаем SSH клиент
        ssh_client = SSHClient(host, port, username, password, ssh_key)
        
        # Устанавливаем x-ui
        success, panel_url, logs = await install_xui(ssh_client, bot)
        
        if success:
            # Сохраняем сервер в БД
            conn = sqlite3.connect('vpn_bot.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO servers (host, ssh_port, ssh_username, ssh_password, ssh_key, panel_port, panel_path, panel_password)
                VALUES (?, ?, ?, ?, ?, 54321, ?, 'admin12345')
            ''', (host, port, username, password, ssh_key, panel_url.split('/')[-1]))
            server_id = cursor.lastrowid
            
            # Получаем характеристики сервера
            await bot.send_message(ADMIN_CHAT_ID, "📊 Получаю характеристики сервера...")
            
            client = await ssh_client.connect()
            
            # Получаем RAM
            ram_log, _ = await ssh_client.execute_command(client, "free -h | awk '/^Mem:/ {print $2}'")
            ram = ram_log.strip() if ram_log.strip() else "Не определена"
            
            # Получаем CPU
            cpu_log, _ = await ssh_client.execute_command(client, "lscpu | grep 'Model name' | cut -d':' -f2 | xargs")
            cpu = cpu_log.strip() if cpu_log.strip() else "Не определен"
            
            # Получаем дисковое пространство
            disk_log, _ = await ssh_client.execute_command(client, "df -h / | awk 'NR==2 {print $2}'")
            disk = disk_log.strip() if disk_log.strip() else "Не определено"
            
            client.close()
            
            # Обновляем информацию о сервере
            cursor.execute('''
                UPDATE servers SET 
                ram_info = ?, cpu_info = ?, disk_info = ?
                WHERE id = ?
            ''', (ram, cpu, disk, server_id))
            conn.commit()
            conn.close()
            
            # Отправляем результат админу
            result_msg = (
                f"✅ VPN успешно установлен!\n\n"
                f"🌐 Сервер: {host}\n"
                f"🔗 Панель управления: {panel_url}\n"
                f"👤 Логин: admin\n"
                f"🔑 Пароль: admin12345\n\n"
                f"📊 Характеристики сервера:\n"
                f"• RAM: {ram}\n"
                f"• CPU: {cpu}\n"
                f"• Диск: {disk}\n\n"
                f"🔧 Порты открыты: 54321, 443, 2096\n"
                f"⚡ Reality настроен на порту 443"
            )
            
            await bot.send_message(ADMIN_CHAT_ID, result_msg)
            await message.answer("✅ Сервер успешно добавлен и VPN установлен!", reply_markup=admin_main_kb)
            
        else:
            # Ошибка установки
            error_msg = f"❌ Ошибка установки VPN на {host}:\n\n{logs[-1000:]}"
            await bot.send_message(ADMIN_CHAT_ID, error_msg)
            await message.answer("❌ Ошибка при установке VPN. Подробности в лог-чате.", reply_markup=admin_main_kb)
    
    except Exception as e:
        error_msg = f"❌ Критическая ошибка: {str(e)}"
        await bot.send_message(ADMIN_CHAT_ID, error_msg)
        await message.answer("❌ Произошла ошибка. Подробности в лог-чате.", reply_markup=admin_main_kb)
    
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
            text += f"📊 Пользователи: {server[3]}/{server[4]}\n"
            text += f"💾 RAM: {server[5] or 'Нет данных'}\n"
            text += f"⚡ CPU: {server[6] or 'Нет данных'}\n"
            text += f"🔧 Статус: {server[2]}\n"
            text += "─" * 20 + "\n"
    else:
        text = "❌ Серверов нет"
    
    from keyboards import admin_servers_kb
    await message.answer(text, reply_markup=admin_servers_kb)

# 4. Кнопка "⚙️ Управление серверами"
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
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup()
    for server in servers:
        kb.add(InlineKeyboardButton(f"🖥 {server[1]}", callback_data=f"manage_server_{server[0]}"))
    
    await message.answer("Выберите сервер для управления:", reply_markup=kb)

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
    await message.answer("Введите ID пользователя для выдачи VPN (например: 123456789):", reply_markup=types.ReplyKeyboardRemove())

# Обработка выдачи VPN (простая версия)
async def process_give_vpn(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        user_id = int(message.text)
        from keyboards import tariffs_kb
        await message.answer(f"Выберите тариф для пользователя {user_id}:", reply_markup=tariffs_kb)
    except:
        await message.answer("❌ Неверный ID пользователя")

# 7. Кнопка "🚫 Отключить VPN"
async def disable_vpn(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите ID пользователя для отключения VPN:", reply_markup=types.ReplyKeyboardRemove())

# 8. Кнопка "💰 Метод оплаты" - ВЕБХУК
async def payment_method(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    # Генерируем URL вебхука для Tribute
    webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url=https://ваш-сервер.ру/tribute_webhook"
    
    instruction = (
        f"🔗 Вебхук для Tribute:\n\n"
        f"1. URL для настройки вебхука:\n"
        f"`{webhook_url}`\n\n"
        f"2. API ключ Tribute:\n"
        f"`42d4d099-20fd-4f55-a196-d77d9fed`\n\n"
        f"3. Инструкция:\n"
        f"• Зайдите в панель Tribute\n"
        f"• Добавьте этот URL как вебхук\n"
        f"• Укажите API ключ выше\n"
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
    
    stats = f"📊 Статистика:\n🖥 Серверов: {servers}\n👥 Пользователей: {users}\n📅 Подписок: {active_subs}\n💰 Доход: {income}₽"
    conn.close()
    
    from keyboards import admin_main_kb
    await message.answer(stats, reply_markup=admin_main_kb)

# 10. Кнопка "🔙 Назад" для админа
async def admin_back(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    from keyboards import admin_main_kb
    await message.answer("👑 Админ-панель", reply_markup=admin_main_kb)

# Регистрируем ВСЕ обработчики
def register_admin_handlers(dp: Dispatcher):
    # Основные кнопки
    dp.register_message_handler(admin_servers, text='🖥 Сервера', user_id=ADMIN_ID)
    dp.register_message_handler(add_server_start, text='➕ Добавить сервер', user_id=ADMIN_ID)
    dp.register_message_handler(list_servers, text='📋 Список серверов', user_id=ADMIN_ID)
    dp.register_message_handler(manage_servers, text='⚙️ Управление серверами', user_id=ADMIN_ID)
    dp.register_message_handler(admin_users, text='👥 Пользователи', user_id=ADMIN_ID)
    dp.register_message_handler(give_vpn, text='🎁 Выдать VPN', user_id=ADMIN_ID)
    dp.register_message_handler(disable_vpn, text='🚫 Отключить VPN', user_id=ADMIN_ID)
    dp.register_message_handler(payment_method, text='💰 Метод оплаты', user_id=ADMIN_ID)
    dp.register_message_handler(admin_stats, text='📊 Статистика', user_id=ADMIN_ID)
    dp.register_message_handler(admin_back, text='🔙 Назад', user_id=ADMIN_ID)
    
    # Обработчики состояний добавления сервера
    dp.register_message_handler(process_host, state=AddServer.host)
    dp.register_message_handler(process_ssh_port, state=AddServer.ssh_port)
    dp.register_message_handler(process_ssh_username, state=AddServer.ssh_username)
    dp.register_message_handler(process_ssh_method, state=AddServer.ssh_method)
    dp.register_message_handler(process_ssh_password, state=AddServer.ssh_password)
    dp.register_message_handler(process_ssh_key, state=AddServer.ssh_key)
    
    # Обработчик выдачи VPN
    dp.register_message_handler(process_give_vpn, user_id=ADMIN_ID)