import re
import asyncio
from utils.ssh_client import SSHClient

async def get_server_info(ssh_client: SSHClient):
    """Получить характеристики сервера"""
    try:
        client = await ssh_client.connect()
        if not client:
            return {'success': False, 'error': 'SSH connection failed'}
        
        # RAM
        ram_out, _ = await ssh_client.execute_command(client, "free -h | awk '/^Mem:/ {print $2}'")
        ram = ram_out.strip() if ram_out.strip() else "Не определена"
        
        # CPU
        cpu_out, _ = await ssh_client.execute_command(client, "lscpu | grep 'Model name' | cut -d':' -f2 | xargs")
        cpu = cpu_out.strip() if cpu_out.strip() else "Не определен"
        
        # Disk
        disk_out, _ = await ssh_client.execute_command(client, "df -h / | awk 'NR==2 {print $2}'")
        disk = disk_out.strip() if disk_out.strip() else "Не определено"
        
        # OS
        os_out, _ = await ssh_client.execute_command(client, "cat /etc/os-release | grep 'PRETTY_NAME' | cut -d'=' -f2 | tr -d '\"' 2>/dev/null || echo 'Unknown'")
        os_info = os_out.strip()
        
        # Uptime
        uptime_out, _ = await ssh_client.execute_command(client, "uptime -p 2>/dev/null || echo 'Не определен'")
        uptime = uptime_out.strip()
        
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

async def install_xui(ssh_client: SSHClient, bot=None):
    """Установка x-ui на сервер"""
    log_messages = []
    
    try:
        client = await ssh_client.connect()
        if not client:
            return False, None, "❌ Не удалось подключиться по SSH"
        
        log_messages.append("✅ SSH подключение установлено")
        
        # 1. Обновление
        await ssh_client.execute_command(client, "apt update && apt upgrade -y")
        log_messages.append("📦 Обновление пакетов...")
        
        await ssh_client.execute_command(client, "apt install curl wget git ufw expect -y")
        log_messages.append("📦 Установка утилит...")
        
        # 2. Установка x-ui с expect
        install_script = '''/usr/bin/expect -c '
set timeout 300
spawn bash <(curl -Ls https://raw.githubusercontent.com/alireza0/x-ui/master/install.sh)
expect "panel port:" { send "54321\\r" }
expect "panel username:" { send "admin\\r" }
expect "panel password:" { send "admin12345\\r" }
expect eof
' '''
        
        output, code = await ssh_client.execute_command(client, install_script)
        log_messages.append("🚀 Установка x-ui...")
        
        # 3. Открытие портов
        await ssh_client.execute_command(client, "ufw allow 54321/tcp")
        await ssh_client.execute_command(client, "ufw allow 443/tcp")
        await ssh_client.execute_command(client, "ufw allow 2096/tcp")
        await ssh_client.execute_command(client, "ufw --force enable")
        log_messages.append("🔓 Открытие портов...")
        
        # 4. Проверяем установку
        await ssh_client.execute_command(client, "sleep 5")
        status_out, _ = await ssh_client.execute_command(client, "systemctl is-active x-ui 2>/dev/null || echo 'inactive'")
        
        if "active" not in status_out:
            # Пробуем запустить
            await ssh_client.execute_command(client, "systemctl start x-ui 2>/dev/null || true")
            await ssh_client.execute_command(client, "sleep 3")
            status_out, _ = await ssh_client.execute_command(client, "systemctl is-active x-ui 2>/dev/null || echo 'inactive'")
        
        if "active" in status_out:
            # Получаем путь панели
            path_out, _ = await ssh_client.execute_command(client, "sqlite3 /etc/x-ui/x-ui.db 'SELECT path FROM settings LIMIT 1' 2>/dev/null || echo 'admin'")
            panel_path = path_out.strip() if path_out.strip() else "admin"
            
            panel_url = f"http://{ssh_client.host}:54321/{panel_path}"
            log_messages.append(f"✅ X-UI запущен")
            log_messages.append(f"🔗 Панель: {panel_url}")
            
            client.close()
            return True, panel_url, "\n".join(log_messages)
        else:
            # Пробуем получить путь альтернативным методом
            path_out, _ = await ssh_client.execute_command(client, "grep -o '\"path\":\"[^\"]*' /etc/x-ui/x-ui.db 2>/dev/null | cut -d'\"' -f4 | head -1 || echo 'admin'")
            panel_path = path_out.strip() if path_out.strip() else "admin"
            panel_url = f"http://{ssh_client.host}:54321/{panel_path}"
            
            log_messages.append(f"⚠️ X-UI возможно установлен, но не запущен")
            log_messages.append(f"🔗 Панель: {panel_url}")
            log_messages.append(f"👤 Логин: admin")
            log_messages.append(f"🔑 Пароль: admin12345")
            log_messages.append(f"🔄 Запустите вручную: systemctl start x-ui")
            
            client.close()
            return True, panel_url, "\n".join(log_messages)
            
    except Exception as e:
        log_messages.append(f"❌ Ошибка: {str(e)}")
        if 'client' in locals():
            client.close()
        return False, None, "\n".join(log_messages)