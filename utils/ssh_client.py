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
        """Асинхронное подключение по SSH"""
        loop = asyncio.get_event_loop()
        
        def sync_connect():
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            try:
                if self.key:
                    # Используем ключ
                    key_file = StringIO(self.key)
                    
                    # Пробуем разные форматы ключей
                    try:
                        pkey = paramiko.RSAKey.from_private_key(key_file)
                    except paramiko.ssh_exception.SSHException:
                        key_file.seek(0)
                        try:
                            pkey = paramiko.Ed25519Key.from_private_key(key_file)
                        except:
                            key_file.seek(0)
                            try:
                                pkey = paramiko.ECDSAKey.from_private_key(key_file)
                            except:
                                # Пробуем как DSA ключ
                                key_file.seek(0)
                                pkey = paramiko.DSSKey.from_private_key(key_file)
                    
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
                
            except Exception as e:
                self.logger.error(f"SSH ошибка: {str(e)}")
                raise e
        
        try:
            self._client = await loop.run_in_executor(None, sync_connect)
            self.logger.info(f"✅ SSH подключение к {self.host}:{self.port}")
            return self._client
        except Exception as e:
            raise Exception(f"SSH подключение не удалось: {str(e)}")
    
    async def execute_command(self, client, command, timeout=30):
        """Выполнение команды (для старого установщика)"""
        def sync_execute():
            try:
                stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
                exit_status = stdout.channel.recv_exit_status()
                output = stdout.read().decode('utf-8', errors='ignore').strip()
                error = stderr.read().decode('utf-8', errors='ignore').strip()
                
                # Форматируем результат как в старом коде
                result = f"Команда: {command}\n"
                result += f"Код выхода: {exit_status}\n"
                if output:
                    result += f"Вывод:\n{output[:1000]}\n"
                if error:
                    result += f"Ошибки:\n{error[:1000]}\n"
                    
                return result, exit_status
            except Exception as e:
                raise Exception(f"Ошибка выполнения команды: {str(e)}")
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_execute)
    
    async def execute(self, command, timeout=30):
        """Упрощенный метод execute (для нового установщика)"""
        if not self._client:
            self._client = await self.connect()
        
        def sync_execute():
            stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode('utf-8', errors='ignore').strip()
            error = stderr.read().decode('utf-8', errors='ignore').strip()
            return output, exit_status
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_execute)
    
    def close(self):
        """Закрыть соединение"""
        if self._client:
            self._client.close()
            self._client = None