#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示版本 - 模拟SSH连接和数据采集
用于在没有真实SSH密钥的情况下演示平台功能
"""

import json
import time
import schedule
import threading
import random
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

from ssh_collector import ServerMetrics
from excel_reporter import ExcelReporter


class DemoSSHCollector:
    """模拟SSH采集器 - 生成模拟数据用于演示"""
    
    def __init__(self, server_config: Dict[str, Any]):
        self.config = server_config
    
    def collect_all_metrics(self) -> ServerMetrics:
        """生成模拟的巡检数据"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 生成随机但合理的模拟数据
        cpu_load_1min = round(random.uniform(0.5, 3.0), 2)
        cpu_load_5min = round(cpu_load_1min * random.uniform(0.8, 1.2), 2)
        cpu_load_15min = round(cpu_load_5min * random.uniform(0.9, 1.1), 2)
        cpu_usage = round(random.uniform(20, 85), 1)
        
        memory_total = 8192  # 8GB
        memory_usage_percent = round(random.uniform(30, 80), 1)
        memory_used = round(memory_total * memory_usage_percent / 100, 1)
        memory_free = round(memory_total - memory_used, 1)
        
        disk_total = 100  # 100GB
        disk_usage_percent = round(random.uniform(40, 75), 1)
        disk_used = round(disk_total * disk_usage_percent / 100, 1)
        disk_free = round(disk_total - disk_used, 1)
        
        # 模拟TCP端口
        ports = [22, 80, 443, 3306, 6379, 8080, 9000]
        listening_ports = ', '.join([str(p) for p in random.sample(ports, random.randint(3, 6))])
        
        total_processes = random.randint(80, 150)
        running_processes = random.randint(60, total_processes)
        
        # Docker信息
        docker_installed = True
        docker_version = "Docker version 24.0.7"
        docker_images = random.randint(10, 50)
        containers_total = random.randint(5, 20)
        containers_running = random.randint(2, containers_total)
        containers_stopped = containers_total - containers_running
        
        return ServerMetrics(
            timestamp=timestamp,
            server_name=self.config['name'],
            server_ip=self.config['ip'],
            cpu_load_1min=cpu_load_1min,
            cpu_load_5min=cpu_load_5min,
            cpu_load_15min=cpu_load_15min,
            cpu_usage_percent=cpu_usage,
            memory_total_mb=memory_total,
            memory_used_mb=memory_used,
            memory_free_mb=memory_free,
            memory_usage_percent=memory_usage_percent,
            disk_total_gb=disk_total,
            disk_used_gb=disk_used,
            disk_free_gb=disk_free,
            disk_usage_percent=disk_usage_percent,
            tcp_listening_ports=listening_ports,
            total_processes=total_processes,
            running_processes=running_processes,
            docker_installed=docker_installed,
            docker_version=docker_version,
            docker_images_count=docker_images,
            docker_containers_total=containers_total,
            docker_containers_running=containers_running,
            docker_containers_stopped=containers_stopped,
            target_dir_exists=True,
            target_dir_size_mb=round(random.uniform(100, 500), 2),
            connection_status="Success",
            error_message=""
        )


