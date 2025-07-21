#!/usr/bin/env python3
"""
增强的岗位详情抓取方案
绕过反爬虫机制，精确提取岗位描述、任职要求和公司详情
"""

import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


async def fetch_job_details_enhanced(self, url: str, job_data: Dict) -> Dict:
    """
    增强的岗位详情抓取方法
    访问详情页并精确提取岗位职责、任职要求等信息
    
    Args:
        url: 岗位详情页URL
        job_data: 已有的岗位数据
    
    Returns:
        Dict: 更新后的岗位数据
    """
    if not url or not url.startswith('http'):
        return job_data
    
    try:
        # 创建新页面避免影响主页面
        detail_page = await self.browser.new_page()
        
        # 设置更真实的浏览器行为
        await detail_page.set_viewport_size({"width": 1920, "height": 1080})
        
        # 访问详情页
        logger.info(f"🔍 访问岗位详情页: {url}")
        await detail_page.goto(url, wait_until="networkidle", timeout=15000)
        
        # 等待关键内容加载
        await detail_page.wait_for_selector('.job-sec-text, .job-detail', timeout=5000)
        await asyncio.sleep(1.5)  # 额外等待动态内容
        
        # 模拟真实用户行为 - 滚动页面
        await detail_page.evaluate("""
            () => {
                // 平滑滚动到岗位详情区域
                const jobSection = document.querySelector('.job-sec-text');
                if (jobSection) {
                    jobSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
                // 随机滚动一些距离
                window.scrollBy(0, Math.random() * 200 + 100);
            }
        """)
        await asyncio.sleep(0.5)
        
        # 1. 提取岗位职责（job_description）
        job_description = await self._extract_job_description(detail_page)
        if job_description and len(job_description) > 50:
            job_data['job_description'] = job_description
            logger.info(f"✅ 获取岗位职责: {len(job_description)}字符")
        
        # 2. 提取任职要求（job_requirements）
        job_requirements = await self._extract_job_requirements(detail_page)
        if job_requirements and len(job_requirements) > 30:
            job_data['job_requirements'] = job_requirements
            logger.info(f"✅ 获取任职要求: {len(job_requirements)}字符")
        
        # 3. 提取公司详情（company_details）
        company_details = await self._extract_company_details(detail_page)
        if company_details:
            job_data['company_details'] = company_details
            job_data['company'] = company_details.split(' ')[0]  # 更新公司名称
            logger.info(f"✅ 获取公司详情: {company_details}")
        
        # 4. 提取其他补充信息
        additional_info = await self._extract_additional_info(detail_page)
        job_data.update(additional_info)
        
        await detail_page.close()
        return job_data
        
    except Exception as e:
        logger.warning(f"⚠️ 获取详情页失败: {e}")
        if 'detail_page' in locals():
            try:
                await detail_page.close()
            except:
                pass
        return job_data


async def _extract_job_description(self, page) -> str:
    """提取岗位职责"""
    # Boss直聘岗位职责的精确选择器
    selectors = [
        # 最精确：查找包含"岗位职责"文本的区域
        "//div[contains(text(), '岗位职责')]/following-sibling::div[1]",
        "//div[contains(text(), '工作职责')]/following-sibling::div[1]",
        "//div[contains(text(), '职位描述')]/following-sibling::div[1]",
        # 标准选择器
        ".job-sec-text:first-child",
        ".job-detail .job-sec:first-child .job-sec-text",
        # 通过结构定位
        ".job-detail-section:first-child .text",
        "section.job-sec:nth-child(1) .job-sec-text",
        # 备用选择器
        ".job-sec .job-sec-text",
        ".detail-content .text:first-child"
    ]
    
    for selector in selectors:
        try:
            if selector.startswith("//"):
                # XPath选择器
                elem = await page.query_selector(f"xpath={selector}")
            else:
                # CSS选择器
                elem = await page.query_selector(selector)
            
            if elem:
                text = await elem.inner_text()
                if text and len(text.strip()) > 50:
                    # 清理文本
                    cleaned_text = text.strip()
                    # 如果包含明显的分隔符，只取岗位职责部分
                    if "任职要求" in cleaned_text:
                        cleaned_text = cleaned_text.split("任职要求")[0].strip()
                    if "岗位要求" in cleaned_text:
                        cleaned_text = cleaned_text.split("岗位要求")[0].strip()
                    
                    return cleaned_text[:1500]  # 限制长度
        except:
            continue
    
    # 如果上述方法都失败，尝试通过JavaScript提取
    try:
        js_result = await page.evaluate("""
            () => {
                // 查找包含岗位职责的文本节点
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );
                
                let node;
                let foundJobDesc = false;
                let description = '';
                
                while (node = walker.nextNode()) {
                    const text = node.textContent.trim();
                    if (text.includes('岗位职责') || text.includes('工作职责') || text.includes('职位描述')) {
                        foundJobDesc = true;
                        continue;
                    }
                    
                    if (foundJobDesc && text.length > 20) {
                        // 找到下一个包含实质内容的文本节点
                        const parentClass = node.parentElement?.className || '';
                        if (parentClass.includes('job-sec-text') || parentClass.includes('text') || parentClass.includes('detail')) {
                            description = text;
                            break;
                        }
                    }
                }
                
                return description;
            }
        """)
        
        if js_result and len(js_result) > 50:
            return js_result[:1500]
    except:
        pass
    
    return ""


