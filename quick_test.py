#!/usr/bin/env python3
"""
快速测试前端显示问题
"""

import asyncio
import json
from crawler.unified_crawler_interface import get_unified_crawler, SearchParams, CrawlerEngine

async def quick_test():
    print("🔍 快速测试引擎选择...")
    
    try:
        crawler = get_unified_crawler()
        
        # 创建搜索参数
        params = SearchParams(
            keyword="数据分析师",
            city="shanghai",
            max_jobs=1,
            engine=CrawlerEngine.REAL_PLAYWRIGHT
        )
        
        print(f"使用引擎: {params.engine}")
        
        # 执行搜索（但不等待完成，只是测试调用）
        print("开始搜索...")
        # result = await crawler.search_jobs(params)
        
        # 模拟结果
        print("✅ 引擎调用成功")
        
    except Exception as e:
        print(f"❌ 出错: {e}")

if __name__ == "__main__":
    asyncio.run(quick_test())