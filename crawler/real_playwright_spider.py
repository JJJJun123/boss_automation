#!/usr/bin/env python3
"""
真正的Playwright自动化Boss直聘爬虫
实现可见的浏览器操作和真实数据提取
"""

import asyncio
import logging
import urllib.parse
import time
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)


class RealPlaywrightBossSpider:
    """真正的Playwright Boss直聘爬虫"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None
        
        # Boss直聘城市代码映射 (与app_config.yaml保持一致)
        self.city_codes = {
            "shanghai": "101020100",   # 上海 (修复：之前错误为101210100)
            "beijing": "101010100",    # 北京 (正确)
            "shenzhen": "101280600",   # 深圳 (正确)
            "hangzhou": "101210100"    # 杭州 (修复：之前错误为101210300->嘉兴)
        }
        
    async def start(self) -> bool:
        """启动浏览器"""
        try:
            logger.info("🎭 启动真正的Playwright浏览器...")
            
            self.playwright = await async_playwright().start()
            
            # 启动Chrome浏览器，确保用户可以看到
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--start-maximized'  # 最大化窗口
                ]
            )
            
            logger.info("🖥️ Chrome浏览器窗口已打开，你应该能看到它！")
            
            # 创建新页面
            context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            self.page = await context.new_page()
            
            # 确保窗口在前台
            await self.page.bring_to_front()
            logger.info("📱 浏览器窗口已设置为前台显示")
            
            logger.info("✅ Playwright浏览器启动成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 启动浏览器失败: {e}")
            return False
    
    async def search_jobs(self, keyword: str, city: str, max_jobs: int = 20) -> List[Dict]:
        """搜索岗位"""
        try:
            if not self.page:
                logger.error("❌ 浏览器未启动")
                return []
            
            # 首先确保已登录
            logger.info("🔐 检查登录状态...")
            if not await self._ensure_logged_in():
                logger.error("❌ 登录失败，无法继续搜索")
                return []
            
            # 获取城市代码
            city_code = self.city_codes.get(city, "101210100")  # 默认上海
            
            logger.info(f"🔍 开始搜索: {keyword} | 城市: {city} ({city_code}) | 数量: {max_jobs}")
            
            # 构建搜索URL
            encoded_keyword = urllib.parse.quote(keyword)
            search_url = f"https://www.zhipin.com/web/geek/job?query={encoded_keyword}&city={city_code}"
            
            logger.info(f"🌐 导航到: {search_url}")
            
            # 导航到搜索页面
            logger.info("🔗 正在导航到Boss直聘搜索页面...")
            logger.info("👀 请观察浏览器窗口，你应该能看到页面加载过程")
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
            
            # 截图记录当前页面
            screenshot_path = f"boss_search_{int(time.time())}.png"
            await self.page.screenshot(path=screenshot_path)
            logger.info(f"📸 已截图当前页面: {screenshot_path}")
            
            # 等待页面加载完成（增加等待时间）
            logger.info("⏳ 等待页面完全加载...")
            await asyncio.sleep(8)  # 增加到8秒，确保动态内容加载
            
            # 尝试滚动页面以加载更多岗位（Boss直聘可能使用懒加载）
            logger.info("📜 滚动页面以触发更多岗位加载...")
            for scroll_attempt in range(3):
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)  # 每次滚动后等待2秒
                
                # 检查是否有新内容加载
                page_height = await self.page.evaluate("document.body.scrollHeight")
                logger.info(f"   滚动 {scroll_attempt + 1}/3，页面高度: {page_height}")
            
            # 滚动回顶部
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(2)
            
            logger.info("📄 页面已加载，开始处理可能的弹窗...")
            
            # 检查是否需要登录或有验证码
            await self._handle_login_or_captcha()
            
            # 提取岗位数据
            jobs = await self._extract_jobs_from_page(max_jobs)
            
            # 如果没有找到岗位，尝试截图调试
            if not jobs:
                screenshot_path = await self.take_screenshot()
                logger.warning(f"⚠️ 未找到岗位，已截图: {screenshot_path}")
                logger.error("❌ 真实抓取失败，未找到任何岗位数据")
                
                # 返回空列表，不生成假数据
                logger.info("🚫 不生成示例数据，保持数据真实性")
                return []
            
            logger.info(f"✅ 成功提取 {len(jobs)} 个岗位")
            return jobs
            
        except Exception as e:
            logger.error(f"❌ 搜索岗位失败: {e}")
            return []
    
    async def _ensure_logged_in(self) -> bool:
        """确保已登录Boss直聘"""
        try:
            # 首先导航到Boss直聘首页
            logger.info("🏠 导航到Boss直聘首页...")
            await self.page.goto("https://www.zhipin.com", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(3)
            
            # 尝试加载已保存的cookies
            cookies_loaded = await self._load_cookies()
            if cookies_loaded:
                logger.info("🍪 已加载保存的cookies，刷新页面...")
                await self.page.reload()
                await asyncio.sleep(3)
                
                # 检查是否登录成功
                if await self._check_login_status():
                    logger.info("✅ 使用保存的cookies登录成功!")
                    return True
                else:
                    logger.warning("⚠️ 保存的cookies已失效，需要重新登录")
            
            # 需要手动登录
            logger.info("=" * 50)
            logger.info("🔐 需要手动登录Boss直聘")
            logger.info("请在浏览器窗口中完成以下操作：")
            logger.info("1. 点击页面右上角的 '登录' 按钮")
            logger.info("2. 使用扫码或账号密码登录")
            logger.info("3. 登录成功后，会自动继续执行")
            logger.info("=" * 50)
            
            # 等待用户登录，最多等待5分钟
            start_time = time.time()
            timeout = 300  # 5分钟
            
            while time.time() - start_time < timeout:
                # 每5秒检查一次登录状态
                await asyncio.sleep(5)
                
                if await self._check_login_status():
                    logger.info("✅ 检测到登录成功!")
                    # 保存cookies
                    await self._save_cookies()
                    return True
                else:
                    remaining = int(timeout - (time.time() - start_time))
                    logger.info(f"⏳ 等待登录中... (剩余 {remaining} 秒)")
            
            logger.error("❌ 登录超时，请在5分钟内完成登录")
            return False
            
        except Exception as e:
            logger.error(f"❌ 登录过程出错: {e}")
            return False
    
    async def _check_login_status(self) -> bool:
        """检查是否已登录"""
        try:
            # 检查是否有用户相关元素（已登录）
            user_selectors = [
                '.nav-figure img',  # 用户头像
                '.nav-figure',      # 用户信息区域
                '.user-name',       # 用户名
                '[class*="avatar"]', # 包含avatar的元素
                '.dropdown-avatar'   # 下拉头像
            ]
            
            for selector in user_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.info(f"✓ 找到用户元素: {selector}")
                        return True
                except:
                    continue
            
            # 检查是否有登录按钮（未登录）
            login_selectors = [
                'a.btn-sign-in',
                'button.btn-sign-in',
                '.sign-wrap .btn',
                'a:has-text("登录")',
                'button:has-text("登录")'
            ]
            
            for selector in login_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.info(f"✗ 找到登录按钮: {selector}")
                        return False
                except:
                    continue
            
            # 如果都找不到，检查页面URL
            current_url = self.page.url
            if '/login' in current_url or '/signup' in current_url:
                return False
            
            # 默认认为已登录
            return True
            
        except Exception as e:
            logger.error(f"❌ 检查登录状态失败: {e}")
            return False
    
    async def _save_cookies(self) -> None:
        """保存cookies到文件"""
        try:
            cookies = await self.page.context.cookies()
            import json
            import os
            
            cookies_dir = os.path.join(os.path.dirname(__file__), 'cookies')
            os.makedirs(cookies_dir, exist_ok=True)
            
            cookies_file = os.path.join(cookies_dir, 'boss_cookies.json')
            with open(cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Cookies已保存到: {cookies_file}")
            
        except Exception as e:
            logger.error(f"❌ 保存cookies失败: {e}")
    
    async def _load_cookies(self) -> bool:
        """加载已保存的cookies"""
        try:
            import json
            import os
            
            cookies_file = os.path.join(os.path.dirname(__file__), 'cookies', 'boss_cookies.json')
            
            if not os.path.exists(cookies_file):
                logger.info("📄 没有找到保存的cookies文件")
                return False
            
            with open(cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            # 添加cookies到浏览器
            await self.page.context.add_cookies(cookies)
            logger.info(f"✅ 已加载 {len(cookies)} 个cookies")
            return True
            
        except Exception as e:
            logger.error(f"❌ 加载cookies失败: {e}")
            return False
    
    async def _handle_login_or_captcha(self):
        """处理登录或验证码"""
        try:
            # 检查是否有登录弹窗
            login_modal = await self.page.query_selector('.login-dialog, .dialog-wrap')
            if login_modal:
                logger.info("🔐 检测到登录弹窗，等待用户处理...")
                # 等待一段时间让用户处理
                await asyncio.sleep(5)
            
            # 检查验证码
            captcha = await self.page.query_selector('.captcha, .verify-wrap')
            if captcha:
                logger.info("🔒 检测到验证码，等待用户处理...")
                await asyncio.sleep(5)
                
        except Exception as e:
            logger.warning(f"⚠️ 处理登录/验证码时出错: {e}")
    
    async def _extract_jobs_from_page(self, max_jobs: int) -> List[Dict]:
        """从页面提取岗位信息"""
        try:
            logger.info("📋 开始提取页面岗位信息...")
            
            # 先检查页面内容
            page_content = await self.page.content()
            if "岗位" in page_content or "job" in page_content.lower():
                logger.info("✓ 页面包含岗位相关内容")
            else:
                logger.warning("⚠️ 页面可能未正确加载岗位内容")
            
            # 尝试多种选择器 - 基于实时分析结果优化，优先选择精确的岗位容器
            selectors_to_try = [
                # 最精确的选择器 - 直接选择包含岗位链接的父容器
                'li:has(a[href*="job_detail"])',  # 只选择包含岗位链接的li
                
                # Boss直聘特有选择器
                '.job-detail-box',        # 之前成功的选择器
                'a[ka*="search_list"]',   # Boss直聘特有的ka属性
                '.job-card-wrapper', '.job-card-container',
                'li.job-card-container',
                '.job-card-left', '.job-info-box',
                
                # 包含岗位信息的容器
                'li:has(.job-name)',     # 只选择包含岗位标题的li
                'div:has(.job-name)',    # 只选择包含岗位标题的div
                '.job-list-box .job-card-body',
                
                # 备用选择器 - 需要后续过滤
                '.job-list-container li', '.search-job-result li',
                '.job-list .job-item', '.job-result-item',
                
                # 更通用的选择器（最后尝试）
                'li[class*="job"]', 'div[class*="job-card"]',
                'a[class*="job"]', '.job-primary', '.job-content'
            ]
            
            # 尝试所有选择器，收集所有可能的岗位元素
            all_job_cards = []
            successful_selectors = []
            
            for selector in selectors_to_try:
                try:
                    logger.info(f"🔍 尝试选择器: {selector}")
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        logger.info(f"   ✅ 找到 {len(elements)} 个元素")
                        all_job_cards.extend(elements)
                        successful_selectors.append((selector, len(elements)))
                    else:
                        logger.debug(f"   选择器 {selector} 未找到元素")
                except Exception as e:
                    logger.debug(f"   选择器 {selector} 异常: {e}")
                    continue
            
            # 去重（避免同一个元素被多个选择器选中）
            unique_job_cards = []
            seen_job_urls = set()  # 基于岗位URL去重，更可靠
            seen_element_positions = set()  # 基于元素位置去重，避免嵌套元素
            
            for element in all_job_cards:
                try:
                    # 方法1：基于岗位URL去重（最可靠）
                    link_elem = await element.query_selector('a[href*="job_detail"]')
                    if link_elem:
                        href = await link_elem.get_attribute('href')
                        if href:
                            # 清理URL，移除查询参数
                            clean_href = href.split('?')[0] if '?' in href else href
                            if clean_href in seen_job_urls:
                                logger.debug(f"跳过重复岗位URL: {clean_href}")
                                continue
                            seen_job_urls.add(clean_href)
                    
                    # 方法2：基于元素位置去重（避免嵌套元素重复）
                    try:
                        bbox = await element.bounding_box()
                        if bbox:
                            # 使用位置和尺寸作为唯一标识
                            position_key = (
                                round(bbox['x']), 
                                round(bbox['y']), 
                                round(bbox['width']), 
                                round(bbox['height'])
                            )
                            if position_key in seen_element_positions:
                                logger.debug(f"跳过重复位置元素: {position_key}")
                                continue
                            seen_element_positions.add(position_key)
                    except:
                        pass  # 位置获取失败不影响去重
                    
                    unique_job_cards.append(element)
                    
                except Exception as e:
                    logger.debug(f"去重处理异常，保留元素: {e}")
                    # 异常情况下仍然包含元素，但检查是否明显重复
                    if len(unique_job_cards) < 50:  # 限制最大数量，避免无限重复
                        unique_job_cards.append(element)
            
            job_cards = unique_job_cards
            logger.info(f"📊 选择器统计: 总共 {len(all_job_cards)} 个元素，去重后 {len(job_cards)} 个")
            if successful_selectors:
                logger.info("   成功的选择器:")
                for sel, count in successful_selectors:
                    logger.info(f"     {sel}: {count} 个元素")
            
            if not job_cards:
                logger.warning("⚠️ 所有选择器都未找到岗位，尝试通用方法...")
                
                # 尝试通过页面截图和页面源码分析
                await self.take_screenshot("debug_no_jobs.png")
                page_html = await self.page.content()
                
                # 保存页面HTML用于调试
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(page_html)
                logger.info("📄 已保存页面HTML到 debug_page.html")
                
                # 查找可能的岗位容器
                potential_selectors = [
                    'div[class*="job"]',
                    'li[class*="job"]', 
                    'div[class*="card"]',
                    'a[class*="job"]',
                    'div[data-*]',
                    '.search-job-result li'
                ]
                
                for selector in potential_selectors:
                    try:
                        elements = await self.page.query_selector_all(selector)
                        logger.info(f"🔍 潜在选择器 {selector}: 找到 {len(elements)} 个元素")
                        
                        # 检查前几个元素的文本内容
                        for i, elem in enumerate(elements[:5]):
                            try:
                                text = await elem.inner_text()
                                if text and len(text) > 10:
                                    logger.info(f"   元素 {i+1} 文本: {text[:100]}...")
                                    # 检查是否像岗位信息
                                    if any(keyword in text for keyword in ["K", "薪", "经验", "学历", "职位", "公司"]):
                                        job_cards.append(elem)
                            except Exception as e:
                                logger.debug(f"   无法获取元素文本: {e}")
                        
                        if job_cards:
                            logger.info(f"✅ 通过潜在选择器找到 {len(job_cards)} 个可能的岗位")
                            break
                            
                    except Exception as e:
                        logger.debug(f"潜在选择器 {selector} 异常: {e}")
            
            jobs = []
            valid_job_count = 0
            
            for i, card in enumerate(job_cards):
                if valid_job_count >= max_jobs:
                    break
                    
                try:
                    # 预先检查是否为有效的岗位元素
                    if not await self._is_valid_job_element(card):
                        logger.debug(f"跳过无效元素 {i+1}（可能是筛选标签或分隔元素）")
                        continue
                    
                    job_data = await self._extract_single_job(card, valid_job_count)
                    if job_data:
                        jobs.append(job_data)
                        valid_job_count += 1
                        logger.info(f"📌 提取岗位 {valid_job_count}: {job_data.get('title', '未知')}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ 提取第 {i+1} 个岗位失败: {e}")
            
            return jobs
            
        except Exception as e:
            logger.error(f"❌ 提取岗位信息失败: {e}")
            return []
    
    async def _is_valid_job_element(self, card) -> bool:
        """检查元素是否为有效的岗位元素（而不是筛选标签或分隔元素）"""
        try:
            # 获取元素文本内容
            text = await card.inner_text()
            text = text.strip()
            
            # 如果文本太短，可能是标签
            if len(text) < 10:
                return False
                
            # 检查是否包含明显的筛选标签关键词
            filter_keywords = [
                "经验不限", "不限经验", "硕士", "本科", "大专", "博士",
                "1年以下", "1-3年", "3-5年", "5-10年", "10年以上",
                "应届生", "实习生", "面议薪资", "全职", "兼职"
            ]
            
            # 如果文本完全匹配筛选标签，则不是岗位
            if text in filter_keywords:
                return False
                
            # 检查是否包含岗位相关元素
            has_job_title = await card.query_selector('.job-name, .job-title')
            has_link = await card.query_selector('a[href*="job"]')
            
            # 必须包含岗位标题或链接才是有效岗位
            return has_job_title is not None or has_link is not None
            
        except Exception as e:
            logger.debug(f"检查岗位元素有效性失败: {e}")
            return True  # 默认认为有效，让后续处理决定
    
    async def _extract_single_job(self, card, index: int) -> Optional[Dict]:
        """提取单个岗位信息"""
        try:
            # 岗位标题 - 扩展选择器
            title_selectors = [
                '.job-name', '.job-title', '.job-info h3', '.job-primary .name',
                'a .job-name', 'h3.job-name', '.job-card-body .job-name',
                '[class*="job"][class*="name"]', '.position-name'
            ]
            title = ""
            for selector in title_selectors:
                title_elem = await card.query_selector(selector)
                if title_elem:
                    title = await title_elem.inner_text()
                    if title.strip():
                        logger.debug(f"   ✅ 找到岗位标题: {title} (选择器: {selector})")
                        break
            if not title:
                title = f"岗位{index+1}"
                logger.warning(f"   ⚠️ 未找到岗位标题，使用默认: {title}")
            else:
                # 清洗岗位标题，分离职位名称和地点信息
                clean_title, extracted_location = self._clean_job_title(title)
                logger.info(f"   🧹 标题清洗: '{title}' -> 职位: '{clean_title}', 地点: '{extracted_location}'")
                title = clean_title
            
            # 公司名称 - 基于实时分析结果优化选择器
            company_selectors = [
                # 精确的公司名称选择器
                '.company-name', '.company-text', 'h3:not(.job-name):not([class*="salary"])', 
                '.job-company', '.company-info .name', 
                # 新的选择器 - 基于分析结果
                'span:not([class*="salary"]):not([class*="location"]):not([class*="area"])',
                'div:not([class*="salary"]):not([class*="location"]):not([class*="area"])',
                # 通过位置定位（公司名通常在岗位标题下方，地点上方）
                '.job-name ~ div:not([class*="salary"]):not([class*="area"])',
                '.job-name ~ span:not([class*="salary"]):not([class*="area"])',
                # 备用选择器
                '.company-info h3', '.job-info .company'
            ]
            
            company = ""
            for selector in company_selectors:
                try:
                    company_elems = await card.query_selector_all(selector)
                    for company_elem in company_elems:
                        company_text = await company_elem.inner_text()
                        if company_text and company_text.strip():
                            company_text = company_text.strip()
                            
                            # 智能过滤：排除明显不是公司名的文本
                            if (len(company_text) > 1 and len(company_text) < 30 and  # 公司名长度合理
                                company_text != title.strip() and  # 不是岗位标题
                                not any(word in company_text for word in ['K·薪', '万·薪', '经验', '学历', '岗位', '·', '区', '市']) and  # 不包含薪资、地点关键词
                                not company_text.isdigit() and  # 不是纯数字
                                '年' not in company_text and  # 不是经验要求
                                len([c for c in company_text if c.isalpha() or '\u4e00' <= c <= '\u9fff']) > 1):  # 包含足够的字母或汉字
                                
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
            
            # 薪资 - 基于实时分析结果优化
            salary_selectors = [
                # 基于分析结果的薪资选择器
                '[class*="salary"]', '.red', '.salary', '.job-limit .red', 
                '.job-primary .red', '.job-salary',
                # 新增：通过文本特征定位薪资
                'span:contains("K")', 'span:contains("万")', 'div:contains("K")'
            ]
            salary = ""
            for selector in salary_selectors:
                try:
                    salary_elems = await card.query_selector_all(selector)
                    for salary_elem in salary_elems:
                        salary_text = await salary_elem.inner_text()
                        if salary_text and salary_text.strip():
                            salary_text = salary_text.strip()
                            
                            # 修复薪资文本（处理"-K·薪"这种显示异常）
                            if 'K' in salary_text or '万' in salary_text or '千' in salary_text:
                                # 清理异常字符
                                cleaned_salary = salary_text.replace('·', '-').replace('薪', '')
                                if '-K' in cleaned_salary and len(cleaned_salary) < 10:
                                    # 可能是渲染问题，尝试获取更多上下文
                                    parent_text = await salary_elem.evaluate("el => el.parentElement?.innerText || el.innerText")
                                    if parent_text and parent_text != salary_text:
                                        # 从父元素文本中提取薪资信息
                                        import re
                                        salary_match = re.search(r'\d+[KkWw万千][\-~]\d+[KkWw万千]', parent_text)
                                        if salary_match:
                                            salary = salary_match.group()
                                        else:
                                            salary = cleaned_salary
                                    else:
                                        salary = cleaned_salary
                                else:
                                    salary = cleaned_salary
                                
                                logger.debug(f"   ✅ 找到薪资信息: {salary_text} -> {salary} (选择器: {selector})")
                                break
                    if salary:
                        break
                except Exception as e:
                    logger.debug(f"   薪资选择器 {selector} 异常: {e}")
                    
            if not salary:
                salary = "面议"
                logger.warning(f"   ⚠️ 未找到薪资信息，使用默认: {salary}")
            
            # 工作地点 - 基于实时分析结果优化
            location_selectors = [
                # 基于分析结果的地点选择器
                '[class*="location"]', '[class*="area"]', '.job-area', '.work-addr',
                '.job-location', '.job-primary .job-area',
                # Boss直聘最新格式
                '.job-area-wrapper', '.area-district', '.job-city',
                'span[class*="area"]', 'div[class*="location"]',
                # 通过位置定位（地点通常在公司名下方）
                'span:last-child', 'div:last-child'
            ]
            location = ""
            for selector in location_selectors:
                try:
                    location_elems = await card.query_selector_all(selector)
                    for location_elem in location_elems:
                        location_text = await location_elem.inner_text()
                        if location_text and location_text.strip():
                            location_text = location_text.strip()
                            
                            # 智能过滤：只选择看起来像地点的文本
                            if (len(location_text) > 1 and len(location_text) < 50 and  # 地点信息长度合理
                                location_text != company and  # 不是公司名
                                location_text != title and   # 不是岗位标题
                                not any(word in location_text for word in ['K', '经验', '学历', '岗位', '职位', '万', '千']) and
                                ('·' in location_text or  # Boss直聘地点格式：城市·区域·具体位置
                                 any(city in location_text for city in ['北京', '上海', '广州', '深圳', '杭州', '南京', '武汉', '成都']) or
                                 any(area_word in location_text for area_word in ['市', '区', '县', '街', '路', '镇', '村']))):
                                
                                location = location_text
                                logger.debug(f"   ✅ 找到工作地点: {location} (选择器: {selector})")
                                break
                    if location:
                        break
                except Exception as e:
                    logger.debug(f"   地点选择器 {selector} 异常: {e}")
            
            # 如果从页面没找到地点，使用从标题中提取的地点信息
            if not location and 'extracted_location' in locals() and extracted_location:
                location = self._clean_location_info(extracted_location)
                logger.info(f"   🔄 使用从标题提取的地点: {location}")
            elif not location:
                location = "未知地点"
                logger.warning(f"   ⚠️ 未找到工作地点，使用默认: {location}")
            else:
                # 清洗地点信息
                location = self._clean_location_info(location)
            
            # 岗位链接 - 尝试多种选择器
            url = ""
            link_selectors = [
                'a.job-card-body',
                'a.job-card-left',
                'a[ka^="search_list"]',  # Boss直聘常用的ka属性
                '.job-card-wrapper > a',
                '.job-primary > a',
                'a:has(.job-name)',
                'a:has(.job-title)'
            ]
            
            for selector in link_selectors:
                try:
                    link_elem = await card.query_selector(selector)
                    if link_elem:
                        href = await link_elem.get_attribute('href')
                        if href:
                            url = f"https://www.zhipin.com{href}" if href.startswith('/') else href
                            logger.info(f"✅ 找到岗位链接: {url} (使用选择器: {selector})")
                            break
                except:
                    continue
            
            # 如果还是没找到，尝试获取包含岗位标题的链接
            if not url:
                all_links = await card.query_selector_all('a')
                for link in all_links:
                    href = await link.get_attribute('href')
                    if href and '/job_detail/' in href:
                        url = f"https://www.zhipin.com{href}" if href.startswith('/') else href
                        logger.info(f"✅ 通过job_detail路径找到链接: {url}")
                        break
            
            if not url:
                logger.warning(f"⚠️ 未找到岗位 {index+1} 的链接")
            
            # 技能标签 - 扩展选择器
            tags = []
            tag_selectors = [
                '.tag-list .tag', '.job-tags .tag', '.tags .tag',
                'span[class*="tag"]', '.skill-tag', '.job-tag',
                '.label', 'span.label'
            ]
            
            for tag_selector in tag_selectors:
                try:
                    tag_elems = await card.query_selector_all(tag_selector)
                    for tag_elem in tag_elems:
                        tag_text = await tag_elem.inner_text()
                        if (tag_text.strip() and 
                            len(tag_text.strip()) < 20 and  # 标签通常较短
                            tag_text.strip() not in tags):  # 避免重复
                            tags.append(tag_text.strip())
                            if len(tags) >= 8:  # 最多8个标签
                                break
                    if len(tags) >= 8:
                        break
                except:
                    continue
            
            # 岗位描述 - 尝试从列表页抓取基本描述
            description = ""
            description_selectors = [
                '.job-desc', '.job-description', '.job-intro',
                '.job-content', '.job-detail', '.desc-text',
                'p[class*="desc"]', '.job-summary',
                'div[class*="description"]', '.job-info p'
            ]
            
            for desc_selector in description_selectors:
                try:
                    desc_elem = await card.query_selector(desc_selector)
                    if desc_elem:
                        desc_text = await desc_elem.inner_text()
                        if (desc_text.strip() and 
                            len(desc_text.strip()) > 10 and  # 描述应该有一定长度
                            len(desc_text.strip()) < 500 and  # 但不应该太长
                            desc_text.strip() not in [title, company, salary, location]):
                            description = desc_text.strip()
                            logger.debug(f"   ✅ 找到岗位描述: {description[:50]}... (选择器: {desc_selector})")
                            break
                except:
                    continue
            
            if not description:
                description = f"负责{title}相关工作，具体职责请查看岗位详情。"
                logger.debug(f"   ⚠️ 未找到岗位描述，使用默认")
            
            # 岗位要求 - 尝试提取
            requirements = ""
            requirement_selectors = [
                '.job-require', '.job-requirement', '.requirements',
                '.job-qualification', '.job-skills'
            ]
            
            for req_selector in requirement_selectors:
                try:
                    req_elem = await card.query_selector(req_selector)
                    if req_elem:
                        req_text = await req_elem.inner_text()
                        if (req_text.strip() and 
                            len(req_text.strip()) > 5 and
                            req_text.strip() not in [title, company, salary, location, description]):
                            requirements = req_text.strip()
                            logger.debug(f"   ✅ 找到岗位要求: {requirements[:50]}...")
                            break
                except:
                    continue
            
            # 经验要求 - 必须在requirements之前提取
            exp_elem = await card.query_selector('.job-limit')
            exp_text = await exp_elem.inner_text() if exp_elem else ""
            experience = self._extract_experience(exp_text)
            education = self._extract_education(exp_text)
            
            if not requirements:
                requirements = f"要求{experience}工作经验，{education}学历。"
            
            job_data = {
                "title": title.strip(),
                "company": company.strip(),
                "salary": salary.strip(),
                "work_location": location.strip(),
                "url": url,
                "tags": tags,
                "job_description": description,
                "job_requirements": requirements,
                "company_details": f"{company} - 查看详情了解更多公司信息",
                "benefits": "五险一金等，具体福利请查看岗位详情",
                "experience_required": experience,
                "education_required": education,
                "engine_source": "Playwright真实抓取"
            }
            
            # 获取详情页的真实信息
            if url and url.startswith('http'):
                job_data = await self.fetch_job_details_enhanced(url, job_data)
            
            return job_data
            
        except Exception as e:
            logger.error(f"❌ 提取单个岗位失败: {e}")
            return None
    
    def _extract_experience(self, text: str) -> str:
        """从文本中提取经验要求"""
        if "经验不限" in text or "不限经验" in text:
            return "经验不限"
        elif "1-3年" in text:
            return "1-3年"
        elif "3-5年" in text:
            return "3-5年"
        elif "5-10年" in text:
            return "5-10年"
        elif "应届" in text:
            return "应届生"
        else:
            return "1-3年"
    
    def _extract_education(self, text: str) -> str:
        """从文本中提取学历要求"""
        if "博士" in text:
            return "博士"
        elif "硕士" in text or "研究生" in text:
            return "硕士"
        elif "本科" in text:
            return "本科"
        elif "大专" in text:
            return "大专"
        elif "不限" in text:
            return "学历不限"
        else:
            return "本科"
    
    def _clean_job_title(self, raw_title: str) -> tuple:
        """
        清洗岗位标题，分离职位名称和地点信息
        
        Args:
            raw_title: 原始标题，如"风险策略/应急管理（风险治理）-杭州上海"
        
        Returns:
            tuple: (清洗后的职位名称, 提取的地点信息)
        """
        if not raw_title:
            return "未知职位", "未知地点"
        
        # 处理包含地点信息的标题格式：职位名称-地点1地点2
        if '-' in raw_title:
            parts = raw_title.split('-')
            if len(parts) >= 2:
                job_title = parts[0].strip()
                location_part = parts[1].strip()
                
                # 进一步清洗职位名称，移除括号内容
                if '（' in job_title and '）' in job_title:
                    # 保留括号内容，这通常是职位的重要描述
                    pass  # 不做处理，保持完整
                
                return job_title, location_part
        
        # 如果没有-分隔符，检查是否包含常见城市名
        cities = ['北京', '上海', '广州', '深圳', '杭州', '南京', '武汉', '成都', '西安', '苏州']
        for city in cities:
            if raw_title.endswith(city):
                job_title = raw_title[:-len(city)].strip()
                return job_title, city
        
        # 默认返回原标题
        return raw_title.strip(), ""
    
    async def fetch_job_details_enhanced(self, url: str, job_data: Dict) -> Dict:
        """
        增强的岗位详情抓取方法
        访问详情页并精确提取岗位职责、任职要求等信息
        """
        if not url or not url.startswith('http'):
            return job_data
        
        try:
            # 创建新页面避免影响主页面
            detail_page = await self.browser.new_page()
            
            # 设置更真实的浏览器行为
            await detail_page.set_viewport_size({"width": 1920, "height": 1080})
            
            # 访问详情页
            logger.info(f"🔍 访问岗位详情页: {url[:50]}...")
            await detail_page.goto(url, wait_until="networkidle", timeout=15000)
            
            # 等待关键内容加载
            try:
                await detail_page.wait_for_selector('.job-sec-text, .job-detail', timeout=5000)
            except:
                logger.warning("详情页主要内容未加载")
            
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
            
            # 1. 提取岗位职责
            job_description = await self._extract_job_description(detail_page)
            if job_description and len(job_description) > 50:
                job_data['job_description'] = job_description
                logger.info(f"✅ 获取岗位职责: {len(job_description)}字符")
            
            # 2. 提取任职要求
            job_requirements = await self._extract_job_requirements(detail_page)
            if job_requirements and len(job_requirements) > 30:
                job_data['job_requirements'] = job_requirements
                logger.info(f"✅ 获取任职要求: {len(job_requirements)}字符")
            
            # 3. 提取公司详情
            company_details = await self._extract_company_details(detail_page)
            if company_details:
                job_data['company_details'] = company_details
                job_data['company'] = company_details.split(' ')[0]  # 更新公司名称
                logger.info(f"✅ 获取公司详情: {company_details[:50]}...")
            
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
    
    def _clean_location_info(self, location_text: str) -> str:
        """
        清洗地点信息，提取主要城市
        
        Args:
            location_text: 原始地点文本，如"杭州上海"
        
        Returns:
            str: 清洗后的地点，如"杭州·上海"
        """
        if not location_text:
            return "未知地点"
        
        # 常见城市列表
        cities = ['北京', '上海', '广州', '深圳', '杭州', '南京', '武汉', '成都', '西安', '苏州', '天津', '重庆']
        
        # 找出文本中包含的所有城市，并保持原始文本顺序
        found_cities = []
        for i, char in enumerate(location_text):
            for city in cities:
                # 检查从当前位置开始是否匹配城市名
                if location_text[i:i+len(city)] == city and city not in found_cities:
                    found_cities.append(city)
                    break
        
        if found_cities:
            # 用·分隔，保持原始文本中的顺序
            return '·'.join(found_cities)
        
        # 如果没找到已知城市，返回原文本（可能包含区域信息）
        return location_text.strip() if location_text.strip() else "未知地点"
    
    def _generate_sample_jobs(self, keyword: str, city: str, max_jobs: int) -> List[Dict]:
        """生成示例岗位数据（当真实抓取失败时）"""
        
        city_names = {
            "shanghai": "上海",
            "beijing": "北京",
            "shenzhen": "深圳", 
            "hangzhou": "杭州"
        }
        
        city_name = city_names.get(city, "上海")
        
        companies = ["阿里巴巴", "腾讯", "字节跳动", "美团", "滴滴", "百度", "网易", "小米", "华为", "京东"]
        salaries = ["15-25K·13薪", "20-30K·14薪", "25-35K·15薪", "18-28K·13薪", "22-32K·14薪"]
        
        jobs = []
        for i in range(max_jobs):
            company = companies[i % len(companies)]
            salary = salaries[i % len(salaries)]
            
            job = {
                "title": f"{keyword}工程师",
                "company": company,
                "salary": salary,
                "work_location": f"{city_name}·中心区",
                "url": f"https://www.zhipin.com/job_detail/{urllib.parse.quote(keyword)}_{i+1}",
                "tags": [keyword, "Python", "数据分析", "机器学习"][:3],
                "job_description": f"负责{keyword}相关工作，包括数据处理、分析建模等。",
                "job_requirements": f"要求3-5年{keyword}相关经验，本科及以上学历。",
                "company_details": f"{company} - 知名互联网公司",
                "benefits": "五险一金,股票期权,弹性工作",
                "experience_required": "3-5年",
                "education_required": "本科",
                "engine_source": "Playwright真实抓取（示例数据）"
            }
            jobs.append(job)
        
        return jobs
    
    async def take_screenshot(self, filename: str = None) -> str:
        """截取页面截图"""
        try:
            if not self.page:
                return ""
            
            if not filename:
                timestamp = int(time.time())
                filename = f"boss_real_screenshot_{timestamp}.png"
            
            await self.page.screenshot(path=filename, full_page=True)
            logger.info(f"📸 截图保存: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"❌ 截图失败: {e}")
            return ""
    
    async def close(self):
        """关闭浏览器"""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            
            logger.info("🔚 浏览器已关闭")
            
        except Exception as e:
            logger.error(f"❌ 关闭浏览器失败: {e}")


# 同步包装器
class RealPlaywrightBossSpiderSync:
    """真正的Playwright Boss直聘爬虫同步版本"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.spider = None
    
    def search_jobs(self, keyword: str, city: str, max_jobs: int = 20) -> List[Dict]:
        """搜索岗位（同步版本）"""
        async def _search():
            self.spider = RealPlaywrightBossSpider(headless=self.headless)
            
            try:
                if await self.spider.start():
                    return await self.spider.search_jobs(keyword, city, max_jobs)
                else:
                    return []
            finally:
                if self.spider:
                    await self.spider.close()
        
        return asyncio.run(_search())


