#!/usr/bin/env python3
"""
调试城市搜索问题
验证为什么选择上海却得到杭州岗位
"""

import asyncio
import logging
import sys
import os
import urllib.parse

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def debug_city_search():
    """调试城市搜索"""
    try:
        from crawler.real_playwright_spider import RealPlaywrightBossSpider
        
        logger.info("🔍 开始调试城市搜索问题...")
        
        # 创建爬虫实例（可见模式，便于观察）
        spider = RealPlaywrightBossSpider(headless=False)
        
        if not await spider.start():
            logger.error("❌ 无法启动Playwright")
            return
        
        # 测试不同城市的搜索URL
        test_cases = [
            ("上海", "shanghai", "101210100"),
            ("杭州", "hangzhou", "101210300"),
        ]
        
        keyword = "数据分析"
        
        for city_name, city_key, expected_code in test_cases:
            logger.info(f"\n{'='*50}")
            logger.info(f"🏙️ 测试城市: {city_name} ({city_key})")
            
            # 获取城市代码
            actual_code = spider.city_codes.get(city_key, "unknown")
            logger.info(f"   预期代码: {expected_code}")
            logger.info(f"   实际代码: {actual_code}")
            
            if actual_code != expected_code:
                logger.error(f"   ❌ 城市代码不匹配！")
                continue
            
            # 构建搜索URL
            encoded_keyword = urllib.parse.quote(keyword)
            search_url = f"https://www.zhipin.com/web/geek/job?query={encoded_keyword}&city={actual_code}"
            
            logger.info(f"🌐 访问URL: {search_url}")
            await spider.page.goto(search_url, wait_until="domcontentloaded")
            
            # 等待页面加载
            await asyncio.sleep(5)
            
            # 检查页面URL（可能有重定向）
            current_url = spider.page.url
            logger.info(f"📍 当前页面URL: {current_url}")
            
            # 检查URL中的城市参数
            if f"city={actual_code}" in current_url:
                logger.info("   ✅ URL中包含正确的城市代码")
            else:
                logger.warning("   ⚠️ URL中的城市代码可能被修改了")
            
            # 检查页面标题和城市信息
            try:
                page_title = await spider.page.title()
                logger.info(f"📄 页面标题: {page_title}")
                
                # 寻找城市选择器元素
                city_selector_elem = await spider.page.query_selector('.city-label, .selected-city, [class*="city"]')
                if city_selector_elem:
                    city_text = await city_selector_elem.inner_text()
                    logger.info(f"🏙️ 页面显示城市: {city_text}")
                    if city_name in city_text:
                        logger.info("   ✅ 页面城市匹配")
                    else:
                        logger.warning(f"   ⚠️ 页面城市不匹配: {city_text}")
                else:
                    logger.warning("   ⚠️ 未找到城市选择器元素")
                
                # 查看前几个岗位的地点信息
                logger.info("🔍 分析前3个岗位的地点信息:")
                
                job_cards = await spider.page.query_selector_all('.job-list-container li')[:3]
                
                for i, card in enumerate(job_cards):
                    try:
                        # 获取岗位标题
                        title_elem = await card.query_selector('.job-name, .job-title')
                        title = await title_elem.inner_text() if title_elem else "未知标题"
                        
                        # 获取地点信息
                        location_selectors = ['.job-area', '.area-district', '.job-location']
                        location = "未知地点"
                        for selector in location_selectors:
                            loc_elem = await card.query_selector(selector)
                            if loc_elem:
                                location = await loc_elem.inner_text()
                                if location.strip():
                                    break
                        
                        logger.info(f"   岗位{i+1}: {title} | 地点: {location}")
                        
                        # 分析地点是否匹配
                        if city_name in location or city_name in title:
                            logger.info(f"      ✅ 包含目标城市: {city_name}")
                        elif any(other_city in location for other_city in ["杭州", "上海", "北京", "深圳"]):
                            logger.warning(f"      ⚠️ 包含其他城市，可能是跨城市岗位")
                        else:
                            logger.warning(f"      ❓ 地点信息不明确")
                            
                    except Exception as e:
                        logger.warning(f"   岗位{i+1}分析失败: {e}")
                        
            except Exception as e:
                logger.warning(f"页面分析失败: {e}")
            
            # 等待观察
            logger.info("⏳ 等待5秒，可以观察浏览器中的结果...")
            await asyncio.sleep(5)
        
        # 关闭浏览器
        await spider.close()
        
        logger.info("✅ 城市搜索调试完成")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 调试过程失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("🔍 Boss直聘城市搜索调试工具")
    print("=" * 50)
    
    success = asyncio.run(debug_city_search())
    
    if success:
        print("\n✅ 调试完成")
        print("💡 请观察上述输出，查看城市搜索的实际行为")
    else:
        print("\n❌ 调试失败，请检查错误信息")


if __name__ == "__main__":
    main()