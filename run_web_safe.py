#!/usr/bin/env python3
"""
Boss直聘自动化Web版本 - 安全启动脚本 (Python 3.13兼容)
自动处理端口占用问题和依赖缺失
"""

import os
import sys
import subprocess
import socket
import time
import signal

def is_port_in_use(port):
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return False
        except OSError:
            return True

def kill_process_on_port(port):
    """终止占用指定端口的进程"""
    try:
        # 使用 lsof 查找占用端口的进程
        result = subprocess.run(
            ['lsof', '-t', f'-i:{port}'], 
            capture_output=True, 
            text=True
        )
        
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                    print(f"✅ 已终止占用端口 {port} 的进程 (PID: {pid})")
                except:
                    pass
            time.sleep(1)  # 等待进程完全退出
            return True
    except:
        pass
    return False

def find_available_port(start_port=5001, max_attempts=10):
    """查找可用端口"""
    for i in range(max_attempts):
        port = start_port + i
        if not is_port_in_use(port):
            return port
    return None

def main():
    print("=" * 50)
    print("🍎 Boss直聘自动化Web版本 - 安全启动")
    print("=" * 50)
    
    # 默认端口
    default_port = 5001
    
    # 检查端口是否被占用
    if is_port_in_use(default_port):
        print(f"⚠️  端口 {default_port} 已被占用")
        
        # 询问用户操作
        print("\n请选择操作:")
        print("1. 自动终止占用端口的进程并使用默认端口")
        print("2. 使用其他可用端口")
        print("3. 退出")
        
        choice = input("\n请输入选项 (1/2/3): ").strip()
        
        if choice == '1':
            print(f"\n正在终止占用端口 {default_port} 的进程...")
            if kill_process_on_port(default_port):
                port = default_port
            else:
                print("❌ 无法终止进程，将使用其他端口")
                port = find_available_port(default_port + 1)
        elif choice == '2':
            port = find_available_port(default_port + 1)
        else:
            print("退出程序")
            sys.exit(0)
    else:
        port = default_port
    
    if not port:
        print("❌ 无法找到可用端口")
        sys.exit(1)
    
    # 设置环境变量
    os.environ['FLASK_PORT'] = str(port)
    
    # 启动应用
    print(f"\n✅ 使用端口: {port}")
    print(f"🚀 启动应用...")
    print(f"\n📱 Web界面: http://localhost:{port}")
    print(f"🔗 API文档: http://localhost:{port}/api/health")
    print("\n按 Ctrl+C 停止服务")
    print("=" * 50)
    
    try:
        # 运行原始的启动脚本，但修改端口
        subprocess.run([
            sys.executable, 
            'backend/app.py'
        ], env={**os.environ, 'FLASK_PORT': str(port)})
    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()