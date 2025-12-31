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
        
    async def connect(self):
        """Асинхронное подключение по SSH"""
        loop = asyncio.get_event_loop()
        
        # Создаем функцию для синхронного выполнения
        def sync_connect():
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.key:
                # Используем ключ
                key_file = StringIO(self.key)
                try:
                    pkey = paramiko.RSAKey.from_private_key(key_file)
                except paramiko.ssh_exception.SSHException:
                    key_file.seek(0)
                    try:
                        pkey = paramiko.Ed25519Key.from_private_key(key_file)
                    except:
                        key_file.seek(0)
                        pkey = paramiko.ECDSAKey.from_private_key(key_file)
                
                # Подключаемся с ключом
                client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    pkey=pkey,
                    timeout=10,
                    banner_timeout=20
                )
            else:
                # Подключаемся с паролем
                client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=10,
                    banner_timeout=20
                )
            
            return client
        
        # Выполняем в executor
        try:
            client = await loop.run_in_executor(None, sync_connect)
            self.logger.info(f"✅ SSH подключение установлено к {self.host}:{self.port}")
            return client
        except Exception as e:
            self.logger.error(f"❌ SSH подключение не удалось: {str(e)}")
            raise Exception(f"SSH подключение не удалось: {str(e)}")
    
    async def execute_command(self, client, command, timeout=30):
        """Выполнение команды"""
        def sync_execute():
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode('utf-8', errors='ignore').strip()
            error = stderr.read().decode('utf-8', errors='ignore').strip()
            return output, exit_status
        
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, sync_execute)
        except Exception as e:
            raise Exception(f"Ошибка выполнения команды: {str(e)}")