#!/usr/bin/env python3
"""
简单测试AI分析器，不涉及爬虫
"""

import sys
import os
import threading

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_ai_only():
    """只测试AI分析，不涉及爬虫"""
    
    print("🧪 测试AI分析器...")
    
    try:
        # 创建测试岗位数据
        test_job = {
            'title': '测试AI工程师',
            'company': '测试公司',
            'salary': '20k-30k',
            'job_description': '''
            岗位职责：
            1. 负责机器学习算法开发
            2. 参与AI产品设计和优化
            3. 处理大规模数据分析
            
            任职要求：
            1. 熟悉Python编程
            2. 了解深度学习框架
            3. 有AI项目经验
            '''
        }
        
        # 测试Enhanced分析器
        from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer
        
        analyzer = EnhancedJobAnalyzer(
            extraction_provider="glm",
            analysis_provider="deepseek"
        )
        print("✅ Enhanced分析器创建成功")
        
        # 测试信息提取
        print("🔍 测试信息提取...")
        extracted = analyzer._stage1_extract_job_info([test_job])
        
        import asyncio
        extracted_result = asyncio.run(extracted)
        print(f"✅ 信息提取完成: {len(extracted_result)} 个结果")
        
        return True
        
    except Exception as e:
        print(f"❌ AI测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ai_in_thread():
    """在线程中测试AI"""
    
    print("🧵 在线程中测试AI...")
    
    result = {"success": False}
    
    def thread_worker():
        try:
            result["success"] = test_ai_only()
        except Exception as e:
            print(f"线程中出错: {e}")
            import traceback
            traceback.print_exc()
    
    thread = threading.Thread(target=thread_worker)
    thread.daemon = True
    thread.start()
    thread.join()
    
    return result["success"]

if __name__ == "__main__":
    print("🏃 在主线程中测试AI...")
    success1 = test_ai_only()
    
    print("\n" + "="*50)
    
    print("🧵 在后台线程中测试AI...")  
    success2 = test_ai_in_thread()
    
    print(f"\n📊 测试结果:")
    print(f"   主线程: {'✅ 成功' if success1 else '❌ 失败'}")
    print(f"   后台线程: {'✅ 成功' if success2 else '❌ 失败'}")