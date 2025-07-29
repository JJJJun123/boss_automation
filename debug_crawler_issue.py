#!/usr/bin/env python3
"""
诊断爬虫抓取失败问题
测试Boss直聘页面结构变化
"""

import asyncio
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def debug_boss_page_structure():
    """调试Boss直聘页面结构"""
    playwright = await async_playwright().start()
    
    try:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # 测试搜索URL
        keyword = "金融AI解决方案"
        city_code = "101020100"  # 上海
        search_url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city_code}"
        
        logger.info(f"🌐 导航到: {search_url}")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        
        # 等待页面加载
        await asyncio.sleep(8)
        
        # 截图保存
        screenshot_path = "debug_boss_page.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        logger.info(f"📸 已截图: {screenshot_path}")
        
        # 获取页面标题
        title = await page.title()
        logger.info(f"📄 页面标题: {title}")
        
        # 测试当前的岗位容器选择器
        selectors_to_test = [
            'li:has(a[href*="job_detail"])',  # 最精确：包含岗位链接的li
            '.job-detail-box',                # Boss直聘特有
            'a[ka*="search_list"]',           # ka属性标识
            '.job-card-wrapper', 
            '.job-card-container',
            'li.job-card-container', 
            '.job-card-left', 
            '.job-info-box', 
            '.job-list-box .job-card-body',
            'li[class*="job"]', 
            'div[class*="job-card"]',
            '.job-primary', 
            '.job-content',
            # 新增可能的选择器
            '.job-card',
            '[data-jobid]',
            '.job-item',
            '.search-job-result',
            'li[data-jid]',
            'div[data-jobid]'
        ]
        
        logger.info("🔍 测试岗位容器选择器...")
        
        found_selectors = []
        for selector in selectors_to_test:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    visible_count = 0
                    for element in elements[:3]:  # 只测试前3个
                        if await element.is_visible():
                            visible_count += 1
                    
                    if visible_count > 0:
                        found_selectors.append((selector, len(elements), visible_count))
                        logger.info(f"✅ 找到: {selector} - 总数: {len(elements)}, 可见: {visible_count}")
                    else:
                        logger.debug(f"❌ 不可见: {selector} - 总数: {len(elements)}")
                else:
                    logger.debug(f"❌ 未找到: {selector}")
            except Exception as e:
                logger.debug(f"❌ 错误: {selector} - {e}")
        
        if not found_selectors:
            logger.error("❌ 所有选择器都失败了！")
            
            # 尝试分析页面内容
            logger.info("🔍 分析页面内容...")
            
            # 检查是否有登录要求
            login_elements = await page.query_selector_all('a[href*="login"], .login-btn, button:has-text("登录")')
            if login_elements:
                logger.warning("⚠️ 检测到登录元素，可能需要登录")
            
            # 检查是否有验证码
            captcha_elements = await page.query_selector_all('.captcha, .verify-wrap, [class*="captcha"]')
            if captcha_elements:
                logger.warning("⚠️ 检测到verification码")
            
            # 检查是否有错误页面
            error_elements = await page.query_selector_all('.error-page, .not-found, .empty-result')
            if error_elements:
                logger.warning("⚠️ 检测到错误页面")
            
            # 获取页面上所有的li元素（可能的岗位容器）
            all_li = await page.query_selector_all('li')
            logger.info(f"📊 页面共有 {len(all_li)} 个li元素")
            
            # 获取页面上所有包含job关键词的元素
            job_related = await page.query_selector_all('*[class*="job"], *[id*="job"], *[data*="job"]')
            logger.info(f"📊 页面共有 {len(job_related)} 个job相关元素")
            
            # 保存页面HTML用于分析
            html_content = await page.content()
            with open("debug_boss_page.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info("📄 已保存页面HTML: debug_boss_page.html")
        
        else:
            logger.info(f"🎯 找到 {len(found_selectors)} 个有效选择器")
            
            # 测试最佳选择器的数据提取
            best_selector = found_selectors[0][0]
            logger.info(f"🧪 测试最佳选择器: {best_selector}")
            
            elements = await page.query_selector_all(best_selector)
            for i, element in enumerate(elements[:3]):
                try:
                    text = await element.inner_text()
                    logger.info(f"元素 {i+1}: {text[:100]}...")
                except:
                    logger.info(f"元素 {i+1}: 无法获取文本")
        
        # 等待用户查看
        logger.info("🕐 等待10秒用于检查...")
        await asyncio.sleep(10)
        
    except Exception as e:
        logger.error(f"❌ 调试过程出错: {e}")
    
    finally:
        await browser.close()
        await playwright.stop()


async def main():
    """主函数"""
    print("🚀 开始调试Boss直聘爬虫问题")
    print("这将打开浏览器窗口并分析页面结构")
    
    await debug_boss_page_structure()
    
    print("✅ 调试完成，请查看生成的截图和HTML文件")


if __name__ == "__main__":
    asyncio.run(main())