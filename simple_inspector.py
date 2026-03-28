#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化版服务器巡检工具 - 使用CSV格式报告
"""

import paramiko
import csv
import time
import os
from datetime import datetime
import sys

# 服务器配置
SERVERS = [
    {
        'ip': '49.235.161.106',
        'port': 22,
        'username': 'root',
        'key_path': None,
        'password': None,
        'target_dir': '/opt/apps/memo-app'
    }
]

INSPECTION_INTERVAL = 10  # 分钟
INSPECTION_DURATION = 30  # 分钟
REPORT_PATH = 'server_inspection_report.csv'
SSH_TIMEOUT = 30

class ServerInspector:
    def __init__(self, ip, port, username, key_path=None, password=None, target_dir=None):
        self.ip = ip
        self.port = port
        self.username = username
        self.key_path = key_path
        self.password = password
        self.target_dir = target_dir
        self.ssh = None
        
    def connect(self):
        """建立SSH连接"""
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            connect_kwargs = {
                'hostname': self.ip,
                'port': self.port,
                'username': self.username,
                'timeout': SSH_TIMEOUT
            }
            
            # 尝试密码认证
            if self.password:
                connect_kwargs['password'] = self.password
                self.ssh.connect(**connect_kwargs)
                return True, "密码认证成功"
            
            # 尝试密钥认证
            key_paths = [
                self.key_path,
                os.path.expanduser('~/.ssh/id_rsa'),
                os.path.expanduser('~/.ssh/id_dsa'),
                'id_rsa'
            ]
            
            for kp in key_paths:
                if kp and os.path.exists(kp):
                    try:
                        private_key = paramiko.RSAKey.from_private_key_file(kp)
                        connect_kwargs['pkey'] = private_key
                        self.ssh.connect(**connect_kwargs)
                        return True, f"密钥认证成功 ({kp})"
                    except Exception as e:
                        continue
            
            # 尝试SSH代理
            try:
                agent = paramiko.Agent()
                agent_keys = agent.get_keys()
                if agent_keys:
                    for key in agent_keys:
                        try:
                            connect_kwargs['pkey'] = key
                            self.ssh.connect(**connect_kwargs)
                            return True, "SSH代理认证成功"
                        except:
                            pass
            except:
                pass
            
            return False, "所有认证方式失败"
            
        except Exception as e:
            return False, f"连接失败: {str(e)}"
    
    def execute_command(self, command):
        """执行远程命令"""
        if not self.ssh:
            return None, "未建立连接"
        try:
            stdin, stdout, stderr = self.ssh.exec_command(command, timeout=SSH_TIMEOUT)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            return output if output else error, None
        except Exception as e:
            return None, str(e)
    
    def get_cpu_usage(self):
        """获取CPU使用率"""
        command = "top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | awk '{print 100 - $1}'"
        output, error = self.execute_command(command)
        if error or not output:
            command = "mpstat 1 1 | awk '/Average:/ {print 100 - $12}'"
            output, error = self.execute_command(command)
            if error or not output:
                return "获取失败"
        try:
            return f"{float(output):.2f}%"
        except:
            return output if output else "获取失败"
    
    def get_memory_usage(self):
        """获取内存使用率"""
        command = "free | grep Mem | awk '{print $3/$2 * 100.0}'"
        output, error = self.execute_command(command)
        if error or not output:
            return "获取失败"
        try:
            return f"{float(output):.2f}%"
        except:
            return output
    
    def get_disk_usage(self):
        """获取磁盘使用率"""
        command = "df -h 2>/dev/null | grep -v 'tmpfs' | grep -v 'udev' | head -5"
        output, error = self.execute_command(command)
        if error:
            return "获取失败"
        lines = output.split('\n')
        result = []
        for line in lines[1:]:  # 跳过表头
            parts = line.split()
            if len(parts) >= 6:
                result.append(f"{parts[5]}:{parts[4]}")
        return '; '.join(result)
    
    def get_tcp_ports(self):
        """获取TCP监听端口"""
        command = "ss -tuln 2>/dev/null | grep LISTEN | awk '{print $5}' | awk -F: '{print $NF}' | sort -n | uniq | head -20"
        output, error = self.execute_command(command)
        if error:
            command = "netstat -tuln 2>/dev/null | grep LISTEN | awk '{print $4}' | awk -F: '{print $NF}' | sort -n | uniq | head -20"
            output, error = self.execute_command(command)
            if error:
                return "获取失败"
        ports = [p for p in output.split('\n') if p and p != 'Address' and p != '*']
        return ', '.join(ports) if ports else "无监听端口"
    
    def get_process_status(self):
        """获取系统进程存活情况"""
        command = "ps aux 2>/dev/null | wc -l"
        output, error = self.execute_command(command)
        if error:
            return "获取失败"
        return f"进程总数: {output}"
    
    def get_docker_info(self):
        """获取Docker相关信息"""
        check_cmd = "which docker || command -v docker 2>/dev/null"
        output, error = self.execute_command(check_cmd)
        if not output or error:
            return "Docker未安装", "0", "0", "0", "N/A"
        
        check_running = "docker info >/dev/null 2>&1 && echo 'running' || echo 'stopped'"
        status, _ = self.execute_command(check_running)
        if 'stopped' in status:
            return "Docker服务未运行", "0", "0", "0", "N/A"
        
        count_cmd = "docker ps -q 2>/dev/null | wc -l"
        count_output, _ = self.execute_command(count_cmd)
        running_containers = count_output.strip() if count_output else "0"
        
        stopped_cmd = "docker ps -aq 2>/dev/null | wc -l"
        stopped_output, _ = self.execute_command(stopped_cmd)
        total_containers = stopped_output.strip() if stopped_output else "0"
        
        images_cmd = "docker images -q 2>/dev/null | wc -l"
        images_output, _ = self.execute_command(images_cmd)
        images_count = images_output.strip() if images_output else "0"
        
        images_list_cmd = "docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | head -5"
        images_list, _ = self.execute_command(images_list_cmd)
        images_list = images_list.replace('\n', ', ') if images_list else "无镜像"
        
        docker_status = f"运行中: {running_containers}, 总容器: {total_containers}, 镜像: {images_count}"
        return docker_status, running_containers, total_containers, images_count, images_list
    
    def get_target_dir_status(self):
        """获取目标目录状态"""
        if not self.target_dir:
            return "未指定"
        
        command = f"ls -la {self.target_dir} 2>&1 | head -1"
        output, error = self.execute_command(command)
        if 'No such file or directory' in output:
            return "目录不存在"
        elif 'Permission denied' in output:
            return "权限不足"
        
        count_cmd = f"find {self.target_dir} -maxdepth 1 -type f 2>/dev/null | wc -l"
        count_output, _ = self.execute_command(count_cmd)
        file_count = count_output.strip() if count_output else "N/A"
        
        size_cmd = f"du -sh {self.target_dir} 2>/dev/null | awk '{{print $1}}'"
        size_output, _ = self.execute_command(size_cmd)
        dir_size = size_output.strip() if size_output else "N/A"
        
        return f"存在, 文件数: {file_count}, 大小: {dir_size}"
    
    def disconnect(self):
        """关闭连接"""
        if self.ssh:
            try:
                self.ssh.close()
            except:
                pass
    
    def inspect(self):
        """执行完整巡检"""
        result = {
            '服务器IP': self.ip,
            '巡检时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '连接状态': '',
            'CPU使用率': '',
            '内存使用率': '',
            '磁盘使用率': '',
            'TCP监听端口': '',
            '进程状态': '',
            'Docker状态': '',
            '运行中容器数': '',
            '总容器数': '',
            '镜像数': '',
            '镜像列表': '',
            '目标目录状态': ''
        }
        
        conn_status, conn_msg = self.connect()
        result['连接状态'] = conn_msg
        
        if conn_status:
            result['CPU使用率'] = self.get_cpu_usage()
            result['内存使用率'] = self.get_memory_usage()
            result['磁盘使用率'] = self.get_disk_usage()
            result['TCP监听端口'] = self.get_tcp_ports()
            result['进程状态'] = self.get_process_status()
            
            docker_status, running, total, images, images_list = self.get_docker_info()
            result['Docker状态'] = docker_status
            result['运行中容器数'] = running
            result['总容器数'] = total
            result['镜像数'] = images
            result['镜像列表'] = images_list
            
            result['目标目录状态'] = self.get_target_dir_status()
            
            self.disconnect()
        
        return result

class ReportGenerator:
    def __init__(self, output_path=REPORT_PATH):
        self.output_path = output_path
        self.fieldnames = [
            '服务器IP', '巡检时间', '连接状态', 'CPU使用率', '内存使用率',
            '磁盘使用率', 'TCP监听端口', '进程状态', 'Docker状态',
            '运行中容器数', '总容器数', '镜像数', '镜像列表', '目标目录状态'
        ]
    
    def generate(self, results):
        """生成CSV报告"""
        if not results:
            print("警告: 没有巡检数据可生成报告")
            return None
        
        try:
            file_exists = os.path.exists(self.output_path)
            
            with open(self.output_path, 'a' if file_exists else 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                
                if not file_exists:
                    writer.writeheader()
                
                for result in results:
                    writer.writerow(result)
            
            print(f"报告已更新: {os.path.abspath(self.output_path)}")
            return self.output_path
        except Exception as e:
            print(f"生成报告失败: {e}")
            return None

def run_single_inspection():
    """执行一次巡检并返回结果"""
    results = []
    for server_info in SERVERS:
        inspector = ServerInspector(
            ip=server_info['ip'],
            port=server_info['port'],
            username=server_info['username'],
            key_path=server_info.get('key_path'),
            password=server_info.get('password'),
            target_dir=server_info.get('target_dir')
        )
        result = inspector.inspect()
        results.append(result)
        
        print(f"\n服务器 {result['服务器IP']}:")
        print(f"  连接状态: {result['连接状态']}")
        if '成功' in result['连接状态']:
            print(f"  CPU使用率: {result['CPU使用率']}")
            print(f"  内存使用率: {result['内存使用率']}")
            print(f"  Docker状态: {result['Docker状态']}")
            print(f"  目标目录: {result['目标目录状态']}")
    
    return results

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Linux服务器批量自动化巡检平台')
    parser.add_argument('--test', action='store_true', help='仅执行一次测试巡检')
    parser.add_argument('--password', help='SSH密码')
    parser.add_argument('--key-path', help='SSH私钥路径')
    args = parser.parse_args()
    
    # 更新服务器配置
    if args.password:
        for server in SERVERS:
            server['password'] = args.password
    if args.key_path:
        for server in SERVERS:
            server['key_path'] = args.key_path
    
    if args.test:
        print("=== 测试模式: 仅执行一次巡检 ===")
        results = run_single_inspection()
        generator = ReportGenerator()
        generator.generate(results)
        print("\n=== 测试完成 ===")
        return
    
    print("=" * 60)
    print("Linux服务器批量自动化巡检平台")
    print("=" * 60)
    print(f"服务器数量: {len(SERVERS)}")
    print(f"巡检间隔: {INSPECTION_INTERVAL} 分钟")
    print(f"持续时间: {INSPECTION_DURATION} 分钟")
    print(f"报告格式: CSV (可直接用Excel打开)")
    print("\n按 Ctrl+C 可中断巡检任务")
    print("=" * 60)
    
    start_time = time.time()
    end_time = start_time + (INSPECTION_DURATION * 60)
    inspection_count = 0
    generator = ReportGenerator()
    
    try:
        while time.time() < end_time:
            inspection_count += 1
            print(f"\n=== 第 {inspection_count} 次巡检开始 [{datetime.now().strftime('%H:%M:%S')}] ===")
            
            results = run_single_inspection()
            generator.generate(results)
            
            if time.time() + (INSPECTION_INTERVAL * 60) < end_time:
                print(f"\n等待 {INSPECTION_INTERVAL} 分钟后进行下一次巡检... (按Ctrl+C退出)")
                time.sleep(INSPECTION_INTERVAL * 60)
            else:
                break
    
    except KeyboardInterrupt:
        print("\n=== 用户中断巡检任务 ===")
    finally:
        print(f"\n=== 巡检任务结束，共执行 {inspection_count} 次 ===")
        if os.path.exists(REPORT_PATH):
            print(f"最终报告: {os.path.abspath(REPORT_PATH)}")
            print("提示: CSV文件可直接用Microsoft Excel打开查看")

if __name__ == '__main__':
    main()
