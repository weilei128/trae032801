#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Linux服务器批量自动化巡检平台主程序
功能：
1. 通过SSH协议远程连接多台服务器
2. 采集CPU负载、内存使用率、磁盘容量、TCP端口监听状态、系统进程存活情况
3. 采集Docker相关信息（镜像、容器等）
4. 将巡检结果汇总为Excel报表
5. 支持定时巡检，每10分钟一次，持续30分钟后自动停止
"""

import json
import time
import schedule
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path

from ssh_collector import SSHCollector, ServerMetrics
from excel_reporter import ExcelReporter


class ServerInspectionPlatform:
    """服务器巡检平台主类"""
    
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
        """巡检单个服务器"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 正在巡检服务器: {server_config['name']} ({server_config['ip']})")
        
        collector = SSHCollector(server_config)
        metrics = collector.collect_all_metrics()
        
        if metrics.connection_status == "Success":
            print(f"  ✓ CPU负载: {metrics.cpu_load_1min:.2f}, {metrics.cpu_load_5min:.2f}, {metrics.cpu_load_15min:.2f}")
            print(f"  ✓ 内存使用率: {metrics.memory_usage_percent:.1f}%")
            print(f"  ✓ 磁盘使用率: {metrics.disk_usage_percent:.1f}%")
            print(f"  ✓ Docker容器: {metrics.docker_containers_running}/{metrics.docker_containers_total} 运行中")
        else:
            print(f"  ✗ 巡检失败: {metrics.error_message}")
        
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
        print(f"预计还剩 {self.max_inspections - self.inspection_count} 次巡检")
        print(f"{'='*60}\n")
        
        # 检查是否达到最大巡检次数
        if self.inspection_count >= self.max_inspections:
            self.stop_inspection()
    
    def generate_report(self):
        """生成Excel报表"""
        report_path = self.config.get('inspection', {}).get('report_path', 'reports/server_inspection_report.xlsx')
        reporter = ExcelReporter(report_path)
        reporter.generate_report(self.all_metrics)
    
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
        
        print(f"\n{'='*60}")
        print("Linux服务器批量自动化巡检平台")
        print(f"{'='*60}")
        print(f"巡检间隔: 每 {interval_minutes} 分钟")
        print(f"总巡检时长: {duration_minutes} 分钟")
        print(f"预计巡检次数: {self.max_inspections} 次")
        print(f"服务器数量: {len(self.config.get('servers', []))} 台")
        print(f"报表保存路径: {inspection_config.get('report_path', 'reports/server_inspection_report.xlsx')}")
        print(f"{'='*60}\n")
        
        # 立即执行第一次巡检
        self.inspect_all_servers()
        
        # 设置定时任务
        schedule.every(interval_minutes).minutes.do(self.inspect_all_servers)
        
        self.is_running = True
        
        # 运行调度器
        while self.is_running and not self.stop_event.is_set():
            schedule.run_pending()
            time.sleep(1)
    
    def run_once(self):
        """只执行一次巡检（用于测试）"""
        print(f"\n{'='*60}")
        print("执行单次巡检")
        print(f"{'='*60}\n")
        
        self.inspect_all_servers()
        
        print(f"\n巡检完成！报表已生成。")


def main():
    """主函数"""
    import sys
    
    # 获取脚本所在目录
    script_dir = Path(__file__).parent.absolute()
    config_path = script_dir / "config" / "servers.json"
    
    # 创建平台实例
    platform = ServerInspectionPlatform(str(config_path))
    
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