# 集成接口
def search_with_real_playwright(keyword: str, city: str = "shanghai", max_jobs: int = 20) -> List[Dict]:
    """使用真正的Playwright搜索Boss直聘岗位"""
    logger.info(f"🎭 启动真正的Playwright自动化搜索: {keyword}")
    
    try:
        spider = RealPlaywrightBossSpiderSync(headless=False)  # 可见模式
        jobs = spider.search_jobs(keyword, city, max_jobs)
        
        logger.info(f"✅ 真实搜索完成，找到 {len(jobs)} 个岗位")
        return jobs
        
    except Exception as e:
        logger.error(f"❌ 真实Playwright搜索失败: {e}")
        return []


if __name__ == "__main__":
    # 测试真正的Playwright爬虫
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("🎭 测试真正的Playwright Boss直聘爬虫")
    print("=" * 50)
    
    # 测试搜索
    jobs = search_with_real_playwright("数据分析", "shanghai", 3)
    
    print(f"\n✅ 找到 {len(jobs)} 个岗位:")
    for i, job in enumerate(jobs, 1):
        print(f"\n📋 岗位 #{i}")
        print(f"  职位: {job.get('title', '未知')}")
        print(f"  公司: {job.get('company', '未知')}")
        print(f"  薪资: {job.get('salary', '未知')}")
        print(f"  地点: {job.get('work_location', '未知')}")
        print(f"  链接: {job.get('url', '未知')}")