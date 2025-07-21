#!/usr/bin/env python3
"""
调试Boss直聘页面结构
分析当前页面元素，找出正确的选择器
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


async def debug_boss_page_structure():
    """调试Boss直聘页面结构"""
    try:
        from crawler.real_playwright_spider import RealPlaywrightBossSpider
        
        logger.info("🔍 开始调试Boss直聘页面结构...")
        
        # 创建爬虫实例（可见模式，便于观察）
        spider = RealPlaywrightBossSpider(headless=False)
        
        if not await spider.start():
            logger.error("❌ 无法启动Playwright")
            return
        
        # 搜索测试关键词
        keyword = "数据分析"
        city = "shanghai"
        
        logger.info(f"🔍 搜索: {keyword} 在 {city}")
        
        # 获取城市代码
        city_code = spider.city_codes.get(city, "101210100")
        search_url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city={city_code}"
        
        logger.info(f"🌐 访问: {search_url}")
        await spider.page.goto(search_url, wait_until="domcontentloaded")
        
        # 等待页面加载
        await asyncio.sleep(8)
        
        # 处理可能的登录弹窗
        try:
            login_modal = await spider.page.query_selector('.login-dialog, .dialog-wrap')
            if login_modal:
                logger.info("🔐 检测到登录弹窗，等待处理...")
                await asyncio.sleep(3)
        except:
            pass
        
        # 截图保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"debug_boss_structure_{timestamp}.png"
        await spider.page.screenshot(path=screenshot_path)
        logger.info(f"📸 截图保存: {screenshot_path}")
        
        # 保存页面HTML
        page_html = await spider.page.content()
        html_path = f"debug_boss_structure_{timestamp}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page_html)
        logger.info(f"📄 页面HTML保存: {html_path}")
        
        # 分析页面结构
        logger.info("🔍 分析页面结构...")
        
        # 尝试找到岗位容器
        potential_job_containers = [
            '.job-card-wrapper', 
            '.job-list-item',
            '.job-card-container', 
            'li[class*="job"]',
            'div[class*="job-card"]',
            '.job-detail-box',
            'a[ka*="search_list"]'
        ]
        
        job_elements = []
        for selector in potential_job_containers:
            try:
                elements = await spider.page.query_selector_all(selector)
                if elements:
                    logger.info(f"✅ 选择器 '{selector}' 找到 {len(elements)} 个元素")
                    job_elements = elements
                    used_selector = selector
                    break
                else:
                    logger.debug(f"   选择器 '{selector}' 未找到元素")
            except Exception as e:
                logger.debug(f"   选择器 '{selector}' 异常: {e}")
        
        if not job_elements:
            logger.warning("⚠️ 未找到岗位元素，尝试通用分析...")
            
            # 分析页面中包含特定关键词的元素
            all_divs = await spider.page.query_selector_all('div')
            logger.info(f"📊 页面共有 {len(all_divs)} 个div元素")
            
            keyword_elements = []
            for i, div in enumerate(all_divs[:100]):  # 只分析前100个
                try:
                    text = await div.inner_text()
                    if text and any(kw in text for kw in ["K", "薪", "经验", "学历"]) and len(text) < 200:
                        keyword_elements.append((i, text[:100]))
                except:
                    continue
            
            logger.info(f"🎯 找到 {len(keyword_elements)} 个可能的岗位相关元素:")
            for i, (index, text) in enumerate(keyword_elements[:10]):
                logger.info(f"   元素 {index}: {text}...")
        
        else:
            # 分析找到的岗位元素结构
            logger.info(f"📋 分析前3个岗位元素的结构 (使用选择器: {used_selector})...")
            
            analysis_results = []
            
            for i, job_elem in enumerate(job_elements[:3]):
                logger.info(f"\n--- 岗位元素 {i+1} ---")
                
                try:
                    # 获取元素的HTML结构
                    elem_html = await job_elem.inner_html()
                    elem_text = await job_elem.inner_text()
                    
                    logger.info(f"📝 元素文本: {elem_text[:200]}...")
                    
                    # 分析内部结构
                    analysis = {
                        "index": i+1,
                        "full_text": elem_text,
                        "html_snippet": elem_html[:500] + "..." if len(elem_html) > 500 else elem_html
                    }
                    
                    # 尝试不同选择器提取信息
                    title_selectors = ['.job-name', '.job-title', 'h3', 'a', 'span[class*="name"]']
                    company_selectors = ['.company-name', '.company', 'span[class*="company"]']
                    salary_selectors = ['.salary', '.red', 'span[class*="salary"]']
                    location_selectors = ['.job-area', '.area', 'span[class*="area"]']
                    
                    for desc, selectors in [
                        ("标题", title_selectors),
                        ("公司", company_selectors), 
                        ("薪资", salary_selectors),
                        ("地点", location_selectors)
                    ]:
                        found_texts = []
                        for sel in selectors:
                            try:
                                elems = await job_elem.query_selector_all(sel)
                                for elem in elems:
                                    text = await elem.inner_text()
                                    if text.strip():
                                        found_texts.append(f"{sel}: '{text.strip()}'")
                            except:
                                continue
                        
                        if found_texts:
                            logger.info(f"   {desc}: {found_texts}")
                            analysis[desc.lower()] = found_texts
                        else:
                            logger.warning(f"   {desc}: 未找到")
                            analysis[desc.lower()] = []
                    
                    analysis_results.append(analysis)
                    
                except Exception as e:
                    logger.error(f"   ❌ 分析岗位元素 {i+1} 失败: {e}")
            
            # 保存分析结果
            analysis_path = f"debug_analysis_{timestamp}.json"
            with open(analysis_path, "w", encoding="utf-8") as f:
                json.dump(analysis_results, f, ensure_ascii=False, indent=2)
            logger.info(f"📊 分析结果保存: {analysis_path}")
        
        # 关闭浏览器
        await spider.close()
        
        logger.info("✅ 页面结构调试完成")
        logger.info(f"📁 生成的文件:")
        logger.info(f"   - 截图: {screenshot_path}")
        logger.info(f"   - HTML: {html_path}")
        if 'analysis_path' in locals():
            logger.info(f"   - 分析: {analysis_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 调试过程失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("🔍 Boss直聘页面结构调试工具")
    print("=" * 40)
    
    success = asyncio.run(debug_boss_page_structure())
    
    if success:
        print("\n✅ 调试完成，请查看生成的文件来分析页面结构")
        print("💡 基于分析结果，我们可以更新选择器以修复抓取问题")
    else:
        print("\n❌ 调试失败，请检查错误信息")


if __name__ == "__main__":
    main()