class DemoInspectionPlatform:
    """演示版巡检平台"""
    
    def __init__(self, config_path: str = "config/servers.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.all_metrics: List[ServerMetrics] = []
        self.inspection_count = 0
        self.max_inspections = 0
        self.is_running = False
        self.stop_event = threading.Event()
        
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return {"servers": [], "inspection": {}}
    
    def inspect_server(self, server_config: Dict[str, Any]) -> ServerMetrics:
        """巡检单个服务器（模拟）"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 正在巡检服务器: {server_config['name']} ({server_config['ip']})")
        
        # 使用模拟采集器
        collector = DemoSSHCollector(server_config)
        metrics = collector.collect_all_metrics()
        
        print(f"  ✓ CPU负载: {metrics.cpu_load_1min:.2f}, {metrics.cpu_load_5min:.2f}, {metrics.cpu_load_15min:.2f}")
        print(f"  ✓ 内存使用率: {metrics.memory_usage_percent:.1f}%")
        print(f"  ✓ 磁盘使用率: {metrics.disk_usage_percent:.1f}%")
        print(f"  ✓ TCP监听端口: {metrics.tcp_listening_ports}")
        print(f"  ✓ Docker容器: {metrics.docker_containers_running}/{metrics.docker_containers_total} 运行中")
        print(f"  ✓ 镜像数量: {metrics.docker_images_count}")
        
        return metrics
    
    def inspect_all_servers(self):
        """巡检所有服务器"""
        self.inspection_count += 1
        print(f"\n{'='*60}")
        print(f"第 {self.inspection_count} 次巡检开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        servers = self.config.get('servers', [])
        if not servers:
            print("警告: 配置文件中没有服务器信息")
            return
        
        for server in servers:
            metrics = self.inspect_server(server)
            self.all_metrics.append(metrics)
        
        # 生成Excel报表
        self.generate_report()
        
        print(f"\n第 {self.inspection_count} 次巡检完成")
        remaining = self.max_inspections - self.inspection_count
        if remaining > 0:
            print(f"预计还剩 {remaining} 次巡检")
        print(f"{'='*60}\n")
        
        # 检查是否达到最大巡检次数
        if self.inspection_count >= self.max_inspections:
            self.stop_inspection()
    
    def generate_report(self):
        """生成Excel报表"""
        report_path = self.config.get('inspection', {}).get('report_path', 'reports/server_inspection_report.xlsx')
        
        # 确保使用绝对路径
        script_dir = Path(__file__).parent.absolute()
        if not Path(report_path).is_absolute():
            report_path = str(script_dir / report_path)
        
        reporter = ExcelReporter(report_path)
        reporter.generate_report(self.all_metrics)
        print(f"  [报表] 已更新: {report_path}")
    
    def stop_inspection(self):
        """停止巡检"""
        print(f"\n{'='*60}")
        print(f"巡检任务已完成！共执行 {self.inspection_count} 次巡检")
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        self.is_running = False
        self.stop_event.set()
        
        # 取消所有定时任务
        schedule.clear()
    
    def run_scheduled_inspection(self):
        """运行定时巡检"""
        inspection_config = self.config.get('inspection', {})
        interval_minutes = inspection_config.get('interval_minutes', 10)
        duration_minutes = inspection_config.get('duration_minutes', 30)
        
        # 计算最大巡检次数
        self.max_inspections = duration_minutes // interval_minutes
        
        # 确保至少执行1次
        if self.max_inspections < 1:
            self.max_inspections = 1
        
        print(f"\n{'='*60}")
        print("Linux服务器批量自动化巡检平台 - 演示模式")
        print(f"{'='*60}")
        print(f"巡检间隔: 每 {interval_minutes} 分钟")
        print(f"总巡检时长: {duration_minutes} 分钟")
        print(f"预计巡检次数: {self.max_inspections} 次")
        print(f"服务器数量: {len(self.config.get('servers', []))} 台")
        
        script_dir = Path(__file__).parent.absolute()
        report_path = inspection_config.get('report_path', 'reports/server_inspection_report.xlsx')
        if not Path(report_path).is_absolute():
            report_path = str(script_dir / report_path)
        print(f"报表保存路径: {report_path}")
        print(f"{'='*60}\n")
        print("注意: 当前为演示模式，使用模拟数据生成报表\n")
        
        # 立即执行第一次巡检
        self.inspect_all_servers()
        
        # 如果还有更多次巡检，设置定时任务
        if self.inspection_count < self.max_inspections:
            schedule.every(interval_minutes).minutes.do(self.inspect_all_servers)
            
            self.is_running = True
            
            # 运行调度器
            while self.is_running and not self.stop_event.is_set():
                schedule.run_pending()
                time.sleep(1)
    
    def run_once(self):
        """只执行一次巡检（用于测试）"""
        print(f"\n{'='*60}")
        print("执行单次巡检 - 演示模式")
        print(f"{'='*60}\n")
        print("注意: 当前为演示模式，使用模拟数据生成报表\n")
        
        self.inspect_all_servers()
        
        print(f"\n巡检完成！报表已生成。")


def main():
    """主函数"""
    import sys
    
    # 获取脚本所在目录
    script_dir = Path(__file__).parent.absolute()
    config_path = script_dir / "config" / "servers.json"
    
    # 创建平台实例
    platform = DemoInspectionPlatform(str(config_path))
    
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # 单次执行模式
        platform.run_once()
    else:
        # 定时执行模式
        try:
            platform.run_scheduled_inspection()
        except KeyboardInterrupt:
            print("\n\n用户中断巡检任务")
            platform.stop_inspection()


if __name__ == "__main__":
    main()
