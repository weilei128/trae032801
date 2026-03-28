from typing import Dict, Any, List
from ssh_client import SSHClient
import re


class SystemCollector:
    def __init__(self, ssh_client: SSHClient):
        self.ssh = ssh_client

    def get_cpu_info(self) -> Dict[str, Any]:
        result = {
            'load_1min': 0.0,
            'load_5min': 0.0,
            'load_15min': 0.0,
            'cpu_usage': 0.0,
            'cpu_cores': 0
        }
        
        exit_code, output, _ = self.ssh.execute_command("cat /proc/loadavg")
        if exit_code == 0 and output:
            parts = output.strip().split()
            if len(parts) >= 3:
                result['load_1min'] = float(parts[0])
                result['load_5min'] = float(parts[1])
                result['load_15min'] = float(parts[2])
        
        exit_code, output, _ = self.ssh.execute_command("nproc")
        if exit_code == 0 and output:
            result['cpu_cores'] = int(output.strip())
        
        exit_code, output, _ = self.ssh.execute_command(
            "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"
        )
        if exit_code == 0 and output:
            try:
                result['cpu_usage'] = float(output.strip())
            except ValueError:
                pass
        
        return result

    def get_memory_info(self) -> Dict[str, Any]:
        result = {
            'total_mb': 0,
            'used_mb': 0,
            'free_mb': 0,
            'available_mb': 0,
            'usage_percent': 0.0
        }
        
        exit_code, output, _ = self.ssh.execute_command("free -m")
        if exit_code == 0 and output:
            lines = output.strip().split('\n')
            for line in lines:
                if line.startswith('Mem:'):
                    parts = line.split()
                    if len(parts) >= 7:
                        result['total_mb'] = int(parts[1])
                        result['used_mb'] = int(parts[2])
                        result['free_mb'] = int(parts[3])
                        result['available_mb'] = int(parts[6])
                        if result['total_mb'] > 0:
                            result['usage_percent'] = round(
                                (result['used_mb'] / result['total_mb']) * 100, 2
                            )
                    break
        
        return result

    def get_disk_info(self) -> List[Dict[str, Any]]:
        result = []
        
        exit_code, output, _ = self.ssh.execute_command("df -h")
        if exit_code == 0 and output:
            lines = output.strip().split('\n')
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 6:
                    filesystem = parts[0]
                    if filesystem.startswith('/dev/') or filesystem.startswith('tmpfs'):
                        size = parts[1]
                        used = parts[2]
                        avail = parts[3]
                        use_percent = parts[4].replace('%', '')
                        mount = parts[5]
                        
                        result.append({
                            'filesystem': filesystem,
                            'size': size,
                            'used': used,
                            'available': avail,
                            'usage_percent': float(use_percent) if use_percent.isdigit() else 0,
                            'mount_point': mount
                        })
        
        return result

    def get_system_info(self) -> Dict[str, Any]:
        result = {
            'hostname': '',
            'os': '',
            'kernel': '',
            'uptime': ''
        }
        
        exit_code, output, _ = self.ssh.execute_command("hostname")
        if exit_code == 0:
            result['hostname'] = output.strip()
        
        exit_code, output, _ = self.ssh.execute_command("cat /etc/os-release | grep PRETTY_NAME | cut -d'\"' -f2")
        if exit_code == 0:
            result['os'] = output.strip()
        
        exit_code, output, _ = self.ssh.execute_command("uname -r")
        if exit_code == 0:
            result['kernel'] = output.strip()
        
        exit_code, output, _ = self.ssh.execute_command("uptime -p")
        if exit_code == 0:
            result['uptime'] = output.strip().replace('up ', '')
        
        return result
