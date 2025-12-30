from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Кнопка "Назад" для Reply
def back_button():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )

# Главное меню пользователя
def user_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛡️ Получить VPN")],
            [KeyboardButton(text="📊 Моя подписка"), KeyboardButton(text="🆘 Поддержка")]
        ],
        resize_keyboard=True
    )

# Главное меню админа
def admin_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🖥️ Серверы")],
            [KeyboardButton(text="💰 Реквизиты оплаты"), KeyboardButton(text="📝 Логи")],
            [KeyboardButton(text="👤 Пользователи"), KeyboardButton(text="🆘 Поддержка")]
        ],
        resize_keyboard=True
    )

# Меню серверов (добавлена кнопка "Назад")
def servers_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить сервер", callback_data="add_server")],
            [InlineKeyboardButton(text="📋 Список серверов", callback_data="list_servers")],
            [InlineKeyboardButton(text="⚙️ Управление", callback_data="manage_servers")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
        ]
    )

# Выбор типа аутентификации
def auth_type_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔑 По ключу (SSH Key)", callback_data="auth_key")],
            [InlineKeyboardButton(text="🔓 По паролю", callback_data="auth_password")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="servers_back")]
        ]
    )

# Тарифы
def tariffs_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1 день (пробный)", callback_data="tariff_trial")],
            [InlineKeyboardButton(text="1 неделя - 100₽", callback_data="tariff_week")],
            [InlineKeyboardButton(text="1 месяц - 250₽", callback_data="tariff_month")],
            [InlineKeyboardButton(text="2 месяца - 450₽", callback_data="tariff_2months")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="user_back")]
        ]
    )

# Подтверждение оплаты
def payment_confirm_menu(sub_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_{sub_id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{sub_id}")]
        ]
    )

# Управление сервером
def server_management_menu(server_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Получить ссылку на панель", callback_data=f"panel_{server_id}")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_{server_id}")],
            [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_{server_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="list_servers")]
        ]
    )