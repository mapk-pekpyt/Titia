import re
from utils.ssh_client import SSHClient
from config import ADMIN_CHAT_ID

async def install_xui(ssh_client: SSHClient, bot):
    """Установка x-ui на сервер"""
    log_messages = []
    
    try:
        # Подключаемся
        client = await ssh_client.connect()
        log_messages.append("✅ SSH подключение установлено")
        
        # 1. Обновление системы
        log, code = await ssh_client.execute_command(client, "apt update && apt upgrade -y")
        log_messages.append("📦 Обновление пакетов...")
        log_messages.append(log[:500])
        
        # 2. Установка необходимых пакетов
        log, code = await ssh_client.execute_command(client, "apt install curl wget git ufw -y")
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
        log_messages.append(log[:1000])
        
        # 4. Открытие портов
        ports_cmd = "ufw allow 54321/tcp && ufw allow 443/tcp && ufw allow 2096/tcp && ufw --force enable"
        log, code = await ssh_client.execute_command(client, ports_cmd)
        log_messages.append("🔓 Открытие портов...")
        
        # 5. Получение пути панели
        log, code = await ssh_client.execute_command(client, "cat /etc/x-ui/x-ui.db | grep -o '\"path\":\"[^\"]*' | cut -d'\"' -f4")
        panel_path = log.split('\n')[-1] if log else "admin"
        
        # 6. Формирование ссылки
        panel_url = f"http://{ssh_client.host}:54321/{panel_path}"
        log_messages.append(f"🔗 Ссылка на панель: {panel_url}")
        log_messages.append(f"👤 Логин: admin")
        log_messages.append(f"🔑 Пароль: admin12345")
        
        client.close()
        return True, panel_url, "\n".join(log_messages)
        
    except Exception as e:
        log_messages.append(f"❌ Ошибка: {str(e)}")
        return False, None, "\n".join(log_messages)