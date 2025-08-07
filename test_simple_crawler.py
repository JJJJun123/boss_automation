#!/usr/bin/env python3
"""
简单的爬虫连接测试
测试是否能正常访问Boss直聘网站
"""

import asyncio
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_basic_connection():
    """测试基本的网站连接"""
    print("🧪 测试1: 基本连接测试")
    print("="*60)
    
    playwright = await async_playwright().start()
    browser = None
    
    try:
        # 启动浏览器（有头模式，方便调试）
        print("🚀 启动浏览器...")
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--start-maximized'
            ]
        )
        
        # 创建上下文
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # 创建页面
        page = await context.new_page()
        
        # 1. 先测试访问百度（验证网络是否正常）
        print("\n📍 测试访问百度...")
        try:
            await page.goto('https://www.baidu.com', timeout=10000)
            print("✅ 百度访问成功，网络正常")
        except Exception as e:
            print(f"❌ 百度访问失败: {e}")
            return False
        
        # 2. 测试访问Boss直聘首页
        print("\n📍 测试访问Boss直聘首页...")
        try:
            await page.goto('https://www.zhipin.com', timeout=30000, wait_until='domcontentloaded')
            print("✅ Boss直聘首页访问成功")
            
            # 截图保存
            await page.screenshot(path='boss_homepage.png')
            print("📸 已保存首页截图: boss_homepage.png")
            
        except Exception as e:
            print(f"❌ Boss直聘首页访问失败: {e}")
            return False
        
        # 3. 测试搜索页面
        print("\n📍 测试访问搜索页面...")
        search_url = 'https://www.zhipin.com/web/geek/job?query=Python&city=101020100'
        try:
            await page.goto(search_url, timeout=30000, wait_until='domcontentloaded')
            print("✅ 搜索页面访问成功")
            
            # 等待一下看是否有内容加载
            await page.wait_for_timeout(3000)
            
            # 检查是否有登录提示
            login_modal = await page.query_selector('.dialog-container')
            if login_modal:
                print("⚠️ 检测到登录弹窗")
                # 尝试关闭
                close_btn = await page.query_selector('.dialog-container .close')
                if close_btn:
                    await close_btn.click()
                    print("✅ 已关闭登录弹窗")
            
            # 检查是否有职位列表
            job_cards = await page.query_selector_all('.job-card-wrapper')
            print(f"📊 找到 {len(job_cards)} 个职位卡片")
            
            # 截图保存
            await page.screenshot(path='boss_search.png')
            print("📸 已保存搜索页截图: boss_search.png")
            
        except Exception as e:
            print(f"❌ 搜索页面访问失败: {e}")
            return False
        
        # 4. 测试是否需要验证码
        print("\n📍 检查是否有验证码...")
        captcha = await page.query_selector('.verifyimg')
        if captcha:
            print("⚠️ 检测到验证码，可能需要人工处理")
        else:
            print("✅ 未检测到验证码")
        
        print("\n✅ 所有测试通过！")
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        return False
        
    finally:
        if browser:
            await browser.close()
        await playwright.stop()


async def test_with_different_options():
    """测试不同的页面加载选项"""
    print("\n🧪 测试2: 不同加载选项测试")
    print("="*60)
    
    playwright = await async_playwright().start()
    browser = None
    
    try:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 测试不同的wait_until选项
        options = ['load', 'domcontentloaded', 'networkidle']
        
        for option in options:
            print(f"\n📍 测试 wait_until='{option}'...")
            try:
                start_time = asyncio.get_event_loop().time()
                await page.goto(
                    'https://www.zhipin.com/web/geek/job?query=Python&city=101020100',
                    timeout=30000,
                    wait_until=option
                )
                duration = asyncio.get_event_loop().time() - start_time
                print(f"✅ 成功，耗时: {duration:.2f}秒")
            except Exception as e:
                print(f"❌ 失败: {e}")
        
    finally:
        if browser:
            await browser.close()
        await playwright.stop()


async def main():
    """主测试函数"""
    print("🚀 Boss直聘爬虫连接测试")
    print("="*60)
    
    # 运行基本连接测试
    success = await test_basic_connection()
    
    if success:
        # 如果基本测试通过，运行更多测试
        await test_with_different_options()
    
    print("\n✅ 测试完成！")
    
    if success:
        print("\n💡 建议:")
        print("1. 爬虫可以正常访问Boss直聘")
        print("2. 建议使用 wait_until='domcontentloaded' 加快加载速度")
        print("3. 需要处理可能出现的登录弹窗")
        print("4. 检查截图文件了解页面实际情况")
    else:
        print("\n⚠️ 连接失败，可能的原因:")
        print("1. 网络问题")
        print("2. IP被限制")
        print("3. 需要更换User-Agent")
        print("4. 需要使用代理")


if __name__ == "__main__":
    asyncio.run(main())