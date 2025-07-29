#!/usr/bin/env python3
"""
直接测试RealPlaywrightBossSpider的详情页抓取功能
"""

import asyncio
import logging
from crawler.real_playwright_spider import RealPlaywrightBossSpider

# 设置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_real_spider():
    """测试真实爬虫的详情页功能"""
    print("🧪 测试RealPlaywrightBossSpider详情页抓取功能")
    print("="*50)
    
    spider = RealPlaywrightBossSpider(headless=True)
    
    try:
        # 启动爬虫
        await spider.start()
        
        # 搜索岗位
        jobs = await spider.search_jobs("数据分析师", "shanghai", 2)
        
        print(f"\n📊 搜索结果:")
        print(f"岗位数量: {len(jobs)}")
        
        for i, job in enumerate(jobs, 1):
            print(f"\n📋 岗位 {i}:")
            print(f"  标题: {job.get('title', '未知')}")
            print(f"  公司: {job.get('company', '未知')}")
            print(f"  URL: {job.get('url', '无')}")
            
            # 检查是否成功获取了详情信息
            job_desc = job.get('job_description', '')
            job_req = job.get('job_requirements', '')
            detail_success = job.get('detail_extraction_success', False)
            
            print(f"  详情页抓取成功: {'✅' if detail_success else '❌'}")
            
            if job_desc and not job_desc.startswith('基于文本解析'):
                print(f"  工作职责: {job_desc[:100]}...")
            else:
                print(f"  工作职责: 未获取到详细信息")
            
            if job_req and job_req != "具体要求请查看岗位详情":
                print(f"  任职资格: {job_req[:100]}...")
            else:
                print(f"  任职资格: 未获取到详细信息")
                
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await spider.close()


if __name__ == "__main__":
    asyncio.run(test_real_spider())