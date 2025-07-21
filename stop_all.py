#!/usr/bin/env python3
"""
停止所有Boss直聘自动化相关进程
"""

import subprocess
import os
import signal
import sys

def stop_processes():
    """停止所有相关进程"""
    print("🛑 停止所有Boss直聘自动化相关进程...")
    
    # 要查找的进程关键词
    keywords = [
        "run_web.py",
        "run_web_safe.py",
        "backend/app.py",
        "boss_automation",
        "flask.*5001",
        "flask.*5002",
        "flask.*5003"
    ]
    
    stopped_count = 0
    
    for keyword in keywords:
        try:
            # 使用 ps 和 grep 查找进程
            cmd = f"ps aux | grep -i '{keyword}' | grep -v grep | awk '{{print $2}}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        print(f"✅ 已停止进程 PID: {pid} (关键词: {keyword})")
                        stopped_count += 1
                    except:
                        pass
        except:
            pass
    
    # 检查特定端口
    ports = [5001, 5002, 5003]
    for port in ports:
        try:
            result = subprocess.run(
                ['lsof', '-t', f'-i:{port}'], 
                capture_output=True, 
                text=True
            )
            
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        print(f"✅ 已停止占用端口 {port} 的进程 PID: {pid}")
                        stopped_count += 1
                    except:
                        pass
        except:
            pass
    
    if stopped_count > 0:
        print(f"\n✅ 共停止 {stopped_count} 个进程")
    else:
        print("\n✅ 没有找到需要停止的进程")

if __name__ == "__main__":
    stop_processes()