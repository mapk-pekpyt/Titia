import re
import asyncio
import logging
from utils.ssh_client import SSHClient

logger = logging.getLogger(__name__)

class VPNInstaller:
    def __init__(self, ssh_client: SSHClient, bot=None, chat_id=None):
        self.ssh = ssh_client
        self.bot = bot
        self.chat_id = chat_id
        self.logs = []
    
    async def log(self, message):
        """Добавляем сообщение в логи"""
        self.logs.append(message)
        logger.info(message)
        
        if self.bot and self.chat_id:
            try:
                if len(message) < 100:
                    await self.bot.send_message(self.chat_id, message)
            except Exception as e:
                logger.error(f"Не удалось отправить лог в Telegram: {e}")
    
    async def execute_with_log(self, command, timeout=60):
        """Выполняет команду и логирует результат"""
        await self.log(f"🛠️  Выполняю: {command[:100]}...")
        
        try:
            # Выполняем команду через SSH
            output, error = await self.ssh.execute(command, timeout=timeout)
            
            # Логируем результат
            if output:
                clean_output = output.strip()
                if clean_output:
                    await self.log(f"📤 Вывод: {clean_output[:200]}" + ("..." if len(clean_output) > 200 else ""))
            
            if error:
                clean_error = error.strip()
                if clean_error and "WARNING: apt does not have" not in clean_error:
                    await self.log(f"⚠️  Ошибка: {clean_error[:200]}" + ("..." if len(clean_error) > 200 else ""))
            
            return output, error
            
        except asyncio.TimeoutError:
            await self.log(f"⏱️  Таймаут команды: {command[:50]}...")
            return None, "Таймаут"
        except Exception as e:
            await self.log(f"❌ Исключение при выполнении: {str(e)}")
            return None, str(e)
    
    async def get_server_info(self):
        """Получить характеристики сервера"""
        try:
            await self.log("🔍 Получаю информацию о сервере...")
            
            # RAM
            ram_out, _ = await self.execute_with_log("free -h | awk '/^Mem:/ {print $2}'")
            ram = ram_out.strip() if ram_out else "Не определена"
            
            # CPU
            cpu_out, _ = await self.execute_with_log("lscpu | grep 'Model name' | cut -d':' -f2 | xargs")
            cpu = cpu_out.strip() if cpu_out else "Не определен"
            
            # Disk
            disk_out, _ = await self.execute_with_log("df -h / | awk 'NR==2 {print $2}'")
            disk = disk_out.strip() if disk_out else "Не определено"
            
            # OS
            os_out, _ = await self.execute_with_log("cat /etc/os-release | grep 'PRETTY_NAME' | cut -d'=' -f2 | tr -d '\"'")
            os_info = os_out.strip() if os_out else "Не определена"
            
            await self.log(f"""
📊 Информация о сервере:
├─ ОЗУ: {ram}
├─ ЦПУ: {cpu}
├─ Диск: {disk}
└─ ОС: {os_info}
            """)
            
            return {
                'ram': ram,
                'cpu': cpu,
                'disk': disk,
                'os': os_info,
                'success': True
            }
            
        except Exception as e:
            await self.log(f"❌ Ошибка получения информации: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def install_xui(self):
        """Основная установка x-ui"""
        try:
            # Подключение
            await self.log("🔗 Подключаюсь к серверу по SSH...")
            if not await self.ssh.connect():
                return False, None, "❌ Не удалось подключиться по SSH"
            await self.log("✅ SSH подключение установлено")
            
            # Шаг 1: Обновление системы
            await self.log("📦 Шаг 1: Обновление системы...")
            await self.execute_with_log("sudo apt update", timeout=60)
            await self.execute_with_log("sudo apt upgrade -y", timeout=120)
            
            # Шаг 2: Установка зависимостей
            await self.log("📦 Шаг 2: Установка зависимостей...")
            await self.execute_with_log("sudo apt install curl wget git ufw sqlite3 expect -y", timeout=120)
            
            # Шаг 3: Установка x-ui (упрощенный метод)
            await self.log("🚀 Шаг 3: Установка x-ui...")
            await self.log("ℹ️  Это займет 2-3 минуты...")
            
            # Установочная команда с автоматическими ответами
            install_cmd = """
            sudo bash -c '
            curl -Ls https://raw.githubusercontent.com/alireza0/x-ui/master/install.sh | bash << EOF
54321
admin
admin12345
EOF
            '
            """
            
            # Запускаем установку
            await self.execute_with_log(install_cmd, timeout=180)
            
            # Небольшая пауза
            await self.log("⏳ Жду завершения установки...")
            await asyncio.sleep(10)
            
            # Проверяем установку
            await self.log("🔍 Проверяю установку...")
            
            # Проверяем статус службы
            status, _ = await self.execute_with_log("sudo systemctl is-active x-ui 2>/dev/null || echo 'inactive'")
            
            if "active" not in status:
                await self.log("⚠️  Пробую запустить x-ui...")
                await self.execute_with_log("sudo systemctl start x-ui")
                await asyncio.sleep(3)
                status, _ = await self.execute_with_log("sudo systemctl is-active x-ui 2>/dev/null || echo 'inactive'")
            
            if "active" in status:
                await self.log("✅ X-UI успешно запущен")
            else:
                await self.log("⚠️  X-UI не запущен автоматически")
            
            # Получаем данные из БД
            await self.log("📊 Получаю данные панели...")
            
            # Порт
            port_output, _ = await self.execute_with_log("sudo sqlite3 /etc/x-ui/x-ui.db 'SELECT port FROM settings' 2>/dev/null || echo '54321'")
            port = port_output.strip() if port_output and port_output.strip().isdigit() else "54321"
            
            # Путь
            path_output, _ = await self.execute_with_log("sudo sqlite3 /etc/x-ui/x-ui.db 'SELECT path FROM settings' 2>/dev/null || echo 'admin'")
            path = path_output.strip() if path_output and path_output.strip() else "admin"
            
            # Сбрасываем пароль на известный
            await self.log("🔐 Устанавливаю пароль...")
            await self.execute_with_log("echo -e 'y\\nadmin12345' | sudo x-ui resetpassword", timeout=30)
            
            # Шаг 4: Настройка фаервола
            await self.log("🔓 Шаг 4: Настройка фаервола...")
            
            # Убедимся что UFW установлен
            await self.execute_with_log("sudo apt install ufw -y 2>/dev/null || true", timeout=60)
            
            # Открываем порты
            ports_to_open = [port, "443", "2096"]
            for p in ports_to_open:
                await self.execute_with_log(f"sudo ufw allow {p}/tcp")
            
            # Включаем фаервол
            await self.execute_with_log("sudo ufw --force enable")
            
            # Проверяем статус
            ufw_status, _ = await self.execute_with_log("sudo ufw status verbose")
            await self.log(f"📡 Статус фаервола: {ufw_status[:300]}")
            
            # Шаг 5: Финальные данные
            await self.log("🌐 Получаю внешний IP...")
            ip_output, _ = await self.execute_with_log("curl -s ifconfig.me")
            server_ip = ip_output.strip() if ip_output else self.ssh.host
            
            # Формируем URL панели
            panel_url = f"http://{server_ip}:{port}/{path}"
            
            await self.log(f"""
🎉 УСТАНОВКА ЗАВЕРШЕНА!

📊 РЕЗУЛЬТАТ:
├─ 🔗 Панель: {panel_url}
├─ 👤 Логин: admin
├─ 🔑 Пароль: admin12345
├─ 🌐 IP: {server_ip}
├─ 🚪 Порт панели: {port}
├─ 📍 Путь: /{path}
└─ 🔧 Режим: Reality на порту 443

📋 ИНСТРУКЦИЯ:
1. Перейдите по ссылке выше
2. Войдите с логином/паролем
3. Создайте Reality подключение
4. Порт Reality: 443
5. SNI: www.google.com
6. SPX: yass
            """)
            
            # Закрываем SSH
            self.ssh.close()
            
            # Возвращаем результат
            full_log = "\n".join(self.logs[-50:])  # Последние 50 строк
            return True, panel_url, full_log
            
        except Exception as e:
            error_msg = f"❌ Критическая ошибка установки: {str(e)}"
            await self.log(error_msg)
            
            if hasattr(self, 'ssh') and self.ssh:
                self.ssh.close()
            
            full_log = "\n".join(self.logs)
            return False, None, full_log


# Функции для обратной совместимости
async def get_server_info(ssh_client: SSHClient):
    """Совместимость со старым кодом"""
    installer = VPNInstaller(ssh_client)
    return await installer.get_server_info()

async def install_xui(ssh_client: SSHClient, bot=None):
    """Совместимость со старым кодом"""
    installer = VPNInstaller(ssh_client, bot)
    return await installer.install_xui()