async def _extract_job_requirements(self, page) -> str:
    """提取任职要求"""
    # Boss直聘任职要求的精确选择器
    selectors = [
        # 最精确：查找包含"任职要求"文本的区域
        "//div[contains(text(), '任职要求')]/following-sibling::div[1]",
        "//div[contains(text(), '岗位要求')]/following-sibling::div[1]",
        "//div[contains(text(), '职位要求')]/following-sibling::div[1]",
        # 标准选择器（通常是第二个job-sec-text）
        ".job-sec-text:nth-child(2)",
        ".job-detail .job-sec:nth-child(2) .job-sec-text",
        # 通过结构定位
        ".job-detail-section:nth-child(2) .text",
        "section.job-sec:nth-child(2) .job-sec-text",
        # 备用选择器
        ".job-require-text",
        ".requirement-content"
    ]
    
    for selector in selectors:
        try:
            if selector.startswith("//"):
                elem = await page.query_selector(f"xpath={selector}")
            else:
                elem = await page.query_selector(selector)
            
            if elem:
                text = await elem.inner_text()
                if text and len(text.strip()) > 30:
                    return text.strip()[:1000]
        except:
            continue
    
    # JavaScript备用方案
    try:
        js_result = await page.evaluate("""
            () => {
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );
                
                let node;
                let foundRequirements = false;
                let requirements = '';
                
                while (node = walker.nextNode()) {
                    const text = node.textContent.trim();
                    if (text.includes('任职要求') || text.includes('岗位要求') || text.includes('职位要求')) {
                        foundRequirements = true;
                        continue;
                    }
                    
                    if (foundRequirements && text.length > 20) {
                        const parentClass = node.parentElement?.className || '';
                        if (parentClass.includes('job-sec-text') || parentClass.includes('text') || parentClass.includes('detail')) {
                            requirements = text;
                            break;
                        }
                    }
                }
                
                return requirements;
            }
        """)
        
        if js_result and len(js_result) > 30:
            return js_result[:1000]
    except:
        pass
    
    return ""


async def _extract_company_details(self, page) -> str:
    """提取公司详情"""
    # Boss直聘公司名称的精确选择器
    selectors = [
        ".brand-name",
        ".company-name",
        ".company-brand",
        "h1 .company-name",
        ".detail-company .company-name",
        ".company-info .name",
        ".job-company h3",
        # 通过结构定位
        ".sider-company .company-name",
        ".job-box .company-info h3"
    ]
    
    for selector in selectors:
        try:
            elem = await page.query_selector(selector)
            if elem:
                text = await elem.inner_text()
                if text and len(text.strip()) > 1:
                    company_name = text.strip()
                    
                    # 尝试获取更多公司信息
                    company_info_elem = await page.query_selector('.company-info, .sider-company')
                    if company_info_elem:
                        info_text = await company_info_elem.inner_text()
                        # 提取行业、规模等信息
                        lines = info_text.split('\n')
                        useful_lines = [line.strip() for line in lines if line.strip() and len(line.strip()) < 50]
                        if len(useful_lines) > 1:
                            return f"{company_name} | {' | '.join(useful_lines[1:3])}"
                    
                    return company_name
        except:
            continue
    
    return ""


async def _extract_additional_info(self, page) -> Dict:
    """提取其他补充信息"""
    additional_info = {}
    
    try:
        # 提取福利信息
        benefits_elem = await page.query_selector('.job-tags, .welfare-list, .tag-list')
        if benefits_elem:
            benefits_text = await benefits_elem.inner_text()
            if benefits_text:
                additional_info['benefits'] = benefits_text.strip()
        
        # 提取工作地址详情
        address_elem = await page.query_selector('.location-address, .work-addr, .job-address')
        if address_elem:
            address_text = await address_elem.inner_text()
            if address_text and '地址' not in address_text:  # 过滤掉"工作地址"这种标签
                additional_info['detailed_address'] = address_text.strip()
        
        # 提取发布时间
        time_elem = await page.query_selector('.job-time, .time')
        if time_elem:
            time_text = await time_elem.inner_text()
            if time_text:
                additional_info['publish_time'] = time_text.strip()
    
    except Exception as e:
        logger.debug(f"提取补充信息失败: {e}")
    
    return additional_info


# 集成到real_playwright_spider.py的方法
def integrate_enhanced_extraction():
    """
    将增强的提取方法集成到real_playwright_spider.py
    
    在_extract_single_job方法的最后，在返回job_data之前调用：
    
    # 获取详情页的真实信息
    if url and url.startswith('http'):
        job_data = await self.fetch_job_details_enhanced(url, job_data)
    """
    pass