#!/usr/bin/env python3
"""
修复岗位详情提取问题
1. 优化公司名称提取选择器
2. 添加从详情页获取真实岗位描述的逻辑
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 在real_playwright_spider.py的_extract_single_job方法中添加以下修复

COMPANY_NAME_FIX = """
# 🏢 优化公司名称提取 - 修复版本
company_selectors = [
    # 最精确的公司名称选择器（基于实际HTML结构）
    'h3:not(.job-name):not([class*="salary"])', 
    '.company-name', '.company-text', 
    '.job-company', '.company-info .name',
    # 通过兄弟元素关系定位（公司名通常在岗位标题后）
    '.job-name + span', '.job-name + div', '.job-name + h3',
    # 通过父子关系定位
    '.job-card-body > div:nth-child(2)', '.job-card-left > div:nth-child(2)',
    # Boss直聘特有结构
    '.job-info > div:not(.job-name):not([class*="salary"])',
    '.job-detail-top .company-name'
]

company = ""
for selector in company_selectors:
    try:
        company_elems = await card.query_selector_all(selector)
        for company_elem in company_elems:
            company_text = await company_elem.inner_text()
            if company_text and company_text.strip():
                company_text = company_text.strip()
                
                # 增强的过滤逻辑
                if (len(company_text) >= 2 and len(company_text) <= 50 and  # 公司名长度合理
                    company_text != title.strip() and  # 不是岗位标题
                    not any(word in company_text for word in [
                        'K·薪', '万·薪', '千·薪', '经验', '学历', '岗位', '年', 
                        '·', '区', '市', '街', '路', '不限', '-', '/'
                    ]) and  # 不包含明显的非公司名关键词
                    not company_text.isdigit() and  # 不是纯数字
                    not company_text.startswith(('1-', '3-', '5-')) and  # 不是经验要求格式
                    len([c for c in company_text if c.isalpha() or '\u4e00' <= c <= '\u9fff']) >= 2):  # 包含足够字符
                    
                    company = company_text
                    logger.debug(f"   ✅ 找到公司名称: {company} (选择器: {selector})")
                    break
        if company:
            break
    except Exception as e:
        logger.debug(f"   公司选择器 {selector} 异常: {e}")

if not company:
    company = "未知公司"
    logger.warning(f"   ⚠️ 未找到公司名称，使用默认: {company}")
"""

DETAILED_EXTRACTION_FIX = """
# 📋 从岗位详情页获取真实信息的增强逻辑
description = ""
requirements = ""
company_details = ""

if url and url.startswith('http'):
    try:
        # 创建新页面获取详情
        detail_page = await self.browser.new_page()
        await detail_page.goto(url, wait_until="domcontentloaded", timeout=8000)
        await asyncio.sleep(1.5)  # 缩短等待时间
        
        # 🎯 提取岗位职责（更精确的选择器）
        job_desc_selectors = [
            '.job-sec-text',  # Boss直聘标准
            '.job-detail-text', '.job-description', 
            'div[class*="job-sec"] .text-desc',
            'section.job-detail .detail-content',
            'div:has-text("岗位职责") + .text-desc',
            'div:has-text("工作内容") + .text-desc',
            '.job-detail .job-detail-section:first-child .text'
        ]
        
        for selector in job_desc_selectors:
            try:
                desc_elem = await detail_page.query_selector(selector)
                if desc_elem:
                    desc_text = await desc_elem.inner_text()
                    if desc_text and len(desc_text.strip()) > 30:  # 确保描述有意义
                        description = desc_text.strip()[:800]  # 合理限制长度
                        logger.debug(f"   ✅ 获取岗位描述: {len(description)}字符")
                        break
            except:
                continue
        
        # 🎯 提取任职要求（更精确的选择器）
        job_req_selectors = [
            'div:has-text("任职要求") + .text-desc',
            'div:has-text("岗位要求") + .text-desc', 
            'div:has-text("职位要求") + .text-desc',
            '.job-require-text', '.requirement-content',
            '.job-detail .job-detail-section:nth-child(2) .text'
        ]
        
        for selector in job_req_selectors:
            try:
                req_elem = await detail_page.query_selector(selector)
                if req_elem:
                    req_text = await req_elem.inner_text()
                    if req_text and len(req_text.strip()) > 15:
                        requirements = req_text.strip()[:600]
                        logger.debug(f"   ✅ 获取任职要求: {len(requirements)}字符")
                        break
            except:
                continue
        
        # 🏢 提取公司详情
        if not company or company == "未知公司":
            company_detail_selectors = [
                '.brand-name', '.company-name', '.company-brand',
                'h1 .company-name', '.detail-company .company-name'
            ]
            
            for selector in company_detail_selectors:
                try:
                    company_elem = await detail_page.query_selector(selector)
                    if company_elem:
                        company_text = await company_elem.inner_text()
                        if company_text and company_text.strip():
                            company = company_text.strip()
                            logger.debug(f"   ✅ 从详情页获取公司: {company}")
                            break
                except:
                    continue
        
        await detail_page.close()
        
    except Exception as e:
        logger.debug(f"   ⚠️ 获取详情页信息失败: {e}")
        # 失败不影响主流程

# 如果仍然没有获取到有意义的信息，使用改进的默认值
if not description or len(description) < 20:
    description = f"负责{title}相关工作。具体职责请点击链接查看岗位详情。"

if not requirements or len(requirements) < 10:
    # 尝试从当前页面提取基本要求信息
    exp_elem = await card.query_selector('.job-limit')
    exp_text = await exp_elem.inner_text() if exp_elem else ""
    experience = self._extract_experience(exp_text)
    education = self._extract_education(exp_text)
    requirements = f"要求{experience}工作经验，{education}学历。更多要求请查看岗位详情。"
"""

def apply_fixes():
    """应用修复到real_playwright_spider.py"""
    print("🔧 岗位详情提取修复脚本")
    print("=" * 50)
    print("📋 这个脚本包含了以下修复:")
    print("1. 🏢 优化公司名称提取选择器和过滤逻辑")
    print("2. 📄 添加从详情页获取真实岗位描述的逻辑") 
    print("3. 🎯 更精确的任职要求提取")
    print()
    print("💡 修复内容已准备好，需要手动应用到代码中:")
    print("   - 替换 real_playwright_spider.py 中的公司名称提取部分")
    print("   - 替换岗位描述提取逻辑")
    print("   - 添加详情页访问功能")
    print()
    print("🚀 应用修复后，重新运行应用即可看到改善!")

if __name__ == "__main__":
    apply_fixes()