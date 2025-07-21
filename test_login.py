#!/usr/bin/env python3
"""
测试Playwright爬虫的登录功能
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


async def test_login_and_search():
    """测试登录和搜索功能"""
    logger.info("🧪 开始测试Playwright爬虫登录功能...")
    
    # 初始化爬虫（非无头模式，确保可见）
    spider = RealPlaywrightBossSpider(headless=False)
    
    try:
        # 1. 启动浏览器
        logger.info("\n📋 步骤1: 启动浏览器")
        success = await spider.start()
        if not success:
            logger.error("❌ 浏览器启动失败")
            return
        
        logger.info("✅ 浏览器启动成功")
        
        # 2. 搜索岗位（会自动触发登录流程）
        logger.info("\n📋 步骤2: 开始搜索岗位（将自动检测并处理登录）")
        
        keyword = "数据分析"
        city = "shanghai"
        max_jobs = 10  # 登录后应该能获取更多岗位
        
        logger.info(f"🔍 搜索参数: {keyword} | {city} | {max_jobs}个岗位")
        jobs = await spider.search_jobs(keyword, city, max_jobs)
        
        # 3. 验证结果
        logger.info(f"\n📊 搜索结果: 找到 {len(jobs)} 个岗位")
        
        if len(jobs) == 0:
            logger.error("❌ 未找到任何岗位，可能登录或搜索失败")
        elif len(jobs) < 5:
            logger.warning(f"⚠️ 只找到 {len(jobs)} 个岗位，可能存在问题")
        else:
            logger.info(f"✅ 成功找到 {len(jobs)} 个岗位，登录和搜索功能正常")
        
        # 显示前3个岗位信息
        for i, job in enumerate(jobs[:3], 1):
            logger.info(f"\n岗位 #{i}:")
            logger.info(f"  职位: {job.get('title', '未知')}")
            logger.info(f"  公司: {job.get('company', '未知')}")
            logger.info(f"  地点: {job.get('work_location', '未知')}")
            logger.info(f"  薪资: {job.get('salary', '未知')}")
            
            # 验证URL
            url = job.get('url', '')
            if url and url.startswith('https://www.zhipin.com/job_detail/'):
                logger.info(f"  URL: {url[:80]}...")
            else:
                logger.warning(f"  URL: {url or '无'}")
        
        # 4. 测试cookies保存
        logger.info("\n📋 步骤3: 验证cookies保存")
        cookies_file = os.path.join(os.path.dirname(__file__), 'crawler', 'cookies', 'boss_cookies.json')
        if os.path.exists(cookies_file):
            logger.info(f"✅ Cookies文件已保存: {cookies_file}")
            # 获取文件大小
            file_size = os.path.getsize(cookies_file)
            logger.info(f"  文件大小: {file_size} 字节")
        else:
            logger.warning("⚠️ 未找到cookies文件")
        
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
    logger.info("Boss直聘自动化 - 登录功能测试")
    logger.info("=" * 50)
    logger.info("\n说明:")
    logger.info("1. 程序会自动打开浏览器")
    logger.info("2. 如果是首次运行，需要手动登录Boss直聘")
    logger.info("3. 登录成功后，cookies会被保存")
    logger.info("4. 下次运行时会自动使用保存的cookies")
    logger.info("=" * 50)
    
    # 运行异步测试
    asyncio.run(test_login_and_search())


if __name__ == "__main__":
    main()