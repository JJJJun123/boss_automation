#!/usr/bin/env python3
"""
调试重复岗位问题
深入分析为什么会抓取到重复的岗位
"""

import asyncio
import logging
import sys
import os
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def debug_duplicate_issue():
    """调试重复岗位问题"""
    try:
        from crawler.real_playwright_spider import RealPlaywrightBossSpider
        
        logger.info("🔍 开始调试重复岗位问题...")
        
        spider = RealPlaywrightBossSpider(headless=False)
        
        if not await spider.start():
            logger.error("❌ 无法启动Playwright")
            return
        
        # 搜索测试
        keyword = "市场风险管理"
        city = "shanghai"
        city_code = spider.city_codes.get(city, "101020100")
        search_url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city_code}"
        
        logger.info(f"🌐 访问: {search_url}")
        await spider.page.goto(search_url, wait_until="domcontentloaded")
        await asyncio.sleep(8)
        
        # 处理弹窗
        try:
            await asyncio.sleep(2)
        except:
            pass
        
        # 滚动加载
        await spider.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(3)
        
        logger.info("🔍 分析页面中的岗位元素去重问题...")
        
        # 使用我们的主要选择器
        selector = 'li:has(a[href*="job_detail"])'
        elements = await spider.page.query_selector_all(selector)
        
        logger.info(f"📊 找到 {len(elements)} 个岗位元素")
        
        # 分析前10个元素的详细信息
        unique_jobs = {}  # 用于检测重复
        element_analysis = []
        
        for i, elem in enumerate(elements[:10]):
            try:
                # 获取岗位链接
                link_elem = await elem.query_selector('a[href*="job_detail"]')
                href = ""
                if link_elem:
                    href = await link_elem.get_attribute('href')
                    if href:
                        # 清理链接（移除查询参数）
                        if '?' in href:
                            href_clean = href.split('?')[0]
                        else:
                            href_clean = href
                
                # 获取岗位标题
                title_elem = await elem.query_selector('.job-name')
                title = ""
                if title_elem:
                    title = await title_elem.inner_text()
                
                # 获取元素的位置信息
                bbox = await elem.bounding_box()
                
                # 获取元素的完整文本
                elem_text = await elem.inner_text()
                
                analysis = {
                    "index": i+1,
                    "title": title.strip() if title else "未找到",
                    "href": href,
                    "href_clean": href_clean if href else "未找到",
                    "position": bbox,
                    "text_preview": elem_text[:100] if elem_text else "无文本",
                    "text_length": len(elem_text) if elem_text else 0
                }
                
                element_analysis.append(analysis)
                
                # 检查重复
                if href_clean:
                    if href_clean in unique_jobs:
                        unique_jobs[href_clean]['duplicates'].append(i+1)
                        logger.warning(f"🔄 发现重复岗位 {i+1}: {title} -> {href_clean}")
                    else:
                        unique_jobs[href_clean] = {
                            'title': title,
                            'first_index': i+1,
                            'duplicates': []
                        }
                        logger.info(f"✅ 新岗位 {i+1}: {title} -> {href_clean}")
                
            except Exception as e:
                logger.error(f"❌ 分析元素 {i+1} 失败: {e}")
        
        # 保存分析结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        analysis_path = f"duplicate_analysis_{timestamp}.json"
        
        result = {
            "total_elements": len(elements),
            "analyzed_elements": len(element_analysis),
            "unique_jobs": len(unique_jobs),
            "duplicate_summary": {},
            "element_details": element_analysis
        }
        
        # 分析重复情况
        for href, info in unique_jobs.items():
            if info['duplicates']:
                result["duplicate_summary"][href] = {
                    "title": info['title'],
                    "first_index": info['first_index'],
                    "duplicate_indexes": info['duplicates'],
                    "total_occurrences": 1 + len(info['duplicates'])
                }
        
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📊 分析报告:")
        logger.info(f"   总元素数: {len(elements)}")
        logger.info(f"   唯一岗位数: {len(unique_jobs)}")
        logger.info(f"   重复岗位数: {len(result['duplicate_summary'])}")
        
        if result['duplicate_summary']:
            logger.info(f"\n🔄 重复岗位详情:")
            for href, info in result['duplicate_summary'].items():
                logger.info(f"   {info['title']}: 出现在位置 {info['first_index']} 和 {info['duplicate_indexes']}")
        
        # 截图保存
        screenshot_path = f"duplicate_debug_{timestamp}.png"
        await spider.page.screenshot(path=screenshot_path)
        
        logger.info(f"📁 生成文件:")
        logger.info(f"   分析报告: {analysis_path}")
        logger.info(f"   页面截图: {screenshot_path}")
        
        await spider.close()
        
        # 给出修复建议
        logger.info(f"\n💡 修复建议:")
        if len(unique_jobs) < len(elements) // 2:
            logger.warning("⚠️ 大量重复元素，建议:")
            logger.warning("   1. 检查选择器是否选中了嵌套元素")
            logger.warning("   2. 添加更严格的去重逻辑")
            logger.warning("   3. 可能需要分析DOM结构调整选择器")
        else:
            logger.info("✅ 重复情况较少，主要优化去重逻辑即可")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("🔍 Boss直聘重复岗位问题调试工具")
    print("=" * 50)
    
    success = asyncio.run(debug_duplicate_issue())
    
    if success:
        print("\n✅ 调试完成，请查看生成的分析报告")
    else:
        print("\n❌ 调试失败，请检查错误信息")


if __name__ == "__main__":
    main()