from typing import Dict, Any, List
from ssh_client import SSHClient
import config


class ServiceCollector:
    def __init__(self, ssh_client: SSHClient):
        self.ssh = ssh_client

    def check_tcp_ports(self, ports: List[int] = None) -> List[Dict[str, Any]]:
        if ports is None:
            ports = config.CHECK_PORTS
        
        result = []
        
        exit_code, output, _ = self.ssh.execute_command("ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null")
        
        listening_ports = set()
        if exit_code == 0 and output:
            for line in output.strip().split('\n'):
                if 'LISTEN' in line:
                    parts = line.split()
                    for part in parts:
                        if ':' in part:
                            try:
                                port = int(part.split(':')[-1])
                                listening_ports.add(port)
                            except ValueError:
                                continue
        
        for port in ports:
            result.append({
                'port': port,
                'status': 'LISTENING' if port in listening_ports else 'NOT LISTENING',
                'is_listening': port in listening_ports
            })
        
        return result

    def check_processes(self, process_names: List[str] = None) -> List[Dict[str, Any]]:
        if process_names is None:
            process_names = config.CHECK_PROCESSES
        
        result = []
        
        exit_code, output, _ = self.ssh.execute_command("ps aux")
        
        running_processes = {}
        if exit_code == 0 and output:
            for line in output.strip().split('\n')[1:]:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    cmd = parts[10].lower()
                    for proc_name in process_names:
                        if proc_name.lower() in cmd:
                            if proc_name not in running_processes:
                                running_processes[proc_name] = {
                                    'count': 0,
                                    'pids': []
                                }
                            running_processes[proc_name]['count'] += 1
                            running_processes[proc_name]['pids'].append(parts[1])
        
        for proc_name in process_names:
            if proc_name in running_processes:
                result.append({
                    'name': proc_name,
                    'status': 'RUNNING',
                    'count': running_processes[proc_name]['count'],
                    'pids': ', '.join(running_processes[proc_name]['pids'][:5]),
                    'is_running': True
                })
            else:
                result.append({
                    'name': proc_name,
                    'status': 'NOT RUNNING',
                    'count': 0,
                    'pids': '',
                    'is_running': False
                })
        
        return result

    def get_all_listening_ports(self) -> List[Dict[str, Any]]:
        result = []
        
        exit_code, output, _ = self.ssh.execute_command("ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null")
        
        if exit_code == 0 and output:
            for line in output.strip().split('\n'):
                if 'LISTEN' in line:
                    parts = line.split()
                    local_addr = ''
                    port = 0
                    program = ''
                    
                    for part in parts:
                        if ':' in part and local_addr == '':
                            local_addr = part
                            try:
                                port = int(part.split(':')[-1])
                            except ValueError:
                                pass
                    
                    if 'users:' in line:
                        try:
                            program = line.split('users:')[1].strip().split('"')[1]
                        except (IndexError, ValueError):
                            pass
                    
                    if port > 0:
                        result.append({
                            'port': port,
                            'address': local_addr,
                            'program': program
                        })
        
        return sorted(result, key=lambda x: x['port'])
