import re
import asyncio
from utils.ssh_client import SSHClient

async def get_server_info(ssh_client: SSHClient):
    """Получить характеристики сервера"""
    try:
        if not await ssh_client.connect():
            return {'success': False, 'error': 'SSH connection failed'}
        
        # RAM
        ram_out, _ = await ssh_client.execute("free -h | awk '/^Mem:/ {print $2}'")
        ram = ram_out.strip() or "Не определена"
        
        # CPU
        cpu_out, _ = await ssh_client.execute("lscpu | grep 'Model name' | cut -d':' -f2 | xargs")
        cpu = cpu_out.strip() or "Не определен"
        
        # Disk
        disk_out, _ = await ssh_client.execute("df -h / | awk 'NR==2 {print $2}'")
        disk = disk_out.strip() or "Не определено"
        
        # OS
        os_out, _ = await ssh_client.execute("cat /etc/os-release | grep 'PRETTY_NAME' | cut -d'=' -f2 | tr -d '\"'")
        os_info = os_out.strip() or "Не определена"
        
        # Uptime
        uptime_out, _ = await ssh_client.execute("uptime -p")
        uptime = uptime_out.strip() or "Не определен"
        
        ssh_client.close()
        
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
        if not await ssh_client.connect():
            return False, None, "❌ Не удалось подключиться по SSH"
        
        log_messages.append("✅ SSH подключение установлено")
        
        # 1. Обновление и установка expect
        await ssh_client.execute("apt update && apt upgrade -y")
        log_messages.append("📦 Обновление пакетов...")
        
        await ssh_client.execute("apt install curl wget git ufw expect -y")
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
        
        output, error = await ssh_client.execute(install_script)
        log_messages.append("🚀 Установка x-ui...")
        
        # 3. Открытие портов
        await ssh_client.execute("ufw allow 54321/tcp")
        await ssh_client.execute("ufw allow 443/tcp")
        await ssh_client.execute("ufw allow 2096/tcp")
        await ssh_client.execute("ufw --force enable")
        log_messages.append("🔓 Открытие портов...")
        
        # 4. Ждём запуска и проверяем
        await ssh_client.execute("sleep 10")
        status_out, _ = await ssh_client.execute("systemctl is-active x-ui")
        
        if "active" not in status_out:
            # Пробуем запустить вручную
            await ssh_client.execute("systemctl start x-ui")
            await ssh_client.execute("sleep 3")
            status_out, _ = await ssh_client.execute("systemctl is-active x-ui")
        
        if "active" in status_out:
            # Получаем путь панели из БД
            path_out, _ = await ssh_client.execute("sqlite3 /etc/x-ui/x-ui.db 'SELECT path FROM settings LIMIT 1' 2>/dev/null || echo 'admin'")
            panel_path = path_out.strip() if path_out.strip() else "admin"
            
            panel_url = f"http://{ssh_client.host}:54321/{panel_path}"
            log_messages.append(f"✅ X-UI запущен")
            log_messages.append(f"🔗 Панель: {panel_url}")
            log_messages.append(f"👤 Логин: admin")
            log_messages.append(f"🔑 Пароль: admin12345")
            
            ssh_client.close()
            return True, panel_url, "\n".join(log_messages)
        else:
            log_messages.append("❌ X-UI не запустился после установки")
            ssh_client.close()
            return False, None, "\n".join(log_messages)
            
    except Exception as e:
        log_messages.append(f"❌ Критическая ошибка: {str(e)}")
        if hasattr(ssh_client, 'close'):
            ssh_client.close()
        return False, None, "\n".join(log_messages)