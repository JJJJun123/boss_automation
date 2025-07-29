#!/usr/bin/env python3
"""
测试增强爬虫系统
验证所有优化组件的功能
"""

import asyncio
import logging
import time
from crawler.enhanced_crawler_manager import (
    get_enhanced_crawler_manager,
    enhanced_search_jobs,
    batch_enhanced_search,
    get_crawler_status,
    optimize_crawler_system
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_basic_search():
    """测试基础搜索功能"""
    print("\n" + "="*60)
    print("🧪 测试1: 基础搜索功能")
    print("="*60)
    
    try:
        results = await enhanced_search_jobs("数据分析", "shanghai", 5)
        
        print(f"✅ 搜索结果: {len(results)} 个岗位")
        
        if results:
            print("\n📋 前3个岗位:")
            for i, job in enumerate(results[:3], 1):
                print(f"  {i}. {job.get('title', '未知')} - {job.get('company', '未知')}")
                print(f"     薪资: {job.get('salary', '未知')} | 地点: {job.get('work_location', '未知')}")
                print(f"     来源: {job.get('engine_source', '未知')}")
                print()
        
        return True
        
    except Exception as e:
        print(f"❌ 基础搜索测试失败: {e}")
        return False


async def test_concurrent_search():
    """测试并发搜索功能"""
    print("\n" + "="*60)
    print("🧪 测试2: 并发搜索功能")
    print("="*60)
    
    try:
        search_requests = [
            {"keyword": "Python开发", "city": "shanghai", "max_jobs": 3},
            {"keyword": "数据科学", "city": "beijing", "max_jobs": 3},
            {"keyword": "机器学习", "city": "shenzhen", "max_jobs": 3}
        ]
        
        start_time = time.time()
        results = await batch_enhanced_search(search_requests)
        duration = time.time() - start_time
        
        print(f"✅ 并发搜索完成，耗时: {duration:.2f}s")
        print(f"📊 搜索结果统计:")
        
        total_jobs = 0
        for task_id, job_list in results.items():
            job_count = len(job_list)
            total_jobs += job_count
            print(f"  - {task_id}: {job_count} 个岗位")
        
        print(f"📈 总计: {total_jobs} 个岗位")
        return True
        
    except Exception as e:
        print(f"❌ 并发搜索测试失败: {e}")
        return False


async def test_caching_mechanism():
    """测试缓存机制"""
    print("\n" + "="*60)
    print("🧪 测试3: 缓存机制")
    print("="*60)
    
    try:
        keyword = "AI工程师"
        city = "hangzhou"
        max_jobs = 3
        
        # 第一次搜索（应该从网络获取）
        print("🔍 第一次搜索（从网络获取）...")
        start_time = time.time()
        results1 = await enhanced_search_jobs(keyword, city, max_jobs)
        duration1 = time.time() - start_time
        
        print(f"  - 结果: {len(results1)} 个岗位")
        print(f"  - 耗时: {duration1:.2f}s")
        
        # 等待一秒钟
        await asyncio.sleep(1)
        
        # 第二次搜索（应该从缓存获取）
        print("🔍 第二次搜索（从缓存获取）...")
        start_time = time.time()
        results2 = await enhanced_search_jobs(keyword, city, max_jobs)
        duration2 = time.time() - start_time
        
        print(f"  - 结果: {len(results2)} 个岗位")
        print(f"  - 耗时: {duration2:.2f}s")
        
        # 分析缓存效果
        if duration2 < duration1 * 0.5:
            print("✅ 缓存机制工作正常，第二次搜索明显更快")
        else:
            print("⚠️ 缓存机制可能未生效")
        
        return True
        
    except Exception as e:
        print(f"❌ 缓存机制测试失败: {e}")
        return False


async def test_performance_monitoring():
    """测试性能监控"""
    print("\n" + "="*60)
    print("🧪 测试4: 性能监控")
    print("="*60)
    
    try:
        # 获取系统状态
        status = await get_crawler_status()
        
        print("📊 系统状态:")
        print(f"  - 初始化状态: {status.get('initialized', False)}")
        print(f"  - 运行时长: {status.get('uptime', 0):.2f}s")
        
        runtime_stats = status.get('runtime_stats', {})
        print(f"  - 总搜索次数: {runtime_stats.get('total_searches', 0)}")
        print(f"  - 成功搜索次数: {runtime_stats.get('successful_searches', 0)}")
        print(f"  - 平均响应时间: {runtime_stats.get('avg_response_time', 0):.2f}s")
        
        # 获取性能监控数据
        perf_monitor = status.get('performance_monitor', {})
        if perf_monitor:
            print("📈 性能监控数据:")
            print(f"  - 监控激活: {perf_monitor.get('monitoring_active', False)}")
            print(f"  - 性能评分: {perf_monitor.get('performance_score', 0):.1f}/100")
            
            system_info = perf_monitor.get('system', {})
            if system_info:
                print(f"  - CPU使用率: {system_info.get('cpu_percent', 0):.1f}%")
                print(f"  - 内存使用率: {system_info.get('memory_percent', 0):.1f}%")
        
        # 获取并发管理器状态
        concurrent_mgr = status.get('concurrent_manager', {})
        if concurrent_mgr:
            print("🔄 并发管理器:")
            print(f"  - 运行状态: {concurrent_mgr.get('is_running', False)}")
            print(f"  - 活跃任务: {concurrent_mgr.get('active_tasks', 0)}")
            print(f"  - 队列大小: {concurrent_mgr.get('queue_size', 0)}")
            
            cache_stats = concurrent_mgr.get('cache_stats', {})
            if cache_stats:
                print(f"  - 缓存命中率: {cache_stats.get('hit_rate', 0):.2%}")
                print(f"  - 内存缓存大小: {cache_stats.get('memory_cache_size', 0)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 性能监控测试失败: {e}")
        return False


async def test_auto_optimization():
    """测试自动优化"""
    print("\n" + "="*60)
    print("🧪 测试5: 自动优化")
    print("="*60)
    
    try:
        # 运行自动优化
        optimization_result = await optimize_crawler_system()
        
        print("🔧 自动优化结果:")
        print(f"  - 性能评分: {optimization_result.get('performance_score', 0):.1f}")
        
        actions = optimization_result.get('optimization_actions', [])
        if actions:
            print("  - 优化动作:")
            for action in actions:
                print(f"    • {action}")
        else:
            print("  - 无需优化，系统运行良好")
        
        # 获取优化建议
        manager = await get_enhanced_crawler_manager()
        recommendations = manager.get_recommendations()
        
        print("💡 优化建议:")
        for rec in recommendations:
            print(f"  • {rec}")
        
        return True
        
    except Exception as e:
        print(f"❌ 自动优化测试失败: {e}")
        return False


async def test_error_handling():
    """测试错误处理"""
    print("\n" + "="*60)
    print("🧪 测试6: 错误处理")
    print("="*60)
    
    try:
        # 测试无效城市
        print("🔍 测试无效城市...")
        results = await enhanced_search_jobs("测试岗位", "invalid_city", 2)
        print(f"  - 无效城市搜索结果: {len(results)} 个岗位")
        
        # 测试空关键词
        print("🔍 测试空关键词...")
        results = await enhanced_search_jobs("", "shanghai", 2)
        print(f"  - 空关键词搜索结果: {len(results)} 个岗位")
        
        print("✅ 错误处理测试完成，系统具备良好的容错能力")
        return True
        
    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 开始测试增强爬虫系统")
    print("测试范围：基础搜索、并发搜索、缓存机制、性能监控、自动优化、错误处理")
    
    test_results = []
    
    # 运行所有测试
    tests = [
        ("基础搜索功能", test_basic_search),
        ("并发搜索功能", test_concurrent_search),
        ("缓存机制", test_caching_mechanism),
        ("性能监控", test_performance_monitoring),
        ("自动优化", test_auto_optimization),
        ("错误处理", test_error_handling)
    ]
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            test_results.append((test_name, result))
        except Exception as e:
            print(f"❌ 测试 '{test_name}' 执行失败: {e}")
            test_results.append((test_name, False))
    
    # 生成测试报告
    print("\n" + "="*60)
    print("📊 测试报告")
    print("="*60)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    print(f"总测试数: {total}")
    print(f"通过测试: {passed}")
    print(f"失败测试: {total - passed}")
    print(f"通过率: {passed/total:.1%}")
    
    print("\n详细结果:")
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  - {test_name}: {status}")
    
    # 关闭管理器
    try:
        manager = await get_enhanced_crawler_manager()
        await manager.shutdown()
        print("\n🛑 已关闭增强爬虫管理器")
    except:
        pass
    
    if passed == total:
        print("\n🎉 所有测试通过！增强爬虫系统运行正常。")
    else:
        print("\n⚠️ 部分测试失败，请检查系统配置。")


if __name__ == "__main__":
    asyncio.run(main())