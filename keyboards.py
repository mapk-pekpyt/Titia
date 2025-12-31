from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Главное меню админа
admin_main_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
admin_main_kb.add(
    KeyboardButton('🖥 Сервера'),
    KeyboardButton('👥 Пользователи'),
    KeyboardButton('📊 Статистика'),
    KeyboardButton('💰 Метод оплаты')
)

# Меню серверов
admin_servers_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
admin_servers_kb.add(
    KeyboardButton('➕ Добавить сервер'),
    KeyboardButton('📋 Список серверов'),
    KeyboardButton('⚙️ Управление серверами'),
    KeyboardButton('🔙 Назад')
)

# Меню пользователей
admin_users_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
admin_users_kb.add(
    KeyboardButton('🎁 Выдать VPN'),
    KeyboardButton('🚫 Отключить VPN'),
    KeyboardButton('🔙 Назад')
)

# Меню управления сервером
server_manage_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
server_manage_kb.add(
    KeyboardButton('✏️ Сменить имя'),
    KeyboardButton('👥 Изменить лимит'),
    KeyboardButton('📡 Пинг сервера'),
    KeyboardButton('🔙 Назад')
)

# Главное меню пользователя
user_main_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
user_main_kb.add(
    KeyboardButton('🔑 Получить VPN'),
    KeyboardButton('📄 Моя подписка'),
    KeyboardButton('🆘 Помощь')
)

# Тарифы
tariffs_kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
tariffs_kb.add(
    KeyboardButton('🎁 Пробник (1 день)'),
    KeyboardButton('📅 Неделя - 100₽'),
    KeyboardButton('📅 Месяц - 250₽'),
    KeyboardButton('📅 2 месяца - 450₽'),
    KeyboardButton('🔙 Назад')
)

# Кнопка "Назад" отдельно
back_kb = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton('🔙 Назад'))

# Inline кнопки для подтверждения
def confirm_kb(action):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton('✅ Да', callback_data=f'confirm_{action}'),
        InlineKeyboardButton('❌ Нет', callback_data='cancel')
    )
    return kb

# Выбор сервера
def servers_list_kb(servers):
    kb = InlineKeyboardMarkup()
    for server in servers:
        kb.add(InlineKeyboardButton(
            f"🖥 {server[1]}", 
            callback_data=f"server_{server[0]}"
        ))
    return kb