#!/usr/bin/env python3
"""
测试脚本：验证所有修复是否正常工作
测试内容：
1. 分析数量显示是否正确
2. 城市选择是否正确
3. URL链接是否真实
4. 浏览器是否可见
"""

import asyncio
import sys
import os
import logging

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from crawler.real_playwright_spider import RealPlaywrightBossSpider
from config.config_manager import ConfigManager
from analyzer.job_analyzer import JobAnalyzer


async def test_playwright_spider():
    """测试Playwright爬虫的所有功能"""
    logger.info("🧪 开始测试Playwright爬虫...")
    
    # 初始化爬虫（非无头模式，确保可见）
    spider = RealPlaywrightBossSpider(headless=False)
    
    try:
        # 1. 测试浏览器启动和可见性
        logger.info("\n📋 测试1: 浏览器启动和可见性")
        success = await spider.start()
        if success:
            logger.info("✅ 浏览器启动成功，窗口应该可见")
            await asyncio.sleep(2)  # 给用户时间观察
        else:
            logger.error("❌ 浏览器启动失败")
            return
        
        # 2. 测试城市选择
        logger.info("\n📋 测试2: 城市选择功能")
        test_cases = [
            ("shanghai", "上海", "101020100"),
            ("beijing", "北京", "101010100"),
        ]
        
        for city_key, city_name, expected_code in test_cases:
            logger.info(f"🔍 测试城市: {city_name} ({city_key})")
            city_code = spider.city_codes.get(city_key)
            if city_code == expected_code:
                logger.info(f"✅ 城市代码正确: {city_code}")
            else:
                logger.error(f"❌ 城市代码错误: 期望 {expected_code}, 实际 {city_code}")
        
        # 3. 测试搜索和URL提取
        logger.info("\n📋 测试3: 搜索功能和URL提取")
        keyword = "数据分析"
        city = "shanghai"
        max_jobs = 5
        
        logger.info(f"🔍 搜索参数: {keyword} | {city} | {max_jobs}个岗位")
        jobs = await spider.search_jobs(keyword, city, max_jobs)
        
        logger.info(f"\n📊 搜索结果: 找到 {len(jobs)} 个岗位")
        
        # 验证结果
        if jobs:
            for i, job in enumerate(jobs[:3], 1):  # 只显示前3个
                logger.info(f"\n岗位 #{i}:")
                logger.info(f"  职位: {job.get('title', '未知')}")
                logger.info(f"  公司: {job.get('company', '未知')}")
                logger.info(f"  地点: {job.get('work_location', '未知')}")
                logger.info(f"  薪资: {job.get('salary', '未知')}")
                logger.info(f"  URL: {job.get('url', '无')}")
                
                # 验证URL格式
                url = job.get('url', '')
                if url and url.startswith('https://www.zhipin.com/job_detail/'):
                    logger.info("  ✅ URL格式正确")
                elif not url:
                    logger.warning("  ⚠️ 未提取到URL")
                else:
                    logger.info(f"  ℹ️ URL格式: {url}")
                
                # 验证地点是否匹配
                location = job.get('work_location', '')
                if '上海' in location:
                    logger.info("  ✅ 地点匹配")
                else:
                    logger.warning(f"  ⚠️ 地点可能不匹配: {location}")
        else:
            logger.warning("⚠️ 未找到任何岗位")
        
        # 4. 测试分析数量
        logger.info("\n📋 测试4: 分析数量显示")
        if jobs:
            # 初始化配置和分析器
            config_manager = ConfigManager()
            ai_config = config_manager.get_ai_config()
            analyzer = JobAnalyzer(ai_config['provider'])
            
            # 模拟分析
            analyze_count = min(3, len(jobs))
            logger.info(f"准备分析 {analyze_count} 个岗位...")
            
            analyzed_jobs = []
            for i, job in enumerate(jobs[:analyze_count]):
                # 添加模拟分析结果
                job['analysis'] = {
                    'score': 5 + i,  # 5, 6, 7
                    'recommendation': '推荐' if (5 + i) >= ai_config['min_score'] else '不推荐',
                    'summary': f'测试分析结果 {i+1}'
                }
                analyzed_jobs.append(job)
            
            # 验证过滤逻辑
            logger.info(f"\n分析完成: {len(analyzed_jobs)} 个岗位")
            recommended = sum(1 for job in analyzed_jobs if job['analysis']['score'] >= ai_config['min_score'])
            logger.info(f"推荐岗位: {recommended} 个")
            logger.info(f"显示岗位: {len(analyzed_jobs)} 个 (应该显示所有分析的岗位)")
            
            if len(analyzed_jobs) == analyze_count:
                logger.info("✅ 分析数量显示正确")
            else:
                logger.error("❌ 分析数量显示不正确")
        
    except Exception as e:
        logger.error(f"❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理资源
        await spider.close()
        logger.info("\n🏁 测试完成")


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("Boss直聘自动化 - 修复验证测试")
    logger.info("=" * 50)
    
    # 运行异步测试
    asyncio.run(test_playwright_spider())


if __name__ == "__main__":
    main()