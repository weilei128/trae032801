# Linux服务器批量自动化巡检平台

## 功能概述

这是一个基于Python的Linux服务器批量自动化巡检平台，通过SSH协议远程连接服务器，采集各项系统指标并生成Excel报表。

### 采集指标

1. **CPU信息**: 1分钟/5分钟/15分钟负载、CPU使用率
2. **内存信息**: 总内存、已用内存、剩余内存、使用率
3. **磁盘信息**: 总容量、已用容量、剩余容量、使用率
4. **网络信息**: TCP端口监听状态
5. **进程信息**: 总进程数、运行中进程数
6. **Docker信息**: 
   - Docker是否安装及版本
   - 镜像仓库中的镜像数量
   - 容器总数、运行中容器数、已停止容器数
7. **目标目录**: 指定目录是否存在及其大小

## 项目结构

```
server_inspector/
├── main.py                 # 主程序入口
├── ssh_collector.py        # SSH连接和信息采集模块
├── excel_reporter.py       # Excel报表生成模块
├── requirements.txt        # Python依赖包
├── config/
│   ├── servers.json        # 服务器配置
│   └── id_rsa             # SSH私钥文件（需替换为实际密钥）
└── reports/               # 生成的报表目录
    └── server_inspection_report.xlsx
```

## 安装依赖

```bash
cd server_inspector
pip install -r requirements.txt
```

## 配置说明

### 1. 配置服务器信息

编辑 `config/servers.json` 文件：

```json
{
  "servers": [
    {
      "name": "memo-app-server",
      "ip": "49.235.161.106",
      "port": 22,
      "username": "root",
      "auth_type": "key",
      "key_path": "config/id_rsa",
      "target_dir": "/opt/apps/memo-app"
    }
  ],
  "inspection": {
    "interval_minutes": 10,
    "duration_minutes": 30,
    "report_path": "reports/server_inspection_report.xlsx"
  }
}
```

### 2. 配置SSH密钥

将您的SSH私钥保存到 `config/id_rsa` 文件中。

**注意**: 在Linux/Mac系统上，请确保私钥文件权限设置为600：
```bash
chmod 600 config/id_rsa
```

## 使用方法

### 定时巡检模式（默认）

每10分钟巡检一次，持续30分钟后自动停止：

```bash
python main.py
```

### 单次巡检模式

只执行一次巡检：

```bash
python main.py --once
```

## 报表说明

生成的Excel报表包含两个工作表：

1. **巡检汇总**: 每次巡检的详细数据，包含所有采集的指标
   - 连接状态列会根据成功/失败显示不同颜色
   - CPU使用率>80%、内存使用率>85%、磁盘使用率>90%会标红告警

2. **统计信息**: 各服务器的统计汇总，包括平均值、最大值、最小值

## 定时任务说明

- **巡检间隔**: 每10分钟执行一次
- **总时长**: 30分钟后自动停止
- **巡检次数**: 共执行3次巡检（0分钟、10分钟、20分钟）

可以通过修改 `config/servers.json` 中的 `inspection` 部分来调整这些参数：

```json
"inspection": {
    "interval_minutes": 10,    // 巡检间隔（分钟）
    "duration_minutes": 30,    // 总运行时长（分钟）
    "report_path": "reports/server_inspection_report.xlsx"
}
```

## 注意事项

1. 确保运行环境可以访问目标服务器的SSH端口
2. SSH私钥需要有正确的权限设置
3. 目标服务器需要安装并启用SSH服务
4. 采集Docker信息需要目标服务器已安装Docker
5. 建议使用Python 3.8或更高版本运行

## 中断巡检

在定时巡检模式下，可以按 `Ctrl+C` 随时中断巡检任务。
