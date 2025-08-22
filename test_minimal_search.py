#!/usr/bin/env python3
"""
最小化测试岗位搜索功能，找出session错误的原因
"""

import sys
import os
import threading
import asyncio

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_minimal_search():
    """最小化测试搜索功能"""
    
    print("🧪 开始最小化搜索测试...")
    
    try:
        # 1. 测试爬虫
        print("1️⃣ 测试爬虫...")
        from crawler.unified_crawler_interface import unified_search_jobs
        
        # 使用asyncio运行搜索
        jobs = asyncio.run(unified_search_jobs("AI工程师", "shanghai", 2))
        print(f"✅ 爬虫测试成功，找到 {len(jobs)} 个岗位")
        
        # 2. 测试AI分析器
        print("2️⃣ 测试AI分析器...")
        from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer
        
        analyzer = EnhancedJobAnalyzer(
            extraction_provider="glm",
            analysis_provider="deepseek"
        )
        print("✅ AI分析器创建成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_in_thread():
    """在线程中运行测试"""
    
    print("🧵 在后台线程中测试...")
    
    def thread_worker():
        return test_minimal_search()
    
    # 创建线程
    thread = threading.Thread(target=thread_worker)
    thread.daemon = True
    thread.start()
    thread.join()

if __name__ == "__main__":
    # 先在主线程测试
    print("🏃 在主线程中测试...")
    success1 = test_minimal_search()
    
    print("\n" + "="*50)
    
    # 然后在后台线程测试
    test_in_thread()
    
    print(f"\n📊 测试结果: 主线程{'成功' if success1 else '失败'}")