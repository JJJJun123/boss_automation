#!/usr/bin/env python3
"""
实时调试Boss直聘选择器问题
分析当前页面的实际DOM结构，找出正确的选择器
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


async def analyze_job_elements():
    """分析岗位元素的实际结构"""
    try:
        from crawler.real_playwright_spider import RealPlaywrightBossSpider
        
        logger.info("🔍 开始实时分析Boss直聘页面结构...")
        
        # 创建爬虫实例（可见模式）
        spider = RealPlaywrightBossSpider(headless=False)
        
        if not await spider.start():
            logger.error("❌ 无法启动Playwright")
            return
        
        # 搜索测试
        keyword = "风险管理"
        city = "shanghai"
        city_code = spider.city_codes.get(city, "101020100")
        search_url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city_code}"
        
        logger.info(f"🌐 访问: {search_url}")
        await spider.page.goto(search_url, wait_until="domcontentloaded")
        
        # 等待页面加载
        await asyncio.sleep(8)
        
        # 处理可能的弹窗
        try:
            await asyncio.sleep(2)
            # 尝试关闭可能的弹窗
            close_buttons = await spider.page.query_selector_all('[class*="close"], .dialog-close, [aria-label="close"]')
            for btn in close_buttons:
                try:
                    await btn.click()
                    logger.info("✅ 关闭了一个弹窗")
                    await asyncio.sleep(1)
                except:
                    pass
        except:
            pass
        
        # 滚动页面加载更多
        await spider.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(3)
        
        # 分析页面结构
        logger.info("🔍 分析页面中的所有岗位元素...")
        
        # 尝试我们当前的选择器
        current_selectors = [
            '.job-list-container li',
            'li[class*="job"]',
            'div[class*="job-card"]',
            '.job-detail-box'
        ]
        
        job_elements = []
        used_selector = ""
        
        for selector in current_selectors:
            try:
                elements = await spider.page.query_selector_all(selector)
                if elements and len(elements) > 5:  # 需要找到多个元素
                    logger.info(f"✅ 选择器 '{selector}' 找到 {len(elements)} 个元素")
                    job_elements = elements[:10]  # 只分析前10个
                    used_selector = selector
                    break
            except Exception as e:
                logger.debug(f"选择器 '{selector}' 异常: {e}")
        
        if not job_elements:
            logger.warning("⚠️ 未找到岗位元素，尝试通用分析...")
            return False
        
        logger.info(f"📋 使用选择器: {used_selector}")
        logger.info(f"📊 分析前5个岗位元素的内部结构...")
        
        analysis_results = []
        
        for i, job_elem in enumerate(job_elements[:5]):
            logger.info(f"\n{'='*60}")
            logger.info(f"🎯 分析岗位元素 {i+1}")
            
            try:
                # 获取元素的文本内容
                elem_text = await job_elem.inner_text()
                logger.info(f"📝 元素文本预览: {elem_text[:150]}...")
                
                # 获取元素的HTML结构（截断显示）
                elem_html = await job_elem.inner_html()
                
                # 测试各种可能的选择器
                field_tests = {
                    "标题": [
                        '.job-name', '.job-title', 'h3', 'a[class*="name"]', 
                        '.position-name', '[class*="title"]', 'span.job-name',
                        'div[class*="name"]', '.job-card-left .name'
                    ],
                    "公司": [
                        '.company-name', '.company-text', 'h3:not(.job-name)', 
                        '.company', '[class*="company"]', '.job-company',
                        'div[class*="company"]', 'span[class*="company"]'
                    ],
                    "薪资": [
                        '.salary', '.red', '[class*="salary"]', '.job-limit',
                        '.price', '[class*="price"]', '[class*="pay"]',
                        'span[class*="salary"]', 'div[class*="salary"]'
                    ],
                    "地点": [
                        '.job-area', '.area', '[class*="area"]', '.location',
                        '.job-location', '[class*="location"]', '.address',
                        'span[class*="area"]', 'div[class*="location"]'
                    ]
                }
                
                element_analysis = {"index": i+1, "text_preview": elem_text[:200]}
                
                for field_name, selectors in field_tests.items():
                    found_results = []
                    
                    for selector in selectors:
                        try:
                            matches = await job_elem.query_selector_all(selector)
                            for match in matches:
                                text = await match.inner_text()
                                if text and text.strip() and len(text.strip()) > 1:
                                    # 避免重复和无意义的文本
                                    text = text.strip()
                                    if (len(text) < 200 and 
                                        text not in [t[1] for t in found_results] and
                                        not any(t in text.lower() for t in ['javascript', 'function', 'null', 'undefined'])):
                                        found_results.append((selector, text))
                        except Exception as e:
                            continue
                    
                    if found_results:
                        logger.info(f"   🎯 {field_name}字段:")
                        for selector, text in found_results[:3]:  # 只显示前3个结果
                            logger.info(f"      {selector}: '{text[:50]}'")
                        element_analysis[field_name.lower()] = found_results[:5]
                    else:
                        logger.warning(f"   ❌ {field_name}: 未找到匹配")
                        element_analysis[field_name.lower()] = []
                
                # 分析链接
                link_selectors = [
                    'a', 'a[href*="job_detail"]', 'a[href*="job"]',
                    '[data-url]', '[onclick*="job"]', '.job-card-body'
                ]
                
                found_links = []
                for selector in link_selectors:
                    try:
                        links = await job_elem.query_selector_all(selector)
                        for link in links:
                            href = await link.get_attribute('href')
                            if href and ('job' in href or 'detail' in href):
                                found_links.append((selector, href))
                    except:
                        continue
                
                if found_links:
                    logger.info(f"   🔗 找到链接:")
                    for selector, href in found_links[:2]:
                        logger.info(f"      {selector}: {href[:60]}...")
                    element_analysis['links'] = found_links[:3]
                else:
                    logger.warning(f"   ❌ 未找到岗位链接")
                    element_analysis['links'] = []
                
                analysis_results.append(element_analysis)
                
            except Exception as e:
                logger.error(f"   ❌ 分析岗位元素 {i+1} 失败: {e}")
        
        # 保存分析结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        analysis_path = f"live_selector_analysis_{timestamp}.json"
        
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis_results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n📊 分析完成！结果保存到: {analysis_path}")
        
        # 基于分析结果给出建议
        logger.info("\n💡 选择器优化建议:")
        
        # 统计最有效的选择器
        for field in ["标题", "公司", "薪资", "地点"]:
            field_key = field.lower()
            all_selectors = []
            
            for result in analysis_results:
                if field_key in result:
                    all_selectors.extend([item[0] for item in result[field_key]])
            
            # 统计频率
            from collections import Counter
            selector_counts = Counter(all_selectors)
            
            if selector_counts:
                best_selector = selector_counts.most_common(1)[0]
                logger.info(f"   {field}: 推荐选择器 '{best_selector[0]}' (出现{best_selector[1]}次)")
            else:
                logger.warning(f"   {field}: 未找到有效选择器")
        
        # 截图保存当前页面
        screenshot_path = f"live_page_{timestamp}.png"
        await spider.page.screenshot(path=screenshot_path)
        logger.info(f"📸 页面截图保存: {screenshot_path}")
        
        await spider.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("🔍 Boss直聘实时选择器分析工具")
    print("=" * 50)
    
    success = asyncio.run(analyze_job_elements())
    
    if success:
        print("\n✅ 分析完成")
        print("💡 基于分析结果，我们可以更新选择器以修复数据提取问题")
        print("📁 请查看生成的JSON文件获取详细分析结果")
    else:
        print("\n❌ 分析失败，请检查错误信息")


if __name__ == "__main__":
    main()