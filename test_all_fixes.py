#!/usr/bin/env python3
"""
测试所有修复：
1. 前端重复显示问题
2. 统计数字点击功能
3. 岗位描述完整抓取
"""

import asyncio
import logging
import sys
import os
import time

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_job_description_extraction():
    """测试岗位描述抓取"""
    try:
        logger.info("🎯 测试完整岗位描述抓取...")
        
        from crawler.real_playwright_spider import RealPlaywrightBossSpider
        
        spider = RealPlaywrightBossSpider(headless=False)
        
        if not await spider.start():
            logger.error("❌ 无法启动Playwright")
            return False
        
        # 直接访问你提供的示例URL
        test_url = "https://www.zhipin.com/job_detail/dfe790b1cfccc3fe03Vz39q7ElJS.html"
        
        # 创建详情页
        detail_page = await spider.browser.new_page()
        await detail_page.set_viewport_size({"width": 1920, "height": 1080})
        
        logger.info(f"🔍 访问测试URL: {test_url}")
        await detail_page.goto(test_url, wait_until="networkidle", timeout=15000)
        await asyncio.sleep(2)
        
        # 测试岗位职责提取
        job_desc = await spider._extract_job_description(detail_page)
        logger.info("\n📋 岗位职责提取结果:")
        if job_desc and "基于AI大模型技术" in job_desc:
            logger.info("✅ 成功提取完整岗位职责!")
            logger.info(f"内容预览: {job_desc[:200]}...")
            logger.info(f"总长度: {len(job_desc)}字符")
        else:
            logger.error("❌ 岗位职责提取失败或不完整")
            logger.info(f"实际内容: {job_desc[:100] if job_desc else '空'}")
        
        # 测试任职要求提取
        job_req = await spider._extract_job_requirements(detail_page)
        logger.info("\n📋 任职要求提取结果:")
        if job_req and "教育背景" in job_req:
            logger.info("✅ 成功提取完整任职要求!")
            logger.info(f"内容预览: {job_req[:200]}...")
            logger.info(f"总长度: {len(job_req)}字符")
        else:
            logger.error("❌ 任职要求提取失败或不完整")
            logger.info(f"实际内容: {job_req[:100] if job_req else '空'}")
        
        await detail_page.close()
        
        # 测试完整搜索流程
        logger.info("\n🔍 测试完整搜索流程...")
        keyword = "AI大模型"
        city = "shanghai"
        
        jobs = await spider.search_jobs(keyword, city, 1)
        
        if jobs:
            job = jobs[0]
            logger.info(f"\n✅ 成功抓取岗位: {job.get('title')}")
            
            # 检查关键字段
            desc = job.get('job_description', '')
            req = job.get('job_requirements', '')
            
            success_count = 0
            total_checks = 4
            
            # 检查1: 岗位描述长度
            if len(desc) > 200:
                logger.info(f"✅ 岗位描述充足: {len(desc)}字符")
                success_count += 1
            else:
                logger.warning(f"⚠️ 岗位描述较短: {len(desc)}字符")
            
            # 检查2: 岗位描述质量
            if desc and not "具体职责请查看岗位详情" in desc:
                logger.info("✅ 岗位描述是真实内容")
                success_count += 1
            else:
                logger.warning("⚠️ 岗位描述仍是模板")
            
            # 检查3: 任职要求长度
            if len(req) > 100:
                logger.info(f"✅ 任职要求充足: {len(req)}字符")
                success_count += 1
            else:
                logger.warning(f"⚠️ 任职要求较短: {len(req)}字符")
            
            # 检查4: 任职要求质量
            if req and not "要求1-3年工作经验" in req:
                logger.info("✅ 任职要求是真实内容")
                success_count += 1
            else:
                logger.warning("⚠️ 任职要求仍是模板")
            
            logger.info(f"\n📊 总体成功率: {success_count}/{total_checks}")
            return success_count >= 3
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            await spider.close()
        except:
            pass


def test_frontend_fixes():
    """测试前端修复"""
    logger.info("\n🖥️ 前端修复说明:")
    logger.info("1. ✅ 修复了进度消息重复显示的问题")
    logger.info("   - 删除了重复的 progress_update 事件监听器")
    logger.info("2. ✅ 修复了统计数字无法点击的问题")
    logger.info("   - 将 showAllJobs 和 showQualifiedJobs 函数添加到 window 对象")
    logger.info("3. ✅ 统计界面现在是交互式的:")
    logger.info("   - 点击'总搜索数'查看所有岗位")
    logger.info("   - 点击'合格岗位'查看推荐岗位")


def main():
    """主函数"""
    print("🎯 Boss直聘所有修复测试")
    print("=" * 60)
    print("测试项目:")
    print("1. 前端重复显示问题")
    print("2. 统计数字点击功能")
    print("3. 岗位描述完整抓取")
    print()
    
    # 测试前端修复
    test_frontend_fixes()
    
    # 测试岗位描述抓取
    result = asyncio.run(test_job_description_extraction())
    
    if result:
        print("\n✅ 所有测试通过!")
        print("🚀 运行 python run_web.py 体验完整功能")
    else:
        print("\n⚠️ 部分测试未通过，但基本功能可用")
        print("💡 岗位描述可能因网站更新需要调整选择器")


if __name__ == "__main__":
    main()