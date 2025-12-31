import re
import asyncio
from utils.ssh_client import SSHClient
from config import ADMIN_CHAT_ID

async def get_server_info(ssh_client: SSHClient):
    """Получить характеристики сервера"""
    try:
        client = await ssh_client.connect()
        
        # RAM
        ram_log, _ = await ssh_client.execute_command(client, "free -h | awk '/^Mem:/ {print $2}'")
        ram = ram_log.strip() or "Не определена"
        
        # CPU
        cpu_log, _ = await ssh_client.execute_command(client, "lscpu | grep 'Model name' | cut -d':' -f2 | xargs")
        cpu = cpu_log.strip() or "Не определен"
        
        # Disk
        disk_log, _ = await ssh_client.execute_command(client, "df -h / | awk 'NR==2 {print $2}'")
        disk = disk_log.strip() or "Не определено"
        
        # OS
        os_log, _ = await ssh_client.execute_command(client, "cat /etc/os-release | grep 'PRETTY_NAME' | cut -d'=' -f2 | tr -d '\"'")
        os_info = os_log.strip() or "Не определена"
        
        # Uptime
        uptime_log, _ = await ssh_client.execute_command(client, "uptime -p")
        uptime = uptime_log.strip() or "Не определен"
        
        client.close()
        
        return {
            'ram': ram,
            'cpu': cpu,
            'disk': disk,
            'os': os_info,
            'uptime': uptime,
            'success': True
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def install_xui(ssh_client: SSHClient, bot):
    """Установка x-ui на сервер"""
    log_messages = []
    
    try:
        client = await ssh_client.connect()
        log_messages.append("✅ SSH подключение установлено")
        
        # 1. Обновление
        log, code = await ssh_client.execute_command(client, "apt update && apt upgrade -y")
        log_messages.append("📦 Обновление пакетов...")
        
        # 2. Установка утилит
        log, code = await ssh_client.execute_command(client, "apt install curl wget git ufw expect -y")
        log_messages.append("📦 Установка утилит...")
        
        # 3. Установка x-ui с автоматическим ответом
        install_script = """
        expect -c '
        spawn bash <(curl -Ls https://raw.githubusercontent.com/alireza0/x-ui/master/install.sh)
        expect "Please enter the panel port:" { send "54321\\r" }
        expect "Please enter the panel username:" { send "admin\\r" }
        expect "Please enter the panel password:" { send "admin12345\\r" }
        expect eof
        '
        """
        log, code = await ssh_client.execute_command(client, install_script)
        log_messages.append("🚀 Установка x-ui...")
        
        # 4. Открытие портов
        ports_cmd = "ufw allow 54321/tcp && ufw allow 443/tcp && ufw allow 2096/tcp && ufw --force enable"
        log, code = await ssh_client.execute_command(client, ports_cmd)
        log_messages.append("🔓 Открытие портов...")
        
        # 5. Получение пути панели
        log, code = await ssh_client.execute_command(client, "cat /etc/x-ui/x-ui.db 2>/dev/null | grep -o '\"path\":\"[^\"]*' | cut -d'\"' -f4 || echo 'admin'")
        panel_path = log.strip().split('\n')[-1] if log.strip() else "admin"
        
        # 6. Формирование ссылки
        panel_url = f"http://{ssh_client.host}:54321/{panel_path}"
        log_messages.append(f"🔗 Панель: {panel_url}")
        
        client.close()
        return True, panel_url, "\n".join(log_messages[:10])  # Первые 10 строк логов
        
    except Exception as e:
        log_messages.append(f"❌ Ошибка: {str(e)}")
        return False, None, "\n".join(log_messages)