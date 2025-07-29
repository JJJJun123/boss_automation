#!/usr/bin/env python3
"""
快速测试大规模抓取优化功能
"""

import os
import sys
import asyncio
import logging

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 简单的日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_job_requirement_summarizer():
    """测试AI岗位要求总结器"""
    logger.info("🧠 测试AI岗位要求总结器...")
    
    try:
        from analyzer.job_requirement_summarizer import JobRequirementSummarizer
        
        # 创建测试数据
        test_jobs = [
            {
                "title": "AI算法工程师",
                "company": "测试公司A",
                "job_description": "负责机器学习算法开发和优化，包括深度学习模型设计、数据预处理等工作。",
                "job_requirements": "要求3年以上AI算法经验，熟练掌握Python、TensorFlow等工具，本科以上学历。",
                "salary": "20K-30K",
                "work_location": "上海"
            },
            {
                "title": "数据分析师",
                "company": "测试公司B", 
                "job_description": "负责业务数据分析，制作数据报表，支持业务决策。",
                "job_requirements": "统计学或相关专业，熟悉SQL、Python，有2年以上数据分析经验。",
                "salary": "15K-25K",
                "work_location": "北京"
            }
        ]
        
        # 测试总结器
        summarizer = JobRequirementSummarizer("deepseek")
        
        # 测试单个岗位总结
        logger.info("🔍 测试单个岗位总结...")
        single_summary = await summarizer.summarize_single_job(test_jobs[0])
        logger.info(f"✅ 单个总结完成，置信度: {single_summary.summary_confidence:.2f}")
        logger.info(f"   核心职责: {single_summary.core_responsibilities[:2]}")
        logger.info(f"   关键要求: {single_summary.key_requirements[:2]}")
        
        # 测试批量总结
        logger.info("🔄 测试批量岗位总结...")
        batch_summaries = await summarizer.summarize_batch_jobs(test_jobs)
        logger.info(f"✅ 批量总结完成: {len(batch_summaries)} 个岗位")
        
        # 获取成本报告
        cost_report = summarizer.get_cost_savings_report()
        logger.info("💰 成本优化报告:")
        logger.info(f"   缓存命中率: {cost_report.get('cache_statistics', {}).get('cache_hit_rate', '0%')}")
        logger.info(f"   节省成本: {cost_report.get('cost_analysis', {}).get('total_savings', '¥0.00')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_configuration_updates():
    """测试配置更新"""
    logger.info("⚙️ 测试配置更新...")
    
    try:
        from config.config_manager import ConfigManager
        
        config_manager = ConfigManager()
        search_config = config_manager.get_search_config()
        
        logger.info(f"📊 当前搜索配置:")
        logger.info(f"   最大岗位数: {search_config.get('max_jobs', 20)}")
        logger.info(f"   最大分析数: {search_config.get('max_analyze_jobs', 10)}")
        
        # 检查是否支持大规模抓取
        max_jobs = search_config.get('max_jobs', 20)
        if max_jobs >= 50:
            logger.info("✅ 配置支持大规模抓取")
        else:
            logger.warning(f"⚠️ 当前配置最大岗位数仅为 {max_jobs}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 配置测试失败: {e}")
        return False

def test_large_scale_crawler_import():
    """测试大规模爬虫导入"""
    logger.info("🏭 测试大规模爬虫模块导入...")
    
    try:
        from crawler.large_scale_crawler import LargeScaleCrawler, LargeScaleProgressTracker
        logger.info("✅ 大规模爬虫模块导入成功")
        
        from crawler.real_playwright_spider import RealPlaywrightBossSpider
        logger.info("✅ 真实Playwright爬虫模块导入成功")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    logger.info("🎯 Boss直聘大规模抓取优化快速测试")
    logger.info("=" * 50)
    
    tests = [
        ("配置更新", test_configuration_updates),
        ("模块导入", test_large_scale_crawler_import),
        ("AI岗位要求总结", test_job_requirement_summarizer),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 执行测试: {test_name}")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"❌ 测试 {test_name} 出错: {e}")
            results[test_name] = False
    
    # 总结
    logger.info("\n" + "=" * 50)
    logger.info("📊 测试结果总结:")
    
    success_count = sum(1 for result in results.values() if result)
    total_count = len(results)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"   {test_name}: {status}")
    
    logger.info(f"\n🎯 总体结果: {success_count}/{total_count} 测试通过")
    
    if success_count == total_count:
        logger.info("🎉 所有测试通过！大规模抓取优化功能就绪")
    else:
        logger.warning("⚠️ 部分测试失败，请检查相关功能")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏹️ 测试被用户中断")
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()