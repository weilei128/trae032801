import paramiko
import os
from typing import Optional, Tuple


class SSHClient:
    def __init__(self, host: str, port: int, username: str, key_file: Optional[str] = None, password: Optional[str] = None):
        self.host = host
        self.port = port
        self.username = username
        self.key_file = key_file
        self.password = password
        self.client: Optional[paramiko.SSHClient] = None

    def connect(self) -> bool:
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.key_file:
                key = paramiko.RSAKey.from_private_key_file(self.key_file)
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    pkey=key,
                    timeout=10
                )
            else:
                default_key_paths = [
                    os.path.expanduser('~/.ssh/id_rsa'),
                    os.path.expanduser('~/.ssh/id_ed25519'),
                ]
                
                connected = False
                for key_path in default_key_paths:
                    if os.path.exists(key_path):
                        try:
                            key = paramiko.RSAKey.from_private_key_file(key_path)
                            self.client.connect(
                                hostname=self.host,
                                port=self.port,
                                username=self.username,
                                pkey=key,
                                timeout=10
                            )
                            connected = True
                            break
                        except Exception:
                            continue
                
                if not connected:
                    self.client.connect(
                        hostname=self.host,
                        port=self.port,
                        username=self.username,
                        password=self.password,
                        timeout=10
                    )
            
            return True
        except Exception as e:
            print(f"SSH连接失败 [{self.host}:{self.port}]: {e}")
            return False

    def disconnect(self):
        if self.client:
            self.client.close()
            self.client = None

    def execute_command(self, command: str) -> Tuple[int, str, str]:
        if not self.client:
            return -1, "", "SSH未连接"
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=30)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode('utf-8', errors='ignore')
            error = stderr.read().decode('utf-8', errors='ignore')
            return exit_code, output, error
        except Exception as e:
            return -1, "", str(e)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
