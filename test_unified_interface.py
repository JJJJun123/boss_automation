#!/usr/bin/env python3
"""
测试统一爬虫接口的引擎切换
"""

import asyncio
import logging
from crawler.unified_crawler_interface import unified_search_jobs

# 设置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_unified_interface():
    """测试统一接口的引擎选择"""
    print("🧪 测试统一爬虫接口引擎选择")
    print("="*50)
    
    try:
        print("\n📋 测试 real_playwright 引擎...")
        # 使用real_playwright引擎
        jobs = await unified_search_jobs(
            keyword="数据分析师",
            city="shanghai", 
            max_jobs=2,
            engine="real_playwright"
        )
        
        print(f"\n📊 搜索结果:")
        print(f"岗位数量: {len(jobs)}")
        
        for i, job in enumerate(jobs, 1):
            print(f"\n📋 岗位 {i}:")
            print(f"  标题: {job.get('title', '未知')}")
            print(f"  公司: {job.get('company', '未知')}")
            print(f"  引擎来源: {job.get('engine_source', '未知')}")
            print(f"  URL: {job.get('url', '无')}")
            
            # 检查是否成功获取了详情信息
            job_desc = job.get('job_description', '')
            job_req = job.get('job_requirements', '')
            detail_success = job.get('detail_extraction_success', False)
            
            print(f"  详情页抓取成功: {'✅' if detail_success else '❌'}")
            
            if detail_success:
                print(f"  工作职责: {job_desc[:100] if job_desc else '未获取'}...")
                print(f"  任职资格: {job_req[:100] if job_req else '未获取'}...")
            else:
                print(f"  工作职责: 使用默认值")
                print(f"  任职资格: 使用默认值")
                
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_unified_interface())