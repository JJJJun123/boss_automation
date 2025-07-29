#!/usr/bin/env python3
"""
调试单个岗位提取问题
"""

import asyncio
import logging
from crawler.unified_crawler_interface import unified_search_jobs

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s - %(levelname)s - %(message)s'
)

# 只显示关键模块的日志
logging.getLogger('crawler.enhanced_extractor').setLevel(logging.DEBUG)
logging.getLogger('crawler.smart_selector').setLevel(logging.DEBUG)
logging.getLogger('crawler.real_playwright_spider').setLevel(logging.INFO)

logger = logging.getLogger(__name__)


async def debug_single_job():
    """调试单个岗位提取"""
    print("🔍 调试单个岗位提取问题")
    print("="*50)
    
    try:
        results = await unified_search_jobs(
            keyword="数据分析师",
            city="shanghai", 
            max_jobs=1,  # 只测试1个岗位
            engine="enhanced_playwright"
        )
        
        print(f"\n📊 最终结果:")
        print(f"岗位数量: {len(results)}")
        
        if results:
            job = results[0]
            print("✅ 成功提取岗位:")
            for key, value in job.items():
                print(f"  {key}: {value}")
        else:
            print("❌ 未提取到任何岗位")
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_single_job())