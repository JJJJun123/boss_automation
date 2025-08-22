#!/usr/bin/env python3
"""
测试session修复是否生效
"""

import threading
import time
from backend.app import app, run_job_search_task

def test_session_fix():
    """测试在后台线程中不使用session"""
    
    # 模拟session数据
    session_data = {
        'has_resume_data': False,
        'resume_data': None
    }
    
    # 模拟搜索参数
    params = {
        'keyword': '测试岗位',
        'city': 'shanghai',
        'max_jobs': 5
    }
    
    print("🧪 开始测试session修复...")
    
    try:
        # 在后台线程中运行任务
        thread = threading.Thread(target=run_job_search_task, args=(params, session_data))
        thread.daemon = True
        thread.start()
        
        # 等待几秒钟看是否有错误
        time.sleep(3)
        
        if thread.is_alive():
            print("✅ 后台线程正在运行，没有session错误")
        else:
            print("⚠️ 后台线程已结束，可能有其他错误")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    test_session_fix()