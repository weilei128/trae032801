import time
import threading
from datetime import datetime
from typing import Dict, Any, List
import config
from ssh_client import SSHClient
from system_collector import SystemCollector
from service_collector import ServiceCollector
from docker_collector import DockerCollector
from excel_reporter import ExcelReporter


class InspectionEngine:
    def __init__(self):
        self.reporter = ExcelReporter()
        self.history_data: List[Dict[str, Any]] = []
        self.report_filepath: str = None
        self.inspection_count: int = 0
        self.running: bool = False
        self.timer: threading.Timer = None

    def inspect_server(self, server_config: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'inspection_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'server_name': server_config.get('name', server_config['host']),
            'host': server_config['host'],
            'system': {},
            'cpu': {},
            'memory': {},
            'disk': [],
            'ports': [],
            'listening_ports': [],
            'processes': [],
            'docker_summary': {},
            'containers': [],
            'images': []
        }
        
        ssh = SSHClient(
            host=server_config['host'],
            port=server_config['port'],
            username=server_config['username'],
            key_file=server_config.get('key_file'),
            password=server_config.get('password')
        )
        
        try:
            if not ssh.connect():
                result['error'] = 'SSH连接失败'
                return result
            
            print(f"  [{server_config['host']}] SSH连接成功")
            
            sys_collector = SystemCollector(ssh)
            result['system'] = sys_collector.get_system_info()
            result['cpu'] = sys_collector.get_cpu_info()
            result['memory'] = sys_collector.get_memory_info()
            result['disk'] = sys_collector.get_disk_info()
            print(f"  [{server_config['host']}] 系统信息采集完成")
            
            svc_collector = ServiceCollector(ssh)
            result['ports'] = svc_collector.check_tcp_ports()
            result['listening_ports'] = svc_collector.get_all_listening_ports()
            result['processes'] = svc_collector.check_processes()
            print(f"  [{server_config['host']}] 服务状态采集完成")
            
            docker_collector = DockerCollector(ssh)
            result['docker_summary'] = docker_collector.get_docker_summary()
            result['containers'] = docker_collector.get_containers()
            result['images'] = docker_collector.get_images()
            print(f"  [{server_config['host']}] Docker信息采集完成")
            
        except Exception as e:
            result['error'] = str(e)
            print(f"  [{server_config['host']}] 采集异常: {e}")
        finally:
            ssh.disconnect()
        
        return result

    def run_inspection(self):
        if not self.running:
            return
        
        self.inspection_count += 1
        inspection_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"\n{'='*60}")
        print(f"[{inspection_time}] 开始第 {self.inspection_count} 次巡检")
        print(f"{'='*60}")
        
        all_data = {}
        
        for server_config in config.SERVERS:
            server_name = server_config.get('name', server_config['host'])
            print(f"\n正在巡检服务器: {server_name} ({server_config['host']})")
            
            server_data = self.inspect_server(server_config)
            all_data[server_name] = server_data
            
            self._add_to_history(server_name, server_data, inspection_time)
        
        if self.report_filepath is None:
            self.report_filepath = self.reporter.generate_report(all_data, self.history_data)
            print(f"\n巡检报告已生成: {self.report_filepath}")
        else:
            self.reporter.update_report(self.report_filepath, all_data, self.history_data)
            print(f"\n巡检报告已更新: {self.report_filepath}")
        
        self._print_summary(all_data)
        
        if self.running:
            elapsed = time.time() - self.start_time
            if elapsed < config.TOTAL_DURATION:
                remaining = config.TOTAL_DURATION - elapsed
                next_interval = min(config.INSPECTION_INTERVAL, remaining)
                print(f"\n下次巡检将在 {int(next_interval)} 秒后开始...")
                self.timer = threading.Timer(next_interval, self.run_inspection)
                self.timer.start()
            else:
                print(f"\n巡检任务已完成，共执行 {self.inspection_count} 次巡检")
                self.running = False

    def _add_to_history(self, server_name: str, server_data: Dict[str, Any], inspection_time: str):
        cpu_usage = server_data.get('cpu', {}).get('cpu_usage', 0)
        memory_usage = server_data.get('memory', {}).get('usage_percent', 0)
        
        disk_max_usage = 0
        for disk in server_data.get('disk', []):
            disk_max_usage = max(disk_max_usage, disk.get('usage_percent', 0))
        
        docker_summary = server_data.get('docker_summary', {})
        docker_status = "运行中" if docker_summary.get('running', False) else "未运行"
        containers_running = docker_summary.get('containers_running', 0)
        
        abnormal_count = 0
        if cpu_usage > 80:
            abnormal_count += 1
        if memory_usage > 80:
            abnormal_count += 1
        if disk_max_usage > 80:
            abnormal_count += 1
        
        for proc in server_data.get('processes', []):
            if not proc.get('is_running', False):
                abnormal_count += 1
        
        self.history_data.append({
            'inspection_time': inspection_time,
            'server_name': server_name,
            'cpu_usage': cpu_usage,
            'memory_usage': memory_usage,
            'disk_max_usage': disk_max_usage,
            'docker_status': docker_status,
            'containers_running': containers_running,
            'abnormal_count': abnormal_count
        })

    def _print_summary(self, all_data: Dict[str, Any]):
        print(f"\n{'='*60}")
        print("巡检摘要:")
        print(f"{'='*60}")
        
        for server_name, data in all_data.items():
            print(f"\n【{server_name}】")
            
            cpu = data.get('cpu', {})
            print(f"  CPU: 使用率 {cpu.get('cpu_usage', 0):.1f}%, "
                  f"负载 {cpu.get('load_1min', 0):.2f}/{cpu.get('load_5min', 0):.2f}/{cpu.get('load_15min', 0):.2f}")
            
            mem = data.get('memory', {})
            print(f"  内存: {mem.get('used_mb', 0)}/{mem.get('total_mb', 0)} MB ({mem.get('usage_percent', 0):.1f}%)")
            
            disk = data.get('disk', [])
            for d in disk:
                print(f"  磁盘 [{d.get('mount_point', '')}]: {d.get('used', '')}/{d.get('size', '')} ({d.get('usage_percent', 0)}%)")
            
            docker = data.get('docker_summary', {})
            if docker.get('installed'):
                print(f"  Docker: {docker.get('version', '')}, "
                      f"容器 {docker.get('containers_running', 0)}/{docker.get('containers_total', 0)} 运行中")
            else:
                print(f"  Docker: 未安装")

    def start(self):
        print(f"\n{'#'*60}")
        print("Linux服务器批量自动化巡检平台")
        print(f"{'#'*60}")
        print(f"\n配置信息:")
        print(f"  - 巡检间隔: {config.INSPECTION_INTERVAL} 秒 ({config.INSPECTION_INTERVAL // 60} 分钟)")
        print(f"  - 总运行时长: {config.TOTAL_DURATION} 秒 ({config.TOTAL_DURATION // 60} 分钟)")
        print(f"  - 目标服务器数量: {len(config.SERVERS)}")
        for s in config.SERVERS:
            print(f"    * {s.get('name', s['host'])} ({s['host']}:{s['port']})")
        print(f"  - 报告输出目录: {config.OUTPUT_DIR}")
        
        self.running = True
        self.start_time = time.time()
        self.run_inspection()

    def stop(self):
        print("\n正在停止巡检...")
        self.running = False
        if self.timer:
            self.timer.cancel()
        print(f"巡检已停止，共完成 {self.inspection_count} 次巡检")
        if self.report_filepath:
            print(f"最终报告: {self.report_filepath}")


def main():
    engine = InspectionEngine()
    
    try:
        engine.start()
    except KeyboardInterrupt:
        engine.stop()


if __name__ == '__main__':
    main()
