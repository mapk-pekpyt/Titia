import asyncio
import re
import random
import string
from .ssh_client import SSHClient
import logging

logger = logging.getLogger(__name__)

class VPNInstaller:
    def __init__(self, ssh_client):
        self.ssh = ssh_client
    
    async def check_prerequisites(self):
        commands = [
            "uname -a",
            "which docker",
            "which curl",
            "ufw status"
        ]
        results = {}
        for cmd in commands:
            output, error = await self.ssh.execute(cmd)
            results[cmd] = output if output else error
        return results
    
    async def install_xui(self):
        # Генерация случайных данных
        panel_port = random.randint(10000, 60000)
        panel_path = '/' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        panel_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        
        install_script = f"""
        bash <(curl -Ls https://raw.githubusercontent.com/alireza0/x-ui/master/install.sh) <<EOF
        {panel_port}
        admin
        {panel_password}
        EOF
        """
        
        output, error = await self.ssh.execute(install_script)
        
        if "installation finished" in output.lower():
            # Получаем IP сервера
            ip_output, _ = await self.ssh.execute("curl -s ifconfig.me")
            server_ip = ip_output.strip()
            
            panel_url = f"http://{server_ip}:{panel_port}{panel_path}"
            
            return {
                "success": True,
                "panel_url": panel_url,
                "username": "admin",
                "password": panel_password,
                "server_ip": server_ip
            }
        else:
            return {"success": False, "error": error}