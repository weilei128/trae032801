# 服务器配置文件模板
# 复制此文件为 config_local.py 并根据实际情况修改

import os

# 服务器列表配置
SERVERS = [
    {
        'ip': '49.235.161.106',
        'port': 22,
        'username': 'root',
        'key_path': os.path.expanduser('~/.ssh/id_rsa'),  # 默认SSH私钥路径
        'password': None,  # 如果使用密码认证，请设置此项
        'target_dir': '/opt/apps/memo-app'
    }
    # 可添加更多服务器
    # {
    #     'ip': '192.168.1.100',
    #     'port': 22,
    #     'username': 'admin',
    #     'key_path': '/path/to/your/private_key',
    #     'password': 'your_password',  # 可选
    #     'target_dir': '/opt/apps'
    # }
]

# 巡检配置
INSPECTION_INTERVAL = 10  # 巡检间隔（分钟）
INSPECTION_DURATION = 30  # 总持续时间（分钟）
REPORT_PATH = 'server_inspection_report.xlsx'  # 报告输出路径

# SSH连接超时设置（秒）
SSH_TIMEOUT = 30
