import asyncio
import random
import string
import logging
from .ssh_client import SSHClient

logger = logging.getLogger(__name__)

class VPNInstaller:
    def __init__(self, ssh_client: SSHClient):
        self.ssh = ssh_client
    
    async def install_xui(self):
        """Устанавливает x-ui с Reality настройками"""
        try:
            # Шаг 1: Обновление системы
            await self.ssh.execute("sudo apt update && sudo apt upgrade -y")
            
            # Шаг 2: Установка зависимостей
            await self.ssh.execute("sudo apt install curl wget git -y")
            
            # Шаг 3: Генерация порта и пароля
            panel_port = random.randint(10000, 60000)
            panel_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            
            # Шаг 4: Установка x-ui
            install_cmd = f"""
            bash <(curl -Ls https://raw.githubusercontent.com/alireza0/x-ui/master/install.sh) <<EOF
            {panel_port}
            admin
            {panel_password}
            EOF
            """
            output, error = await self.ssh.execute(install_cmd)
            
            if "installation finished" not in output.lower() and not error:
                # Пробуем альтернативный метод
                await self.ssh.execute("curl -Ls https://raw.githubusercontent.com/alireza0/x-ui/master/install.sh -o install.sh")
                await self.ssh.execute(f"chmod +x install.sh && echo -e '{panel_port}\\nadmin\\n{panel_password}' | sudo ./install.sh")
            
            # Шаг 5: Сброс пароля на случай если установился дефолтный
            await self.ssh.execute(f"sudo x-ui resetpassword")
            
            # Шаг 6: Открытие портов
            await self.ssh.execute(f"sudo ufw allow {panel_port}/tcp")
            await self.ssh.execute("sudo ufw allow 443/tcp")
            await self.ssh.execute("sudo ufw allow 2096/tcp")
            await self.ssh.execute("sudo ufw --force enable")
            
            # Шаг 7: Получение IP сервера
            ip_output, _ = await self.ssh.execute("curl -s ifconfig.me")
            server_ip = ip_output.strip()
            
            # Шаг 8: Генерация пути панели
            panel_path = '/' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
            
            # Шаг 9: Настройка Reality через API x-ui (автоматически)
            await self.setup_reality(server_ip, panel_port, panel_path, panel_password)
            
            return {
                "success": True,
                "panel_url": f"http://{server_ip}:{panel_port}{panel_path}",
                "username": "admin",
                "password": panel_password,
                "server_ip": server_ip,
                "panel_port": panel_port
            }
            
        except Exception as e:
            logger.error(f"Installation error: {e}")
            return {"success": False, "error": str(e)}
    
    async def setup_reality(self, server_ip, panel_port, panel_path, password):
        """Настройка Reality через веб-панель x-ui"""
        try:
            # Ждём запуска панели
            await asyncio.sleep(10)
            
            # Создаём Reality конфигурацию
            setup_commands = [
                # Вход в панель и создание Reality входящего
                f"""curl -s "http://localhost:{panel_port}{panel_path}/login" \
                    -c /tmp/xui_cookie.txt -o /dev/null""",
                f"""curl -s "http://localhost:{panel_port}{panel_path}/login" \
                    -b /tmp/xui_cookie.txt \
                    -d "username=admin&password={password}" -o /dev/null""",
                # Добавление Reality
                f"""curl -s "http://localhost:{panel_port}{panel_path}/inbound/add" \
                    -b /tmp/xui_cookie.txt \
                    -d "remark=Reality&protocol=vless&port=443&network=tcp&security=reality&\
                    serverName=www.google.com&flow=&fingerprint=chrome&publicKey=&shortId=&spx=yass" \
                    -o /dev/null""",
                # Перезапуск xray
                f"""curl -s "http://localhost:{panel_port}{panel_path}/xray/restart" \
                    -b /tmp/xui_cookie.txt -o /dev/null"""
            ]
            
            for cmd in setup_commands:
                await self.ssh.execute(cmd)
                
        except Exception as e:
            logger.error(f"Reality setup error: {e}")
            # Продолжаем даже при ошибке настройки Reality