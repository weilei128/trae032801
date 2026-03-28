import paramiko
import pandas as pd
from datetime import datetime
import schedule
import time
import os
import sys

# 尝试导入本地配置
try:
    from config_local import SERVERS, INSPECTION_INTERVAL, INSPECTION_DURATION, REPORT_PATH, SSH_TIMEOUT
except ImportError:
    try:
        from config import SERVERS, INSPECTION_INTERVAL, INSPECTION_DURATION, REPORT_PATH, SSH_TIMEOUT
    except ImportError:
        # 默认配置
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
        INSPECTION_INTERVAL = 10
        INSPECTION_DURATION = 30
        REPORT_PATH = 'server_inspection_report.xlsx'
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
        self.sftp = None
        
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
            
            # 优先使用密钥认证
            if self.key_path and os.path.exists(self.key_path):
                try:
                    private_key = paramiko.RSAKey.from_private_key_file(self.key_path)
                    connect_kwargs['pkey'] = private_key
                except Exception as e:
                    print(f"密钥加载失败: {e}，尝试密码认证")
                    if self.password:
                        connect_kwargs['password'] = self.password
            elif self.password:
                connect_kwargs['password'] = self.password
            else:
                # 尝试使用SSH代理
                try:
                    agent = paramiko.Agent()
                    agent_keys = agent.get_keys()
                    if agent_keys:
                        connect_kwargs['pkey'] = agent_keys[0]
                    else:
                        return False, "未找到可用的认证方式（密钥/密码/SSH代理）"
                except:
                    return False, "未找到可用的认证方式（密钥/密码/SSH代理）"
            
            self.ssh.connect(**connect_kwargs)
            self.sftp = self.ssh.open_sftp()
            return True, "连接成功"
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
            # 备选方法
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
        command = "df -h --output=source,pcent,target 2>/dev/null | grep -v 'tmpfs' | grep -v 'udev' | grep -v 'boot' | head -10"
        output, error = self.execute_command(command)
        if error:
            # 备选命令
            command = "df -h 2>/dev/null | grep -v 'tmpfs' | grep -v 'udev' | grep -v 'boot' | awk '{print $1, $5, $6}' | head -10"
            output, error = self.execute_command(command)
            if error:
                return "获取失败"
        return output.replace('\n', '; ')
    
    def get_tcp_ports(self):
        """获取TCP监听端口"""
        command = "ss -tuln 2>/dev/null | grep LISTEN | awk '{print $5}' | awk -F: '{print $NF}' | sort -n | uniq | head -30"
        output, error = self.execute_command(command)
        if error:
            command = "netstat -tuln 2>/dev/null | grep LISTEN | awk '{print $4}' | awk -F: '{print $NF}' | sort -n | uniq | head -30"
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
        # 检查docker是否安装
        check_cmd = "which docker || command -v docker 2>/dev/null"
        output, error = self.execute_command(check_cmd)
        if not output or error:
            return "Docker未安装", "0", "0", "0", "N/A"
        
        # 检查docker服务是否运行
        check_running = "docker info >/dev/null 2>&1 && echo 'running' || echo 'stopped'"
        status, _ = self.execute_command(check_running)
        if 'stopped' in status:
            return "Docker服务未运行", "0", "0", "0", "N/A"
        
        # 运行中的容器数量
        count_cmd = "docker ps -q 2>/dev/null | wc -l"
        count_output, _ = self.execute_command(count_cmd)
        running_containers = count_output.strip() if count_output else "0"
        
        # 总容器数
        stopped_cmd = "docker ps -aq 2>/dev/null | wc -l"
        stopped_output, _ = self.execute_command(stopped_cmd)
        total_containers = stopped_output.strip() if stopped_output else "0"
        
        # 镜像数量
        images_cmd = "docker images -q 2>/dev/null | wc -l"
        images_output, _ = self.execute_command(images_cmd)
        images_count = images_output.strip() if images_output else "0"
        
        # 镜像列表（前10个）
        images_list_cmd = "docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | head -10"
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
        elif error:
            return f"错误: {error[:30]}"
        
        # 统计文件数
        count_cmd = f"find {self.target_dir} -maxdepth 1 -type f 2>/dev/null | wc -l"
        count_output, _ = self.execute_command(count_cmd)
        file_count = count_output.strip() if count_output else "N/A"
        
        # 目录大小
        size_cmd = f"du -sh {self.target_dir} 2>/dev/null | awk '{{print $1}}'"
        size_output, _ = self.execute_command(size_cmd)
        dir_size = size_output.strip() if size_output else "N/A"
        
        return f"存在, 文件数: {file_count}, 大小: {dir_size}"
    
    def disconnect(self):
        """关闭连接"""
        if self.sftp:
            try:
                self.sftp.close()
            except:
                pass
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
    
    def generate(self, results):
        """生成Excel报告"""
        if not results:
            print("警告: 没有巡检数据可生成报告")
            return None
        
        df = pd.DataFrame(results)
        
        try:
            # 创建Excel写入器
            with pd.ExcelWriter(self.output_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='巡检汇总', index=False)
                
                # 调整列宽
                worksheet = writer.sheets['巡检汇总']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if cell.value and len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 60)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            print(f"报告已更新: {os.path.abspath(self.output_path)}")
            return self.output_path
        except Exception as e:
            print(f"生成报告失败: {e}")
            return None

