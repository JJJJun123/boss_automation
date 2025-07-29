#!/usr/bin/env python3
"""
测试爬虫修复效果
验证页面加载等待和降级策略是否有效
"""

import asyncio
import logging
from crawler.unified_crawler_interface import unified_search_jobs

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def test_crawler_fix():
    """测试爬虫修复效果"""
    print("🧪 测试爬虫修复效果")
    print("="*50)
    
    test_cases = [
        {"keyword": "数据分析", "city": "shanghai", "max_jobs": 3},
        {"keyword": "Python开发", "city": "beijing", "max_jobs": 2},
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 测试用例 {i}: {test_case['keyword']} @ {test_case['city']}")
        print("-" * 30)
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            results = await unified_search_jobs(
                keyword=test_case["keyword"],
                city=test_case["city"],
                max_jobs=test_case["max_jobs"],
                engine="enhanced_playwright"
            )
            
            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time
            
            print(f"✅ 搜索完成")
            print(f"⏱️ 耗时: {duration:.2f} 秒")
            print(f"📊 结果数量: {len(results)}")
            
            if results:
                print("📋 岗位详情:")
                for j, job in enumerate(results, 1):
                    print(f"  {j}. {job.get('title', '未知职位')}")
                    print(f"     公司: {job.get('company', '未知公司')}")
                    print(f"     薪资: {job.get('salary', '未知薪资')}")
                    print(f"     地点: {job.get('work_location', '未知地点')}")
                    print(f"     来源: {job.get('engine_source', '未知来源')}")
                    
                    # 检查是否是降级提取
                    if job.get('fallback_extraction'):
                        print(f"     ⚠️ 降级提取: {job.get('extraction_method')}")
                    
                    print()
            else:
                print("❌ 未找到任何岗位")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
        
        print("=" * 50)


async def main():
    """主函数"""
    print("🚀 Boss直聘爬虫修复测试")
    print("测试内容: 页面加载等待、智能选择器、降级策略")
    print()
    
    await test_crawler_fix()
    
    print("\n✅ 测试完成")
    print("如果仍有问题，请检查:")
    print("1. 网络连接是否正常")
    print("2. Boss直聘网站是否可正常访问")
    print("3. 是否需要登录或有验证码")


if __name__ == "__main__":
    asyncio.run(main())