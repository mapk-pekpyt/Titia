import asyncio
import random
import string
import logging
from .ssh_client import SSHClient

logger = logging.getLogger(__name__)

class VPNInstaller:
    def __init__(self, ssh_client: SSHClient, bot=None, chat_id=None):
        self.ssh = ssh_client
        self.bot = bot
        self.chat_id = chat_id
    
    async def send_progress(self, message):
        """Отправляет прогресс установки"""
        if self.bot and self.chat_id:
            try:
                await self.bot.send_message(self.chat_id, message)
            except:
                pass
    
    async def install_xui(self):
        """Устанавливает x-ui с прогрессом"""
        try:
            await self.send_progress("🔄 Шаг 1/8: Обновление системы...")
            await self.ssh.execute("sudo apt update && sudo apt upgrade -y", timeout=60)
            
            await self.send_progress("🔄 Шаг 2/8: Установка зависимостей...")
            await self.ssh.execute("sudo apt install curl wget git ufw -y", timeout=60)
            
            panel_port = random.randint(10000, 60000)
            panel_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            
            await self.send_progress(f"🔄 Шаг 3/8: Установка x-ui (порт: {panel_port})...")
            
            # Используем фоновую установку
            install_script = f"""
            nohup bash -c '
            curl -Ls https://raw.githubusercontent.com/alireza0/x-ui/master/install.sh -o install.sh
            chmod +x install.sh
            echo -e "{panel_port}\\nadmin\\n{panel_password}" | sudo ./install.sh > /tmp/xui_install.log 2>&1
            ' > /dev/null 2>&1 &
            """
            await self.ssh.execute(install_script)
            
            # Ждём установку с проверкой
            for i in range(30):
                await asyncio.sleep(10)
                await self.send_progress(f"⏳ Ожидание установки... ({i+1}/30)")
                
                # Проверяем статус
                check_cmd = "pgrep -f 'x-ui' || echo 'not running'"
                output, _ = await self.ssh.execute(check_cmd)
                if 'not running' not in output:
                    break
            
            await self.send_progress("🔄 Шаг 4/8: Сброс пароля...")
            await self.ssh.execute("sudo x-ui resetpassword > /dev/null 2>&1", timeout=30)
            
            await self.send_progress("🔄 Шаг 5/8: Открытие портов...")
            await self.ssh.execute(f"sudo ufw allow {panel_port}/tcp", timeout=10)
            await self.ssh.execute("sudo ufw allow 443/tcp", timeout=10)
            await self.ssh.execute("sudo ufw allow 2096/tcp", timeout=10)
            await self.ssh.execute("sudo ufw --force enable", timeout=10)
            
            await self.send_progress("🔄 Шаг 6/8: Получение IP...")
            ip_output, _ = await self.ssh.execute("curl -s ifconfig.me", timeout=10)
            server_ip = ip_output.strip()
            
            await self.send_progress("🔄 Шаг 7/8: Настройка Reality...")
            panel_path = '/' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
            
            # Устанавливаем пароль для панели
            set_pass_cmd = f"sudo x-ui <<EOF\n5\ny\nEOF"
            await self.ssh.execute(set_pass_cmd)
            
            await self.send_progress("✅ Установка завершена!")
            
            return {
                "success": True,
                "panel_url": f"http://{server_ip}:{panel_port}{panel_path}",
                "username": "admin",
                "password": panel_password,
                "server_ip": server_ip,
                "panel_port": panel_port
            }
            
        except Exception as e:
            logger.error(f"Install error: {e}")
            await self.send_progress(f"❌ Ошибка: {str(e)[:100]}")
            return {"success": False, "error": str(e)}