class InspectionScheduler:
    def __init__(self, servers, interval_minutes=INSPECTION_INTERVAL, duration_minutes=INSPECTION_DURATION):
        self.servers = servers
        self.interval_minutes = interval_minutes
        self.duration_minutes = duration_minutes
        self.start_time = time.time()
        self.end_time = self.start_time + (duration_minutes * 60)
        self.results = []
        self.report_generator = ReportGenerator()
        self.inspection_count = 0
    
    def run_inspection(self):
        """执行一次巡检"""
        self.inspection_count += 1
        print(f"\n=== 第 {self.inspection_count} 次巡检开始 [{datetime.now().strftime('%H:%M:%S')}] ===")
        current_results = []
        
        for server_info in self.servers:
            inspector = ServerInspector(
                ip=server_info['ip'],
                port=server_info['port'],
                username=server_info['username'],
                key_path=server_info.get('key_path'),
                password=server_info.get('password'),
                target_dir=server_info.get('target_dir')
            )
            result = inspector.inspect()
            current_results.append(result)
            
            # 打印结果摘要
            print(f"\n服务器 {result['服务器IP']}:")
            print(f"  连接状态: {result['连接状态']}")
            if '成功' in result['连接状态']:
                print(f"  CPU使用率: {result['CPU使用率']}")
                print(f"  内存使用率: {result['内存使用率']}")
                print(f"  Docker状态: {result['Docker状态']}")
                print(f"  目标目录: {result['目标目录状态']}")
        
        self.results.extend(current_results)
        
        # 更新报告
        self.report_generator.generate(self.results)
        
        # 检查是否达到结束时间
        if time.time() >= self.end_time:
            print(f"\n=== 巡检任务已完成，共执行 {self.inspection_count} 次 ===")
            print(f"最终报告: {os.path.abspath(self.report_generator.output_path)}")
            return False  # 停止调度
        return True  # 继续调度
    
    def start(self):
        """启动定时巡检"""
        print("=" * 60)
        print("Linux服务器批量自动化巡检平台")
        print("=" * 60)
        print(f"\n服务器数量: {len(self.servers)}")
        print(f"巡检间隔: {self.interval_minutes} 分钟")
        print(f"持续时间: {self.duration_minutes} 分钟")
        print(f"预计执行次数: {self.duration_minutes // self.interval_minutes + 1} 次")
        print(f"\n服务器列表:")
        for server in self.servers:
            print(f"  - {server['ip']}:{server['port']} ({server['username']})")
        print("\n按 Ctrl+C 可中断巡检任务")
        print("=" * 60)
        
        # 立即执行第一次
        if not self.run_inspection():
            return
        
        # 设置定时任务
        schedule.every(self.interval_minutes).minutes.do(self.run_inspection)
        
        try:
            while time.time() < self.end_time:
                schedule.run_pending()
                time.sleep(5)  # 每5秒检查一次
        except KeyboardInterrupt:
            print("\n=== 用户中断巡检任务 ===")
        finally:
            print(f"=== 巡检任务结束，共执行 {self.inspection_count} 次 ===")
            if os.path.exists(self.report_generator.output_path):
                print(f"最终报告: {os.path.abspath(self.report_generator.output_path)}")

def main():
    # 检查是否有命令行参数指定配置
    import argparse
    parser = argparse.ArgumentParser(description='Linux服务器批量自动化巡检平台')
    parser.add_argument('--test', action='store_true', help='仅执行一次测试巡检')
    parser.add_argument('--server', help='指定单个服务器IP进行测试')
    args = parser.parse_args()
    
    servers_to_check = SERVERS
    
    # 如果指定了单个服务器
    if args.server:
        servers_to_check = [s for s in SERVERS if s['ip'] == args.server]
        if not servers_to_check:
            print(f"错误: 未找到服务器 {args.server} 的配置")
            sys.exit(1)
    
    # 测试模式
    if args.test:
        print("=== 测试模式: 仅执行一次巡检 ===")
        for server_info in servers_to_check:
            print(f"\n检查服务器: {server_info['ip']}")
            inspector = ServerInspector(
                ip=server_info['ip'],
                port=server_info['port'],
                username=server_info['username'],
                key_path=server_info.get('key_path'),
                password=server_info.get('password'),
                target_dir=server_info.get('target_dir')
            )
            result = inspector.inspect()
            print(f"连接状态: {result['连接状态']}")
            if '成功' in result['连接状态']:
                print(f"CPU使用率: {result['CPU使用率']}")
                print(f"内存使用率: {result['内存使用率']}")
                print(f"Docker状态: {result['Docker状态']}")
        print("\n=== 测试完成 ===")
        return
    
    # 正常启动巡检
    scheduler = InspectionScheduler(servers=servers_to_check)
    scheduler.start()

if __name__ == '__main__':
    main()
