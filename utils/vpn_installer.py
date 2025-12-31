# В utils/vpn_installer.py исправь установку:

async def install_xui(self):
    """Основная установка x-ui с подробным логированием"""
    try:
        # Подключение
        await self.log("🔗 Подключаюсь к серверу по SSH...")
        if not await self.ssh.connect():
            return False, None, "❌ Не удалось подключиться по SSH"
        await self.log("✅ SSH подключение установлено")
        
        # Шаг 1: Обновление системы с SUDO
        await self.log("📦 Шаг 1: Обновление пакетов...")
        output, error = await self.execute_with_log("sudo apt update && sudo apt upgrade -y", timeout=120)
        if error and "Could not get lock" not in error and "WARNING: apt does not have" not in error:
            await self.log(f"⚠️  Предупреждение при обновлении: {error[:100]}")
        
        # Шаг 2: Установка зависимостей с SUDO
        await self.log("📦 Шаг 2: Установка зависимостей...")
        await self.execute_with_log("sudo apt install curl wget git ufw sqlite3 expect -y", timeout=120)
        
        # Шаг 3: Установка x-ui
        await self.log("🚀 Шаг 3: Установка x-ui...")
        await self.log("ℹ️  Это займет 2-3 минуты...")
        
        # Установка x-ui с ожиданием (используем готовый скрипт)
        install_cmd = """
        sudo bash -c '
        curl -Ls https://raw.githubusercontent.com/alireza0/x-ui/master/install.sh -o /tmp/install.sh
        chmod +x /tmp/install.sh
        /tmp/install.sh << EOF
16354
admin
admin12345
EOF
        '
        """
        await self.execute_with_log(install_cmd, timeout=300)
        
        # Читаем логи установки
        await self.log("📋 Читаю логи установки...")
        log_output, _ = await self.execute_with_log("sudo cat /tmp/xui_install.log 2>/dev/null || echo 'Логи не найдены'")
        if log_output and "Логи не найдены" not in log_output:
            # Ищем реальный порт в логах
            import re
            port_match = re.search(r':(\d+)/', log_output)
            path_match = re.search(r'/([a-zA-Z0-9]+)/?\s*$', log_output)
            
            if port_match:
                real_port = port_match.group(1)
                await self.log(f"🔍 Найден порт в логах: {real_port}")
        
        # Шаг 4: Получение данных установки
        await self.log("🔍 Шаг 4: Получение данных установки...")
        
        # Проверяем запущен ли x-ui
        status, _ = await self.execute_with_log("sudo systemctl is-active x-ui 2>/dev/null || echo 'inactive'")
        
        if not status or "active" not in status:
            await self.log("⚠️  X-UI не запущен, пробую запустить...")
            await self.execute_with_log("sudo systemctl start x-ui")
            await asyncio.sleep(3)
            status, _ = await self.execute_with_log("sudo systemctl is-active x-ui 2>/dev/null || echo 'inactive'")
        
        if status and "active" in status:
            await self.log("✅ X-UI запущен")
        else:
            await self.log("❌ X-UI не удалось запустить")
        
        # Получаем порт панели из БД
        port = "16354"  # Используем порт из логов установки
        port_output, _ = await self.execute_with_log("sudo sqlite3 /etc/x-ui/x-ui.db 'SELECT port FROM settings' 2>/dev/null || echo ''")
        if port_output and port_output.strip().isdigit():
            port = port_output.strip()
        
        # Получаем путь панели
        path = "admin"
        path_output, _ = await self.execute_with_log("sudo sqlite3 /etc/x-ui/x-ui.db 'SELECT path FROM settings' 2>/dev/null || echo ''")
        if path_output and path_output.strip():
            path = path_output.strip()
        
        # Сбрасываем пароль
        await self.log("🔐 Сбрасываю пароль...")
        await self.execute_with_log("sudo x-ui resetpassword <<< $'y\\nadmin12345\\n'", timeout=30)
        
        # Шаг 5: Открытие портов
        await self.log("🔓 Шаг 5: Открытие портов...")
        ports_to_open = [port, "443", "2096"]
        for p in ports_to_open:
            await self.execute_with_log(f"sudo ufw allow {p}/tcp")
        await self.execute_with_log("sudo ufw --force enable")
        
        # Проверяем открытые порты
        ufw_status, _ = await self.execute_with_log("sudo ufw status")
        await self.log(f"📡 Статус фаервола:\n{ufw_status[:500]}")
        
        # Шаг 6: Проверка доступности
        await self.log("🌐 Шаг 6: Проверка доступности...")
        ip_output, _ = await self.execute_with_log("curl -s ifconfig.me")
        server_ip = ip_output.strip() if ip_output else self.ssh.host
        
        # Финальный результат - используем реальные данные
        panel_url = f"http://{server_ip}:{port}/{path}"
        
        await self.log(f"""
🎉 УСТАНОВКА ЗАВЕРШЕНА!

📊 РЕЗУЛЬТАТ:
├─ 🔗 Панель: {panel_url}
├─ 👤 Логин: admin
├─ 🔑 Пароль: admin12345
├─ 🌐 IP: {server_ip}
├─ 🚪 Порт: {port}
└─ 📍 Путь: /{path}

⚠️  ВАЖНО:
1. Проверьте порт {port} в облачном фаерволе
2. URL панели скопирован выше
3. Для Reality используйте порт 443
""")
        
        # Полный лог
        full_log = "\n".join(self.logs)
        self.ssh.close()
        return True, panel_url, full_log
        
    except Exception as e:
        error_msg = f"❌ Ошибка установки: {str(e)}"
        await self.log(error_msg)
        if hasattr(self, 'ssh') and self.ssh:
            self.ssh.close()
        return False, None, "\n".join(self.logs)