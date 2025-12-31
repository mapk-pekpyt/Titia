import paramiko
import asyncio
from io import StringIO
import logging

class SSHClient:
    def __init__(self, host, port, username, password=None, key=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key = key
        self.logger = logging.getLogger(__name__)
        self.client = None
        
    async def connect(self):
        """Подключение по SSH"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.key:
                # Используем ключ
                key_file = StringIO(self.key)
                pkey = paramiko.RSAKey.from_private_key(key_file)
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    pkey=pkey,
                    timeout=30
                )
            else:
                # Подключаемся с паролем
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=30
                )
            
            self.logger.info(f"✅ SSH подключение к {self.host}:{self.port}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ SSH ошибка: {str(e)}")
            return False
    
    async def execute(self, command, timeout=60):
        """Выполнение команды"""
        try:
            if not self.client:
                await self.connect()
            
            # Выполняем команду
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            
            # Ждем завершения
            exit_status = stdout.channel.recv_exit_status()
            
            # Читаем вывод
            output = stdout.read().decode('utf-8', errors='ignore').strip()
            error = stderr.read().decode('utf-8', errors='ignore').strip()
            
            return output, error
            
        except Exception as e:
            self.logger.error(f"Ошибка выполнения команды: {str(e)}")
            return None, str(e)
    
    def close(self):
        """Закрыть соединение"""
        if self.client:
            self.client.close()
            self.client = None