#!/usr/bin/env python3
"""
测试新的搜索功能，强制生成新数据
"""

import asyncio
import logging
import json
import os
from datetime import datetime

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_new_search():
    """测试新的搜索功能"""
    print("🧪 测试新的搜索功能（强制生成新数据）")
    print("="*60)
    
    try:
        # 导入统一爬虫接口
        from crawler.unified_crawler_interface import unified_search_jobs
        
        print("📋 使用 real_playwright 引擎搜索岗位...")
        
        # 强制使用 real_playwright 引擎
        results = await unified_search_jobs(
            keyword="Python开发",  # 使用不同的关键词确保是新搜索
            city="shanghai", 
            max_jobs=1,  # 只搜索1个岗位来快速测试
            engine="real_playwright"  # 明确指定引擎
        )
        
        print(f"\n📊 搜索结果:")
        print(f"岗位数量: {len(results)}")
        
        if results:
            job = results[0]
            print(f"\n📋 岗位详情:")
            print(f"  标题: {job.get('title', '未知')}")
            print(f"  公司: {job.get('company', '未知')}")
            print(f"  引擎来源: {job.get('engine_source', '未知')}")
            print(f"  提取方法: {job.get('extraction_method', '未知')}")
            print(f"  是否降级提取: {job.get('fallback_extraction', '未设置')}")
            print(f"  详情页抓取成功: {job.get('detail_extraction_success', '未设置')}")
            
            # 检查工作描述
            job_desc = job.get('job_description', '')
            if job_desc:
                if job_desc.startswith('基于文本解析'):
                    print(f"  ❌ 工作描述: 仍在使用降级提取")
                    print(f"    内容: {job_desc[:100]}...")
                else:
                    print(f"  ✅ 工作描述: 可能获取了详情页数据")
                    print(f"    内容: {job_desc[:100]}...")
            
            # 检查任职要求
            job_req = job.get('job_requirements', '')
            if job_req and job_req != "具体要求请查看岗位详情":
                print(f"  ✅ 任职要求: 获取了详情页数据")
                print(f"    内容: {job_req[:100]}...")
            else:
                print(f"  ❌ 任职要求: 使用默认值")
            
            # 保存测试结果
            test_result = {
                "test_time": datetime.now().isoformat(),
                "engine_used": "real_playwright",
                "job_data": job
            }
            
            with open('test_result.json', 'w', encoding='utf-8') as f:
                json.dump(test_result, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 测试结果已保存到 test_result.json")
        
        else:
            print("❌ 未找到任何岗位")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_new_search())