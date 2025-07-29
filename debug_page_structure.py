#!/usr/bin/env python3
"""
调试Boss直聘页面结构，找出正确的选择器
"""

import asyncio
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def debug_page_structure():
    """调试页面结构"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            # 访问Boss直聘
            url = "https://www.zhipin.com/web/geek/job?query=数据分析&city=101020100"
            logger.info(f"访问: {url}")
            await page.goto(url)
            await page.wait_for_timeout(5000)
            
            # 保存页面截图
            await page.screenshot(path="debug_boss_page.png", full_page=True)
            logger.info("已保存页面截图: debug_boss_page.png")
            
            # 保存页面HTML
            content = await page.content()
            with open("debug_boss_page.html", "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("已保存页面HTML: debug_boss_page.html")
            
            # 测试不同的选择器
            selectors_to_test = [
                # 岗位容器
                'li.job-card-wrapper',
                '.job-list-box li',
                'ul.job-list-box > li',
                '[class*="job-card"]',
                'a[ka="search_list"]',
                
                # 岗位标题
                '.job-title',
                '.job-name',
                'span.job-name',
                
                # 公司名称
                '.company-name',
                '.company-text h3',
                
                # 薪资
                '.salary',
                'span.salary',
                
                # 地点
                '.job-area',
                'span.job-area'
            ]
            
            logger.info("\n测试选择器:")
            for selector in selectors_to_test:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        logger.info(f"✅ {selector}: 找到 {len(elements)} 个元素")
                        # 获取第一个元素的文本作为示例
                        if len(elements) > 0:
                            text = await elements[0].inner_text()
                            logger.info(f"   示例文本: {text[:50]}...")
                    else:
                        logger.info(f"❌ {selector}: 未找到元素")
                except Exception as e:
                    logger.error(f"❌ {selector}: 错误 - {e}")
            
            # 等待用户查看
            logger.info("\n请查看浏览器窗口，按Ctrl+C结束...")
            await page.wait_for_timeout(300000)  # 5分钟
            
        except KeyboardInterrupt:
            logger.info("用户中断")
        except Exception as e:
            logger.error(f"错误: {e}")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_page_structure())