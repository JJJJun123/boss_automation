#!/usr/bin/env python3
"""
调试引擎选择问题
"""

import json
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_engine_selection():
    """调试引擎选择逻辑"""
    print("🔍 调试引擎选择问题")
    print("="*50)
    
    # 1. 检查当前数据文件
    try:
        with open('data/job_results.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📊 当前数据文件状态:")
        print(f"  生成时间: {data['metadata']['generated_time']}")
        print(f"  总岗位数: {data['metadata']['total_searched']}")
        
        # 检查第一个岗位的引擎来源
        if data['all_jobs']:
            first_job = data['all_jobs'][0]
            print(f"\n📋 第一个岗位信息:")
            print(f"  引擎来源: {first_job.get('engine_source', '未设置')}")
            print(f"  提取方法: {first_job.get('extraction_method', '未设置')}")
            print(f"  是否降级提取: {first_job.get('fallback_extraction', '未设置')}")
            print(f"  详情页抓取成功: {first_job.get('detail_extraction_success', '未设置')}")
            
            # 检查job_description的内容
            job_desc = first_job.get('job_description', '')
            if job_desc:
                print(f"  工作描述前50字符: {job_desc[:50]}...")
                if job_desc.startswith('基于文本解析的岗位描述'):
                    print("  ❌ 使用的是降级提取，不是详情页数据")
                else:
                    print("  ✅ 可能是详情页数据")
    
    except FileNotFoundError:
        print("❌ 数据文件不存在")
    except Exception as e:
        print(f"❌ 读取数据文件失败: {e}")
    
    # 2. 检查后端代码中的引擎设置
    print(f"\n🔧 检查后端代码:")
    try:
        with open('backend/app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找关键的引擎调用代码
        if 'engine="real_playwright"' in content:
            print("  ✅ 找到 real_playwright 引擎调用")
        else:
            print("  ❌ 未找到 real_playwright 引擎调用")
        
        if 'unified_search_jobs(' in content:
            print("  ✅ 找到 unified_search_jobs 调用")
        else:
            print("  ❌ 未找到 unified_search_jobs 调用")
    
    except Exception as e:
        print(f"❌ 检查后端代码失败: {e}")
    
    # 3. 建议解决方案
    print(f"\n💡 问题诊断:")
    print("1. 如果数据显示使用降级提取，说明没有使用 real_playwright 引擎")
    print("2. 需要确保后端调用了正确的引擎")
    print("3. 可能需要重启应用使修改生效")

if __name__ == "__main__":
    debug_engine_selection()