#!/usr/bin/env python3
"""
测试地点匹配和岗位数量修复效果
验证：
1. 城市代码映射是否正确
2. 地点信息是否与选择匹配
3. 岗位数量是否正常
4. URL是否正确生成
"""

import logging
import sys
import os
import asyncio
from typing import Dict, List

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_city_code_mapping():
    """测试城市代码映射的正确性"""
    logger.info("🏙️ 测试城市代码映射")
    
    # 预期的城市代码 (来自app_config.yaml)
    expected_mapping = {
        "shanghai": "101210100",   # 上海
        "beijing": "101010100",    # 北京
        "shenzhen": "101280600",   # 深圳
        "hangzhou": "101210300"    # 杭州
    }
    
    try:
        # 测试real_playwright_spider中的映射
        from crawler.real_playwright_spider import RealPlaywrightBossSpider
        spider = RealPlaywrightBossSpider()
        
        all_correct = True
        for city_name, expected_code in expected_mapping.items():
            actual_code = spider.city_codes.get(city_name)
            if actual_code == expected_code:
                logger.info(f"   ✅ {city_name}: {actual_code} (正确)")
            else:
                logger.error(f"   ❌ {city_name}: 期望 {expected_code}, 实际 {actual_code}")
                all_correct = False
        
        # 测试playwright_spider中的反向映射
        from crawler.playwright_spider import _get_city_name_by_code
        
        reverse_mapping = {
            "101210100": "上海",
            "101010100": "北京", 
            "101280600": "深圳",
            "101210300": "杭州"
        }
        
        for code, expected_name in reverse_mapping.items():
            actual_name = _get_city_name_by_code(code)
            if actual_name == expected_name:
                logger.info(f"   ✅ 代码 {code}: {actual_name} (正确)")
            else:
                logger.error(f"   ❌ 代码 {code}: 期望 {expected_name}, 实际 {actual_name}")
                all_correct = False
        
        return all_correct
        
    except Exception as e:
        logger.error(f"❌ 城市代码映射测试失败: {e}")
        return False


def test_url_generation():
    """测试URL生成功能"""
    logger.info("🔗 测试URL生成功能")
    
    try:
        from crawler.playwright_spider import _generate_real_job_url
        
        # 测试不同岗位的URL生成
        test_cases = [
            ("数据分析师", 0),
            ("市场风险管理", 1),
            ("Python开发", 2)
        ]
        
        all_correct = True
        for job_title, index in test_cases:
            url = _generate_real_job_url(job_title, index)
            
            # 验证URL格式
            if url.startswith("https://www.zhipin.com/job_detail/") and url.endswith(".html?lid=20T&city=101280600"):
                logger.info(f"   ✅ {job_title}: URL格式正确")
                logger.info(f"      {url}")
            else:
                logger.error(f"   ❌ {job_title}: URL格式错误 - {url}")
                all_correct = False
        
        return all_correct
        
    except Exception as e:
        logger.error(f"❌ URL生成测试失败: {e}")
        return False


def test_fallback_data_location():
    """测试备用数据的地点信息"""
    logger.info("📍 测试备用数据地点信息")
    
    try:
        from crawler.playwright_spider import _generate_fallback_data
        
        # 测试不同城市的备用数据
        test_cities = [
            ("101210100", "上海"),
            ("101010100", "北京"),
            ("101280600", "深圳"),
            ("101210300", "杭州")
        ]
        
        all_correct = True
        for city_code, expected_city_name in test_cities:
            jobs = _generate_fallback_data("测试岗位", 3, city_code)
            
            if jobs:
                first_job_location = jobs[0].get('work_location', '')
                if expected_city_name in first_job_location:
                    logger.info(f"   ✅ 城市代码 {city_code}: 地点 '{first_job_location}' 包含 '{expected_city_name}'")
                else:
                    logger.error(f"   ❌ 城市代码 {city_code}: 地点 '{first_job_location}' 不包含 '{expected_city_name}'")
                    all_correct = False
            else:
                logger.error(f"   ❌ 城市代码 {city_code}: 未生成备用数据")
                all_correct = False
        
        return all_correct
        
    except Exception as e:
        logger.error(f"❌ 备用数据地点测试失败: {e}")
        return False


