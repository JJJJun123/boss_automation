#!/usr/bin/env python3
"""
调试Boss直聘岗位详情页面结构
分析job-sec-text、岗位职责、任职要求、brand-name等字段
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


async def debug_job_detail_fields():
    """调试岗位详情页面的字段结构"""
    try:
        from crawler.real_playwright_spider import RealPlaywrightBossSpider
        
        logger.info("🔍 开始调试岗位详情页面字段结构...")
        
        spider = RealPlaywrightBossSpider(headless=False)
        
        if not await spider.start():
            logger.error("❌ 无法启动Playwright")
            return
        
        # 先搜索获取一些岗位链接
        keyword = "风险管理"
        city = "shanghai"
        search_url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city=101020100"
        
        logger.info(f"🌐 首先访问搜索页面获取岗位链接: {search_url}")
        await spider.page.goto(search_url, wait_until="domcontentloaded")
        await asyncio.sleep(5)
        
        # 获取前3个岗位链接
        job_links = []
        try:
            link_elements = await spider.page.query_selector_all('a[href*="job_detail"]')
            for elem in link_elements[:3]:
                href = await elem.get_attribute('href')
                if href:
                    full_url = f"https://www.zhipin.com{href}" if href.startswith('/') else href
                    job_links.append(full_url)
        except Exception as e:
            logger.error(f"获取岗位链接失败: {e}")
            return
        
        if not job_links:
            logger.error("未找到岗位链接")
            return
        
        logger.info(f"📋 找到 {len(job_links)} 个岗位链接，开始分析详情页面...")
        
        analysis_results = []
        
        for i, job_url in enumerate(job_links[:2]):  # 只分析前2个，避免时间过长
            logger.info(f"\n{'='*60}")
            logger.info(f"🎯 分析岗位 {i+1}: {job_url}")
            
            try:
                # 导航到岗位详情页
                await spider.page.goto(job_url, wait_until="domcontentloaded")
                await asyncio.sleep(3)
                
                analysis = {
                    "job_index": i+1,
                    "url": job_url,
                    "fields": {}
                }
                
                # 分析各种可能的字段选择器
                field_selectors = {
                    "岗位标题": ['.job-name', '.job-title', 'h1'],
                    "公司名称_brand": ['.brand-name', '.company-name', '.company-brand'],
                    "薪资": ['.salary', '.job-salary'],
                    "岗位职责_job_sec": ['.job-sec-text', '.job-detail-text', '.job-description'],
                    "任职要求_job_require": ['.job-require', '.job-requirement', '.requirement'],
                    "公司简介": ['.company-intro', '.company-detail', '.company-desc'],
                    "福利待遇": ['.job-tags', '.welfare', '.benefits']
                }
                
                # 测试每个字段的选择器
                for field_name, selectors in field_selectors.items():
                    logger.info(f"   🔍 分析字段: {field_name}")
                    field_results = []
                    
                    for selector in selectors:
                        try:
                            elements = await spider.page.query_selector_all(selector)
                            for elem_idx, elem in enumerate(elements):
                                text = await elem.inner_text()
                                if text and text.strip():
                                    text = text.strip()[:200]  # 限制长度
                                    field_results.append({
                                        "selector": selector,
                                        "element_index": elem_idx,
                                        "text": text,
                                        "text_length": len(text)
                                    })
                                    logger.info(f"      ✅ {selector}[{elem_idx}]: {text[:50]}...")
                        except Exception as e:
                            logger.debug(f"      ❌ {selector}: {e}")
                    
                    analysis["fields"][field_name] = field_results
                
                # 特别分析包含"岗位职责"和"任职要求"文本的元素
                logger.info("   🎯 特别搜索包含关键词的元素:")
                keywords = ["岗位职责", "任职要求", "工作职责", "职位要求", "岗位要求"]
                
                for keyword in keywords:
                    try:
                        # 使用XPath查找包含特定文本的元素
                        elements = await spider.page.query_selector_all(f'text="{keyword}"')
                        if not elements:
                            # 尝试部分匹配
                            elements = await spider.page.query_selector_all('*')
                            matching_elements = []
                            for elem in elements:
                                text = await elem.inner_text()
                                if text and keyword in text:
                                    matching_elements.append(elem)
                            elements = matching_elements[:3]  # 限制数量
                        
                        for elem_idx, elem in enumerate(elements[:2]):  # 只取前2个
                            try:
                                text = await elem.inner_text()
                                if text and len(text) > 10:
                                    # 获取父元素和子元素信息
                                    parent_text = ""
                                    try:
                                        parent = await elem.evaluate("el => el.parentElement")
                                        if parent:
                                            parent_text = await parent.inner_text()
                                    except:
                                        pass
                                    
                                    logger.info(f"      🎯 {keyword}[{elem_idx}]: {text[:100]}...")
                                    if parent_text and parent_text != text:
                                        logger.info(f"         父元素: {parent_text[:50]}...")
                            except Exception as e:
                                logger.debug(f"         分析{keyword}元素失败: {e}")
                    except Exception as e:
                        logger.debug(f"   搜索{keyword}失败: {e}")
                
                # 截图保存当前页面
                screenshot_path = f"job_detail_{i+1}_{datetime.now().strftime('%H%M%S')}.png"
                await spider.page.screenshot(path=screenshot_path)
                logger.info(f"📸 页面截图: {screenshot_path}")
                
                analysis_results.append(analysis)
                
            except Exception as e:
                logger.error(f"❌ 分析岗位 {i+1} 失败: {e}")
        
        # 保存分析结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        analysis_path = f"job_detail_field_analysis_{timestamp}.json"
        
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis_results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n📊 字段分析完成!")
        logger.info(f"📁 分析报告: {analysis_path}")
        
        # 给出选择器建议
        logger.info(f"\n💡 基于分析结果的选择器建议:")
        
        all_successful_selectors = {}
        for result in analysis_results:
            for field, field_results in result["fields"].items():
                if field_results:
                    if field not in all_successful_selectors:
                        all_successful_selectors[field] = {}
                    for item in field_results:
                        selector = item["selector"]
                        if selector in all_successful_selectors[field]:
                            all_successful_selectors[field][selector] += 1
                        else:
                            all_successful_selectors[field][selector] = 1
        
        for field, selectors in all_successful_selectors.items():
            if selectors:
                best_selector = max(selectors.items(), key=lambda x: x[1])
                logger.info(f"   {field}: 推荐 '{best_selector[0]}' (成功{best_selector[1]}次)")
        
        await spider.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("🔍 Boss直聘岗位详情字段分析工具")
    print("=" * 50)
    
    success = asyncio.run(debug_job_detail_fields())
    
    if success:
        print("\n✅ 字段分析完成，请查看生成的报告")
    else:
        print("\n❌ 分析失败，请检查错误信息")


if __name__ == "__main__":
    main()