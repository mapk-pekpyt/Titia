from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from config import ADMIN_ID
from keyboards import user_main_menu, tariffs_menu, admin_main_menu

router = Router()

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
    await message.answer("Здесь будет информация о вашей подписке")

@router.message(F.text == "🆘 Поддержка")
async def support(message: Message):
    await message.answer("По всем вопросам обращайтесь: @vpnhostik")

@router.callback_query(F.data.startswith("tariff_"))
async def process_tariff(callback: CallbackQuery):
    tariff = callback.data.split("_")[1]
    await callback.answer(f"Выбран тариф: {tariff}")
    # Дополнительная логика выбора тарифа