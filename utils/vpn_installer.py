import re
import asyncio
from utils.ssh_client import SSHClient
import logging

logger = logging.getLogger(__name__)

class VPNInstaller:
    def __init__(self, ssh_client: SSHClient, bot=None, chat_id=None):
        self.ssh = ssh_client
        self.bot = bot
        self.chat_id = chat_id
        self.logs = []
    
    async def log(self, message):
        """Добавляем сообщение в логи и отправляем в Telegram"""
        self.logs.append(message)
        logger.info(message)
        
        if self.bot and self.chat_id:
            try:
                # Отправляем короткие сообщения
                if len(message) < 100:
                    await self.bot.send_message(self.chat_id, message)
                else:
                    # Длинные логи отправляем как отдельное сообщение
                    await self.bot.send_message(self.chat_id, "📋 Лог обновлён (см. полный лог)")
            except Exception as e:
                logger.error(f"Не удалось отправить лог в Telegram: {e}")
    
    async def execute_with_log(self, command, timeout=60):
        """Выполняет команду и логирует результат"""
        await self.log(f"🛠️  Выполняю: {command[:100]}...")
        
        try:
            output, error = await self.ssh.execute(command, timeout=timeout)
            
            if output:
                await self.log(f"📤 Вывод: {output[:200]}" + ("..." if len(output) > 200 else ""))
            if error:
                await self.log(f"⚠️  Ошибка: {error[:200]}" + ("..." if len(error) > 200 else ""))
            
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
        """Основная установка x-ui с подробным логированием"""
        try:
            # Подключение
            await self.log("🔗 Подключаюсь к серверу по SSH...")
            if not await self.ssh.connect():
                return False, None, "❌ Не удалось подключиться по SSH"
            await self.log("✅ SSH подключение установлено")
            
            # Шаг 1: Обновление системы
            await self.log("📦 Шаг 1: Обновление пакетов...")
            output, error = await self.execute_with_log("apt update && apt upgrade -y", timeout=120)
            if error and "Could not get lock" not in error:
                await self.log(f"⚠️  Предупреждение при обновлении: {error[:100]}")
            
            # Шаг 2: Установка зависимостей
            await self.log("📦 Шаг 2: Установка зависимостей...")
            await self.execute_with_log("apt install curl wget git ufw sqlite3 -y", timeout=120)
            
            # Шаг 3: Установка x-ui
            await self.log("🚀 Шаг 3: Установка x-ui...")
            await self.log("ℹ️  Это займет 2-3 минуты...")
            
            # Скачиваем установочный скрипт
            await self.execute_with_log("curl -Ls https://raw.githubusercontent.com/alireza0/x-ui/master/install.sh -o install.sh")
            await self.execute_with_log("chmod +x install.sh")
            
            # Запускаем установку с логированием в файл
            install_log = "/tmp/xui_install.log"
            install_cmd = f"sudo ./install.sh > {install_log} 2>&1"
            await self.execute_with_log(install_cmd, timeout=180)
            
            # Читаем логи установки
            await self.log("📋 Читаю логи установки...")
            log_output, _ = await self.execute_with_log(f"cat {install_log} | tail -50")
            if log_output:
                await self.log(f"📜 Логи установки (последние 50 строк):\n{log_output[-1000:]}")
            
            # Шаг 4: Получение данных установки
            await self.log("🔍 Шаг 4: Получение данных установки...")
            
            # Проверяем запущен ли x-ui
            status, _ = await self.execute_with_log("systemctl is-active x-ui")
            if not status or "active" not in status:
                await self.log("⚠️  X-UI не запущен, пробую запустить...")
                await self.execute_with_log("systemctl start x-ui")
                await asyncio.sleep(3)
                status, _ = await self.execute_with_log("systemctl is-active x-ui")
            
            if status and "active" in status:
                await self.log("✅ X-UI запущен")
            else:
                await self.log("❌ X-UI не удалось запустить")
                # Пробуем получить больше информации
                journal, _ = await self.execute_with_log("journalctl -u x-ui -n 30 --no-pager")
                if journal:
                    await self.log(f"📋 Логи systemd:\n{journal[-500:]}")
            
            # Получаем порт панели
            port = "54321"
            port_output, _ = await self.execute_with_log("sqlite3 /etc/x-ui/x-ui.db 'SELECT port FROM settings' 2>/dev/null || echo ''")
            if port_output and port_output.strip().isdigit():
                port = port_output.strip()
            
            # Получаем путь панели
            path = "admin"
            path_output, _ = await self.execute_with_log("sqlite3 /etc/x-ui/x-ui.db 'SELECT path FROM settings' 2>/dev/null || echo ''")
            if path_output and path_output.strip():
                path = path_output.strip()
            
            # Получаем пароль
            password = "admin"
            # Пробуем сбросить пароль на известный
            await self.execute_with_log("x-ui resetpassword <<< $'y\\n'", timeout=30)
            
            # Шаг 5: Открытие портов
            await self.log("🔓 Шаг 5: Открытие портов...")
            ports_to_open = [port, "443", "2096"]
            for p in ports_to_open:
                await self.execute_with_log(f"ufw allow {p}/tcp")
            await self.execute_with_log("ufw --force enable")
            await self.log(f"✅ Порты открыты: {', '.join(ports_to_open)}")
            
            # Шаг 6: Проверка доступности
            await self.log("🌐 Шаг 6: Проверка доступности...")
            ip_output, _ = await self.execute_with_log("curl -s ifconfig.me")
            server_ip = ip_output.strip() if ip_output else self.ssh.host
            
            # Финальный результат
            panel_url = f"http://{server_ip}:{port}/{path}"
            
            await self.log(f"""
🎉 УСТАНОВКА ЗАВЕРШЕНА!
            
📊 РЕЗУЛЬТАТ:
├─ 🔗 Панель: {panel_url}
├─ 👤 Логин: admin
├─ 🔑 Пароль: admin
├─ 🌐 IP: {server_ip}
├─ 🚪 Порт: {port}
└─ 📍 Путь: /{path}

⚠️  ЕСЛИ ПАНЕЛЬ НЕ ОТКРЫВАЕТСЯ:
1. Проверьте порт {port} в облачном фаерволе (Oracle Cloud Security List)
2. Убедитесь что порт открыт: sudo ufw status | grep {port}
3. Проверьте статус: systemctl status x-ui
            """)
            
            # Отправляем полный лог
            full_log = "\n".join(self.logs)
            if self.bot and self.chat_id:
                try:
                    if len(full_log) > 4000:
                        # Разбиваем на части
                        for i in range(0, len(full_log), 4000):
                            await self.bot.send_message(self.chat_id, f"📋 Лог установки (часть {i//4000 + 1}):\n```\n{full_log[i:i+4000]}\n```", parse_mode="Markdown")
                    else:
                        await self.bot.send_message(self.chat_id, f"📋 Полный лог установки:\n```\n{full_log}\n```", parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Не удалось отправить полный лог: {e}")
            
            self.ssh.close()
            return True, panel_url, full_log
            
        except Exception as e:
            error_msg = f"❌ КРИТИЧЕСКАЯ ОШИБКА УСТАНОВКИ: {str(e)}"
            await self.log(error_msg)
            logger.exception("Ошибка установки")
            
            if self.bot and self.chat_id:
                try:
                    await self.bot.send_message(self.chat_id, f"❌ Установка провалена:\n```\n{error_msg}\n\nПоследние логи:\n{chr(10).join(self.logs[-10:])}\n```", parse_mode="Markdown")
                except:
                    pass
            
            if hasattr(self, 'ssh') and self.ssh:
                self.ssh.close()
            
            return False, None, "\n".join(self.logs)