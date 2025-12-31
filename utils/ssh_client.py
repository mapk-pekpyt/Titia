# utils/ssh_client.py
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
        self._client = None
        
    async def connect(self):
        """Подключение по SSH"""
        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.key:
                # Используем ключ
                key_file = StringIO(self.key)
                
                # Пробуем разные форматы ключей
                try:
                    pkey = paramiko.RSAKey.from_private_key(key_file)
                except:
                    key_file.seek(0)
                    try:
                        pkey = paramiko.Ed25519Key.from_private_key(key_file)
                    except:
                        key_file.seek(0)
                        pkey = paramiko.ECDSAKey.from_private_key(key_file)
                
                self._client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    pkey=pkey,
                    timeout=30,
                    banner_timeout=30
                )
            else:
                # Подключаемся с паролем
                self._client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=30,
                    banner_timeout=30
                )
            
            self.logger.info(f"✅ SSH подключение к {self.host}:{self.port}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ SSH ошибка: {str(e)}")
            return False
    
    async def execute(self, command, timeout=60):
        """Выполнение команды - возвращает (output, error)"""
        try:
            if not self._client:
                await self.connect()
            
            # Выполняем команду
            stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
            
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
        if self._client:
            self._client.close()
            self._client = None