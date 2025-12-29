import paramiko
import asyncio
from io import StringIO
import logging

logger = logging.getLogger(__name__)

class SSHClient:
    def __init__(self, host, port, username, password=None, key=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key = key
        self.client = None
    
    async def connect(self):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.key:
                key_file = StringIO(self.key)
                pkey = paramiko.RSAKey.from_private_key(key_file)
                self.client.connect(self.host, self.port, self.username, pkey=pkey, timeout=10)
            else:
                self.client.connect(self.host, self.port, self.username, self.password, timeout=10)
            
            logger.info(f"SSH подключение установлено: {self.host}")
            return True
        except Exception as e:
            logger.error(f"SSH ошибка: {e}")
            return False
    
    async def execute(self, command):
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            return output, error
        except Exception as e:
            logger.error(f"Ошибка выполнения команды: {e}")
            return None, str(e)
    
    def close(self):
        if self.client:
            self.client.close()