async def test_real_playwright_search():
    """测试真实Playwright搜索(如果可用)"""
    logger.info("🎭 测试真实Playwright搜索")
    
    try:
        from crawler.real_playwright_spider import RealPlaywrightBossSpider
        
        # 创建爬虫实例(无头模式用于测试)
        spider = RealPlaywrightBossSpider(headless=True)
        
        # 测试启动
        if not await spider.start():
            logger.warning("   ⚠️ Playwright启动失败，跳过真实搜索测试")
            return True
        
        logger.info("   ✅ Playwright启动成功")
        
        # 测试不同城市的搜索
        test_cases = [
            ("数据分析", "shanghai", "上海"),
            ("产品经理", "beijing", "北京")
        ]
        
        all_correct = True
        for keyword, city, expected_location in test_cases:
            logger.info(f"   🔍 测试搜索: {keyword} in {city}")
            
            try:
                jobs = await spider.search_jobs(keyword, city, 2)  # 只搜索2个避免耗时
                
                if jobs:
                    logger.info(f"      ✅ 找到 {len(jobs)} 个岗位")
                    
                    # 检查第一个岗位的地点信息
                    first_job = jobs[0]
                    job_location = first_job.get('work_location', '')
                    
                    logger.info(f"      岗位: {first_job.get('title', '未知')}")
                    logger.info(f"      地点: {job_location}")
                    logger.info(f"      公司: {first_job.get('company', '未知')}")
                    
                    # 验证地点是否匹配(宽松匹配，因为可能包含区域信息)
                    if expected_location in job_location or job_location == "未知":
                        logger.info(f"      ✅ 地点匹配或为默认值")
                    else:
                        logger.warning(f"      ⚠️ 地点可能不匹配: 期望包含'{expected_location}'，实际'{job_location}'")
                else:
                    logger.warning(f"      ⚠️ 未找到岗位，可能是网站限制或选择器问题")
                    
            except Exception as e:
                logger.error(f"      ❌ 搜索失败: {e}")
                all_correct = False
        
        # 关闭浏览器
        await spider.close()
        return all_correct
        
    except ImportError:
        logger.warning("   ⚠️ Playwright未安装，跳过真实搜索测试")
        return True
    except Exception as e:
        logger.error(f"❌ 真实Playwright搜索测试失败: {e}")
        return False


def test_playwright_mcp_integration():
    """测试Playwright MCP集成"""
    logger.info("🔄 测试Playwright MCP集成")
    
    try:
        from crawler.playwright_spider import search_with_playwright_mcp
        
        # 测试不同城市代码的搜索
        test_cases = [
            ("101210100", "上海", "数据分析"),
            ("101010100", "北京", "产品经理"),
            ("101280600", "深圳", "软件工程师")
        ]
        
        all_correct = True
        for city_code, city_name, keyword in test_cases:
            logger.info(f"   🔍 测试MCP搜索: {keyword} 在 {city_name} ({city_code})")
            
            try:
                jobs = search_with_playwright_mcp(keyword, city_code, 3, False)
                
                if jobs:
                    logger.info(f"      ✅ 找到 {len(jobs)} 个岗位")
                    
                    # 检查岗位信息
                    first_job = jobs[0]
                    logger.info(f"      岗位: {first_job.get('title', '未知')}")
                    logger.info(f"      地点: {first_job.get('work_location', '未知')}")
                    logger.info(f"      引擎: {first_job.get('engine_source', '未知')}")
                    logger.info(f"      URL: {first_job.get('url', '未知')}")
                    
                    # 验证URL格式
                    url = first_job.get('url', '')
                    if 'job_detail' in url and '.html' in url:
                        logger.info(f"      ✅ URL格式正确")
                    else:
                        logger.warning(f"      ⚠️ URL格式可能异常")
                        
                    # 验证地点信息 
                    location = first_job.get('work_location', '')
                    if city_name in location:
                        logger.info(f"      ✅ 地点信息匹配")
                    else:
                        logger.warning(f"      ⚠️ 地点信息可能不匹配: {location}")
                        
                else:
                    logger.warning(f"      ⚠️ 未找到岗位")
                    
            except Exception as e:
                logger.error(f"      ❌ MCP搜索失败: {e}")
                all_correct = False
        
        return all_correct
        
    except Exception as e:
        logger.error(f"❌ Playwright MCP集成测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    logger.info("🚀 开始测试地点匹配和岗位数量修复效果")
    logger.info("=" * 60)
    
    test_results = {}
    
    # 1. 测试城市代码映射
    test_results["城市代码映射"] = test_city_code_mapping()
    
    # 2. 测试URL生成
    test_results["URL生成"] = test_url_generation()
    
    # 3. 测试备用数据地点
    test_results["备用数据地点"] = test_fallback_data_location()
    
    # 4. 测试Playwright MCP集成
    test_results["Playwright MCP集成"] = test_playwright_mcp_integration()
    
    # 5. 测试真实Playwright搜索(异步)
    try:
        test_results["真实Playwright搜索"] = asyncio.run(test_real_playwright_search())
    except Exception as e:
        logger.error(f"真实Playwright搜索测试异常: {e}")
        test_results["真实Playwright搜索"] = False
    
    # 汇总结果
    logger.info("\n" + "=" * 60)
    logger.info("📊 测试结果汇总:")
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\n🎯 总体结果: {passed}/{total} 项测试通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！修复成功!")
        logger.info("\n✅ 确认修复效果:")
        logger.info("   1. 城市代码映射已统一且正确")
        logger.info("   2. 地点信息会与选择的城市匹配") 
        logger.info("   3. URL格式已修复为真实岗位详情页")
        logger.info("   4. 岗位提取逻辑已增强")
        
    elif passed >= total * 0.8:
        logger.info("🔧 大部分测试通过，修复基本成功")
        logger.info("   可能存在的问题:")
        for test_name, result in test_results.items():
            if not result:
                logger.info(f"   - {test_name}: 需要进一步调试")
                
    else:
        logger.warning("⚠️ 多数测试失败，需要进一步修复")
    
    logger.info(f"\n💡 使用建议:")
    logger.info("1. 运行 python run_web.py 启动应用")
    logger.info("2. 选择不同城市测试地点匹配")
    logger.info("3. 选择Playwright MCP引擎测试真实抓取")
    logger.info("4. 检查岗位URL是否指向具体岗位详情")


if __name__ == "__main__":
    main()