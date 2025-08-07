#!/usr/bin/env python3
"""
统一爬虫引擎测试脚本
测试新的统一爬虫架构是否正常工作
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crawler.unified_spider import UnifiedSpider
from crawler.unified_crawler_interface import unified_search_jobs
from config.config_manager import ConfigManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_direct_spider():
    """直接测试统一爬虫引擎"""
    print("\n" + "="*60)
    print("🧪 测试1: 直接使用 UnifiedSpider")
    print("="*60)
    
    spider = UnifiedSpider(headless=False)  # 使用有头模式便于调试
    
    try:
        # 启动爬虫
        logger.info("🚀 启动统一爬虫引擎...")
        started = await spider.start()
        if not started:
            print("❌ 爬虫启动失败")
            return False
        
        print("✅ 爬虫引擎启动成功")
        
        # 测试搜索功能
        test_params = {
            "keyword": "Python开发",
            "city": "shanghai",
            "max_jobs": 5,
            "use_cache": False  # 强制不使用缓存，确保真实爬取
        }
        
        print(f"\n🔍 搜索参数:")
        for key, value in test_params.items():
            print(f"   {key}: {value}")
        
        # 执行搜索
        print("\n⏳ 开始搜索...")
        start_time = datetime.now()
        
        jobs = await spider.search_jobs(
            keyword=test_params["keyword"],
            city=test_params["city"],
            max_jobs=test_params["max_jobs"],
            use_cache=test_params["use_cache"],
            callback=lambda msg: print(f"   📢 {msg}")
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 显示结果
        print(f"\n✅ 搜索完成! 耗时: {duration:.2f}秒")
        print(f"📊 找到 {len(jobs)} 个岗位\n")
        
        # 显示前3个岗位的详细信息
        for i, job in enumerate(jobs[:3], 1):
            print(f"【岗位 {i}】")
            print(f"  职位: {job.get('title', 'N/A')}")
            print(f"  公司: {job.get('company', 'N/A')}")
            print(f"  薪资: {job.get('salary', 'N/A')}")
            print(f"  地区: {job.get('location', 'N/A')}")
            print(f"  经验: {job.get('experience', 'N/A')}")
            print(f"  学历: {job.get('education', 'N/A')}")
            print(f"  引擎: {job.get('engine_source', 'N/A')}")
            print()
        
        # 显示统计信息
        stats = spider.get_stats()
        print("📈 爬虫统计:")
        print(f"  总搜索次数: {stats['total_searches']}")
        print(f"  成功次数: {stats['successful_searches']}")
        print(f"  缓存命中次数: {stats['cache_hits']}")
        print(f"  平均响应时间: {stats['avg_response_time']:.2f}秒")
        
        return len(jobs) > 0
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        return False
        
    finally:
        # 关闭爬虫
        await spider.close()
        print("\n🔒 爬虫引擎已关闭")


async def test_unified_interface():
    """测试统一接口"""
    print("\n" + "="*60)
    print("🧪 测试2: 使用 unified_search_jobs 接口")
    print("="*60)
    
    try:
        # 测试参数
        test_params = {
            "keyword": "数据分析",
            "city": "beijing",
            "max_jobs": 3,
            "use_cache": True  # 允许使用缓存
        }
        
        print(f"\n🔍 搜索参数:")
        for key, value in test_params.items():
            print(f"   {key}: {value}")
        
        # 执行搜索
        print("\n⏳ 开始搜索...")
        start_time = datetime.now()
        
        jobs = await unified_search_jobs(
            keyword=test_params["keyword"],
            city=test_params["city"],
            max_jobs=test_params["max_jobs"],
            use_cache=test_params["use_cache"]
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 显示结果
        print(f"\n✅ 搜索完成! 耗时: {duration:.2f}秒")
        print(f"📊 找到 {len(jobs)} 个岗位")
        
        if jobs:
            print("\n✅ 统一接口测试成功!")
            # 检查是否命中缓存
            if any("缓存" in job.get("engine_source", "") for job in jobs):
                print("📦 命中缓存")
        else:
            print("\n❌ 未找到岗位数据")
        
        return len(jobs) > 0
        
    except Exception as e:
        logger.error(f"接口测试失败: {e}", exc_info=True)
        return False


async def test_cache_functionality():
    """测试缓存功能"""
    print("\n" + "="*60)
    print("🧪 测试3: 缓存功能测试")
    print("="*60)
    
    try:
        # 第一次搜索（无缓存）
        print("\n📍 第一次搜索（应该没有缓存）:")
        start_time1 = datetime.now()
        jobs1 = await unified_search_jobs(
            keyword="前端开发",
            city="hangzhou",
            max_jobs=2,
            use_cache=True
        )
        duration1 = (datetime.now() - start_time1).total_seconds()
        print(f"  耗时: {duration1:.2f}秒")
        print(f"  结果: {len(jobs1)} 个岗位")
        
        # 第二次搜索（应该命中缓存）
        print("\n📍 第二次搜索（应该命中缓存）:")
        start_time2 = datetime.now()
        jobs2 = await unified_search_jobs(
            keyword="前端开发",
            city="hangzhou",
            max_jobs=2,
            use_cache=True
        )
        duration2 = (datetime.now() - start_time2).total_seconds()
        print(f"  耗时: {duration2:.2f}秒")
        print(f"  结果: {len(jobs2)} 个岗位")
        
        # 验证缓存效果
        if duration2 < duration1 * 0.5:  # 缓存应该快很多
            print("\n✅ 缓存功能正常! 第二次搜索明显更快")
        else:
            print("\n⚠️ 缓存可能未生效")
        
        return True
        
    except Exception as e:
        logger.error(f"缓存测试失败: {e}", exc_info=True)
        return False


async def main():
    """主测试函数"""
    print("🚀 Boss直聘统一爬虫引擎测试")
    print("="*60)
    
    # 初始化配置
    config_manager = ConfigManager()
    print("✅ 配置管理器初始化成功")
    
    # 运行测试
    test_results = []
    
    # 测试1: 直接使用爬虫引擎
    result1 = await test_direct_spider()
    test_results.append(("直接爬虫引擎", result1))
    
    # 测试2: 使用统一接口
    result2 = await test_unified_interface()
    test_results.append(("统一接口", result2))
    
    # 测试3: 缓存功能
    result3 = await test_cache_functionality()
    test_results.append(("缓存功能", result3))
    
    # 显示测试总结
    print("\n" + "="*60)
    print("📊 测试总结")
    print("="*60)
    
    all_passed = True
    for test_name, passed in test_results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 所有测试通过!")
    else:
        print("\n⚠️ 部分测试失败，请检查日志")
    
    return all_passed


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(main())
    sys.exit(0 if success else 1)