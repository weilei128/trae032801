#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速测试SSH连接和基本功能
"""

import paramiko
import os

def test_ssh_connection():
    """测试SSH连接"""
    ip = '49.235.161.106'
    port = 22
    username = 'root'
    
    print(f"测试连接到: {ip}:{port}")
    print(f"用户名: {username}")
    
    # 尝试常见的密钥路径
    key_paths = [
        os.path.expanduser('~/.ssh/id_rsa'),
        os.path.expanduser('~/.ssh/id_dsa'),
        'id_rsa',
        'private_key.pem'
    ]
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # 1. 尝试密钥认证
    for key_path in key_paths:
        if os.path.exists(key_path):
            print(f"\n尝试使用密钥: {key_path}")
            try:
                private_key = paramiko.RSAKey.from_private_key_file(key_path)
                ssh.connect(ip, port, username, pkey=private_key, timeout=10)
                print("密钥认证成功!")
                return ssh
            except Exception as e:
                print(f"密钥认证失败: {e}")
    
    # 2. 尝试SSH代理
    print("\n尝试使用SSH代理...")
    try:
        agent = paramiko.Agent()
        agent_keys = agent.get_keys()
        if agent_keys:
            for key in agent_keys:
                try:
                    ssh.connect(ip, port, username, pkey=key, timeout=10)
                    print("SSH代理认证成功!")
                    return ssh
                except:
                    pass
        print("SSH代理认证失败")
    except Exception as e:
        print(f"SSH代理错误: {e}")
    
    # 3. 提示密码
    print("\n请输入密码进行认证 (或按Ctrl+C取消):")
    try:
        import getpass
        password = getpass.getpass("密码: ")
        ssh.connect(ip, port, username, password=password, timeout=10)
        print("密码认证成功!")
        return ssh
    except Exception as e:
        print(f"密码认证失败: {e}")
        return None

def test_commands(ssh):
    """测试执行命令"""
    commands = [
        ('hostname', '主机名'),
        ('uptime', '系统运行时间'),
        ('free -m | grep Mem', '内存使用'),
        ('df -h / | tail -1', '根目录磁盘'),
        ('which docker', 'Docker路径'),
        ('docker ps -q 2>/dev/null | wc -l', '运行中容器数')
    ]
    
    print("\n" + "="*50)
    print("执行测试命令:")
    print("="*50)
    
    for cmd, desc in commands:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"{desc}: {output}")

if __name__ == '__main__':
    print("="*50)
    print("服务器连接测试工具")
    print("="*50)
    
    ssh = test_ssh_connection()
    if ssh:
        test_commands(ssh)
        ssh.close()
        print("\n" + "="*50)
        print("测试完成!")
        print("="*50)
    else:
        print("\n连接失败，请检查:")
        print("1. 网络连接是否正常")
        print("2. SSH密钥是否配置正确")
        print("3. 密码是否正确")
        print("4. 服务器是否允许SSH连接")
