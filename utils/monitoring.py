import asyncio
import sqlite3
from config import DB_PATH, ADMIN_CHAT_ID
import logging

logger = logging.getLogger(__name__)

async def check_server_ssh(server_id, host, port, username, password=None, key=None):
    from .ssh_client import SSHClient
    ssh = SSHClient(host, port, username, password, key)
    connected = await ssh.connect()
    ssh.close()
    return connected

async def start_monitoring(bot):
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT id, host, port, username, password, ssh_key FROM servers WHERE status='active'")
            servers = cursor.fetchall()
            
            for server in servers:
                server_id, host, port, username, password, key = server
                is_up = await check_server_ssh(server_id, host, port, username, password, key)
                
                if not is_up:
                    cursor.execute("UPDATE servers SET status='down' WHERE id=?", (server_id,))
                    await bot.send_message(
                        ADMIN_CHAT_ID,
                        f"⚠️ Сервер {host} недоступен по SSH!\nID: {server_id}"
                    )
                else:
                    cursor.execute("UPDATE servers SET status='active' WHERE id=?", (server_id,))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка мониторинга: {e}")
        
        await asyncio.sleep(300)  # Проверка каждые 5 минут