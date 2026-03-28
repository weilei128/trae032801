"""
SSH服务器信息采集模块
用于通过SSH协议远程连接服务器并采集各项指标
"""

import paramiko
import json
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ServerMetrics:
    """服务器指标数据类"""
    timestamp: str
    server_name: str
    server_ip: str
    
    # CPU信息
    cpu_load_1min: float
    cpu_load_5min: float
    cpu_load_15min: float
    cpu_usage_percent: float
    
    # 内存信息
    memory_total_mb: float
    memory_used_mb: float
    memory_free_mb: float
    memory_usage_percent: float
    
    # 磁盘信息
    disk_total_gb: float
    disk_used_gb: float
    disk_free_gb: float
    disk_usage_percent: float
    
    # TCP端口监听状态
    tcp_listening_ports: str
    
    # 系统进程信息
    total_processes: int
    running_processes: int
    
    # Docker信息
    docker_installed: bool
    docker_version: str
    docker_images_count: int
    docker_containers_total: int
    docker_containers_running: int
    docker_containers_stopped: int
    
    # 目标目录信息
    target_dir_exists: bool
    target_dir_size_mb: float
    
    # 连接状态
    connection_status: str
    error_message: str = ""


class SSHCollector:
    """SSH服务器信息采集器"""
    
    def __init__(self, server_config: Dict[str, Any]):
        self.config = server_config
        self.ssh_client = None
        
    def connect(self) -> bool:
        """建立SSH连接"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.config.get('auth_type') == 'key':
                # 使用SSH密钥认证
                private_key = paramiko.RSAKey.from_private_key_file(
                    self.config['key_path']
                )
                self.ssh_client.connect(
                    hostname=self.config['ip'],
                    port=self.config.get('port', 22),
                    username=self.config['username'],
                    pkey=private_key,
                    timeout=30
                )
            else:
                # 使用密码认证
                self.ssh_client.connect(
                    hostname=self.config['ip'],
                    port=self.config.get('port', 22),
                    username=self.config['username'],
                    password=self.config.get('password'),
                    timeout=30
                )
            return True
        except Exception as e:
            print(f"连接服务器 {self.config['ip']} 失败: {str(e)}")
            return False
    
    def disconnect(self):
        """断开SSH连接"""
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
    
    def execute_command(self, command: str) -> tuple:
        """执行远程命令"""
        if not self.ssh_client:
            return "", "未连接"
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            return output, error
        except Exception as e:
            return "", str(e)
    
    def collect_cpu_info(self) -> Dict[str, float]:
        """采集CPU信息"""
        # 获取负载平均值
        output, _ = self.execute_command("cat /proc/loadavg")
        load_info = output.split()
        
        # 获取CPU使用率
        cpu_output, _ = self.execute_command(
            "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"
        )
        try:
            cpu_usage = float(cpu_output) if cpu_output else 0.0
        except:
            cpu_usage = 0.0
        
        return {
            'load_1min': float(load_info[0]) if len(load_info) > 0 else 0.0,
            'load_5min': float(load_info[1]) if len(load_info) > 1 else 0.0,
            'load_15min': float(load_info[2]) if len(load_info) > 2 else 0.0,
            'usage_percent': cpu_usage
        }
    
    def collect_memory_info(self) -> Dict[str, float]:
        """采集内存信息"""
        output, _ = self.execute_command("free -m | grep 'Mem:'")
        if output:
            parts = output.split()
            if len(parts) >= 4:
                total = float(parts[1])
                used = float(parts[2])
                free = float(parts[3])
                usage_percent = (used / total * 100) if total > 0 else 0.0
                return {
                    'total_mb': total,
                    'used_mb': used,
                    'free_mb': free,
                    'usage_percent': usage_percent
                }
        return {'total_mb': 0, 'used_mb': 0, 'free_mb': 0, 'usage_percent': 0}
    
    def collect_disk_info(self) -> Dict[str, float]:
        """采集磁盘信息"""
        output, _ = self.execute_command("df -h / | tail -1")
        if output:
            parts = output.split()
            if len(parts) >= 6:
                # 解析磁盘使用情况
                total_str = parts[1]
                used_str = parts[2]
                free_str = parts[3]
                usage_str = parts[4].replace('%', '')
                
                # 转换为GB
                total_gb = self._parse_size_to_gb(total_str)
                used_gb = self._parse_size_to_gb(used_str)
                free_gb = self._parse_size_to_gb(free_str)
                
                return {
                    'total_gb': total_gb,
                    'used_gb': used_gb,
                    'free_gb': free_gb,
                    'usage_percent': float(usage_str) if usage_str.isdigit() else 0.0
                }
        return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'usage_percent': 0}
    
    def _parse_size_to_gb(self, size_str: str) -> float:
        """将大小字符串转换为GB"""
        size_str = size_str.upper()
        try:
            if size_str.endswith('G'):
                return float(size_str[:-1])
            elif size_str.endswith('T'):
                return float(size_str[:-1]) * 1024
            elif size_str.endswith('M'):
                return float(size_str[:-1]) / 1024
            elif size_str.endswith('K'):
                return float(size_str[:-1]) / (1024 * 1024)
            else:
                return float(size_str) / (1024 * 1024 * 1024)
        except:
            return 0.0
    
    def collect_tcp_ports(self) -> str:
        """采集TCP端口监听状态"""
        output, _ = self.execute_command(
            "netstat -tlnp 2>/dev/null | grep LISTEN | awk '{print $4}' | cut -d':' -f2 | sort -n | uniq | head -20"
        )
        if not output:
            # 尝试使用ss命令
            output, _ = self.execute_command(
                "ss -tlnp 2>/dev/null | grep LISTEN | awk '{print $4}' | cut -d':' -f2 | sort -n | uniq | head -20"
            )
        return output.replace('\n', ', ') if output else "N/A"
    
    def collect_process_info(self) -> Dict[str, int]:
        """采集系统进程信息"""
        total_output, _ = self.execute_command("ps aux | wc -l")
        running_output, _ = self.execute_command("ps aux | grep 'R' | wc -l")
        
        return {
            'total': int(total_output) - 1 if total_output.isdigit() else 0,
            'running': int(running_output) if running_output.isdigit() else 0
        }
    
    def collect_docker_info(self) -> Dict[str, Any]:
        """采集Docker相关信息"""
        info = {
            'installed': False,
            'version': 'N/A',
            'images_count': 0,
            'containers_total': 0,
            'containers_running': 0,
            'containers_stopped': 0
        }
        
        # 检查Docker是否安装
        version_output, _ = self.execute_command("docker --version 2>/dev/null")
        if version_output and 'Docker version' in version_output:
            info['installed'] = True
            info['version'] = version_output.split(',')[0]
            
            # 获取镜像数量
            images_output, _ = self.execute_command("docker images -q | wc -l")
            info['images_count'] = int(images_output) if images_output.isdigit() else 0
            
            # 获取容器信息
            containers_output, _ = self.execute_command("docker ps -aq | wc -l")
            info['containers_total'] = int(containers_output) if containers_output.isdigit() else 0
            
            running_output, _ = self.execute_command("docker ps -q | wc -l")
            info['containers_running'] = int(running_output) if running_output.isdigit() else 0
            
            info['containers_stopped'] = info['containers_total'] - info['containers_running']
        
        return info
    
    def collect_target_dir_info(self, target_dir: str) -> Dict[str, Any]:
        """采集目标目录信息"""
        # 检查目录是否存在
        check_output, _ = self.execute_command(f"test -d {target_dir} && echo 'exists' || echo 'not exists'")
        exists = check_output == 'exists'
        
        size_mb = 0.0
        if exists:
            size_output, _ = self.execute_command(f"du -sm {target_dir} 2>/dev/null | cut -f1")
            try:
                size_mb = float(size_output)
            except:
                size_mb = 0.0
        
        return {
            'exists': exists,
            'size_mb': size_mb
        }
    
    def collect_all_metrics(self) -> ServerMetrics:
        """采集所有指标"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if not self.connect():
            return ServerMetrics(
                timestamp=timestamp,
                server_name=self.config['name'],
                server_ip=self.config['ip'],
                cpu_load_1min=0, cpu_load_5min=0, cpu_load_15min=0, cpu_usage_percent=0,
                memory_total_mb=0, memory_used_mb=0, memory_free_mb=0, memory_usage_percent=0,
                disk_total_gb=0, disk_used_gb=0, disk_free_gb=0, disk_usage_percent=0,
                tcp_listening_ports="N/A",
                total_processes=0, running_processes=0,
                docker_installed=False, docker_version="N/A",
                docker_images_count=0, docker_containers_total=0,
                docker_containers_running=0, docker_containers_stopped=0,
                target_dir_exists=False, target_dir_size_mb=0,
                connection_status="Failed",
                error_message="无法连接到服务器"
            )
        
        try:
            # 采集各项信息
            cpu_info = self.collect_cpu_info()
            memory_info = self.collect_memory_info()
            disk_info = self.collect_disk_info()
            tcp_ports = self.collect_tcp_ports()
            process_info = self.collect_process_info()
            docker_info = self.collect_docker_info()
            target_dir_info = self.collect_target_dir_info(self.config.get('target_dir', '/opt/apps/memo-app'))
            
            metrics = ServerMetrics(
                timestamp=timestamp,
                server_name=self.config['name'],
                server_ip=self.config['ip'],
                cpu_load_1min=cpu_info['load_1min'],
                cpu_load_5min=cpu_info['load_5min'],
                cpu_load_15min=cpu_info['load_15min'],
                cpu_usage_percent=cpu_info['usage_percent'],
                memory_total_mb=memory_info['total_mb'],
                memory_used_mb=memory_info['used_mb'],
                memory_free_mb=memory_info['free_mb'],
                memory_usage_percent=memory_info['usage_percent'],
                disk_total_gb=disk_info['total_gb'],
                disk_used_gb=disk_info['used_gb'],
                disk_free_gb=disk_info['free_gb'],
                disk_usage_percent=disk_info['usage_percent'],
                tcp_listening_ports=tcp_ports,
                total_processes=process_info['total'],
                running_processes=process_info['running'],
                docker_installed=docker_info['installed'],
                docker_version=docker_info['version'],
                docker_images_count=docker_info['images_count'],
                docker_containers_total=docker_info['containers_total'],
                docker_containers_running=docker_info['containers_running'],
                docker_containers_stopped=docker_info['containers_stopped'],
                target_dir_exists=target_dir_info['exists'],
                target_dir_size_mb=target_dir_info['size_mb'],
                connection_status="Success",
                error_message=""
            )
            
        except Exception as e:
            metrics = ServerMetrics(
                timestamp=timestamp,
                server_name=self.config['name'],
                server_ip=self.config['ip'],
                cpu_load_1min=0, cpu_load_5min=0, cpu_load_15min=0, cpu_usage_percent=0,
                memory_total_mb=0, memory_used_mb=0, memory_free_mb=0, memory_usage_percent=0,
                disk_total_gb=0, disk_used_gb=0, disk_free_gb=0, disk_usage_percent=0,
                tcp_listening_ports="N/A",
                total_processes=0, running_processes=0,
                docker_installed=False, docker_version="N/A",
                docker_images_count=0, docker_containers_total=0,
                docker_containers_running=0, docker_containers_stopped=0,
                target_dir_exists=False, target_dir_size_mb=0,
                connection_status="Error",
                error_message=str(e)
            )
        finally:
            self.disconnect()
        
        return metrics
