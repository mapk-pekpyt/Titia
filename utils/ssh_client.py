import paramiko
import asyncio
from io import StringIO
from config import ADMIN_CHAT_ID

class SSHClient:
    def __init__(self, host, port, username, password=None, key=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key = key
        
    async def connect(self):
        """Асинхронное подключение по SSH"""
        loop = asyncio.get_event_loop()
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            if self.key:
                key_file = StringIO(self.key)
                pkey = paramiko.RSAKey.from_private_key(key_file)
                await loop.run_in_executor(None, client.connect, 
                                         self.host, self.port, 
                                         self.username, pkey)
            else:
                await loop.run_in_executor(None, client.connect,
                                         self.host, self.port,
                                         self.username, self.password)
            return client
        except Exception as e:
            raise Exception(f"SSH подключение не удалось: {str(e)}")
    
    async def execute_command(self, client, command, timeout=30):
        """Выполнение команды с логированием"""
        try:
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            result = f"Команда: {command}\n"
            result += f"Код выхода: {exit_status}\n"
            if output:
                result += f"Вывод:\n{output[:1000]}\n"
            if error:
                result += f"Ошибки:\n{error[:1000]}\n"
                
            return result, exit_status
        except Exception as e:
            raise Exception(f"Ошибка выполнения команды: {str(e)}")