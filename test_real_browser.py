#!/usr/bin/env python3
"""
测试真实浏览器操作
"""

import sys
sys.path.append('.')

from crawler.real_playwright_spider import search_with_real_playwright
import logging

# 设置详细日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

print("=" * 60)
print("🎭 Boss直聘真实浏览器自动化测试")
print("=" * 60)
print()
print("📢 注意事项:")
print("1. Chrome浏览器窗口会自动打开")
print("2. 你会看到浏览器导航到Boss直聘")
print("3. 页面会自动搜索岗位")
print("4. 搜索过程会生成截图")
print()
print("🚀 开始测试...")
print()

# 执行搜索
try:
    jobs = search_with_real_playwright(
        keyword="数据分析",
        city="shanghai", 
        max_jobs=3
    )
    
    print(f"\n✅ 搜索完成！找到 {len(jobs)} 个岗位:")
    print("-" * 50)
    
    for i, job in enumerate(jobs, 1):
        print(f"\n📋 岗位 #{i}")
        print(f"   职位: {job.get('title', '未知')}")
        print(f"   公司: {job.get('company', '未知')}")
        print(f"   薪资: {job.get('salary', '未知')}")
        print(f"   地点: {job.get('work_location', '未知')}")
        print(f"   链接: {job.get('url', '未知')[:80]}...")
        print(f"   来源: {job.get('engine_source', '未知')}")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成！检查生成的截图文件")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()