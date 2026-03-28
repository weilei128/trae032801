SERVERS = [
    {
        'name': 'memo-app-server',
        'host': '49.235.161.106',
        'port': 22,
        'username': 'root',
        'key_file': None,
        'target_dir': '/opt/apps/memo-app'
    }
]

INSPECTION_INTERVAL = 600
TOTAL_DURATION = 1800

OUTPUT_DIR = './reports'

CHECK_PORTS = [80, 443, 8080, 3000, 3306, 6379, 27017]

CHECK_PROCESSES = ['nginx', 'mysql', 'redis', 'node', 'java', 'python', 'docker']
