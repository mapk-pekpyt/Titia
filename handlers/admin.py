# Добавь в конец файла:

@router.callback_query(F.data.startswith("admin_confirm_"))
async def admin_confirm_payment(callback: CallbackQuery):
    data = callback.data.split("_")
    user_id = data[2]
    server_id = data[3]
    tariff = data[4]
    
    tariff_info = TARIFFS[tariff]
    days = tariff_info['days']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Активируем подписку
    end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        UPDATE subscriptions 
        SET payment_status = 'active', start_date = datetime('now'), end_date = ?
        WHERE user_id = ? AND server_id = ? AND tariff = ?
    ''', (end_date, user_id, server_id, tariff))
    
    # Увеличиваем счетчик пользователей
    cursor.execute('''
        UPDATE servers SET current_users = current_users + 1 WHERE id = ?
    ''', (server_id,))
    
    # Получаем данные сервера для уведомления пользователя
    cursor.execute('SELECT server_name FROM servers WHERE id = ?', (server_id,))
    server_name = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    # Уведомляем пользователя
    await callback.bot.send_message(
        user_id,
        f"✅ Ваша подписка активирована!\n\n"
        f"Тариф: {tariff_info['name']}\n"
        f"Сервер: {server_name}\n"
        f"Доступ до: {end_date}\n\n"
        f"Для получения конфигурации нажмите 'Моя подписка'."
    )
    
    await callback.message.edit_text(
        f"✅ Оплата подтверждена!\n"
        f"Пользователь: {user_id}\n"
        f"Тариф: {tariff}\n"
        f"Сервер: {server_name}"
    )

@router.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_payment(callback: CallbackQuery):
    user_id = callback.data.split("_")[2]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions WHERE user_id = ? AND payment_status = 'pending'", (user_id,))
    conn.commit()
    conn.close()
    
    await callback.bot.send_message(user_id, "❌ Ваш заказ был отклонен администратором.")
    await callback.message.edit_text(f"❌ Заказ пользователя {user_id} отклонен.")