#!/usr/bin/env python3
"""
真正的Playwright自动化Boss直聘爬虫
实现可见的浏览器操作和真实数据提取
"""

import asyncio
import logging
import urllib.parse
import time
import os
from pathlib import Path
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from .enhanced_extractor import EnhancedDataExtractor
from .session_manager import SessionManager
from .retry_handler import RetryHandler, RetryConfig, ErrorType, RetryStrategy, retry_on_error
from .large_scale_crawler import LargeScaleCrawler, LargeScaleProgressTracker

logger = logging.getLogger(__name__)


class RealPlaywrightBossSpider:
    """真正的Playwright Boss直聘爬虫"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.enhanced_extractor = EnhancedDataExtractor()  # 集成增强提取器
        self.session_manager = SessionManager()  # 集成会话管理器
        self.retry_handler = RetryHandler()  # 集成重试处理器
        
        # 加载配置
        try:
            from config.config_manager import ConfigManager
            self.config_manager = ConfigManager()
            self.browser_config = self.config_manager.get_app_config('crawler', {}).get('browser', {})
        except:
            logger.warning("无法加载配置管理器，使用默认配置")
            self.config_manager = None
            self.browser_config = {}
        
        # Boss直聘城市代码映射 (与app_config.yaml保持一致)
        self.city_codes = {
            "shanghai": "101020100",   # 上海 (修复：之前错误为101210100)
            "beijing": "101010100",    # 北京 (正确)
            "shenzhen": "101280600",   # 深圳 (正确)
            "hangzhou": "101210100"    # 杭州 (修复：之前错误为101210300->嘉兴)
        }
        
    @retry_on_error(max_attempts=3, base_delay=2.0, strategy=RetryStrategy.EXPONENTIAL_BACKOFF)
    async def start(self) -> bool:
        """启动浏览器 - 使用持久化上下文保持登录状态"""
        logger.info("🎭 启动真正的Playwright浏览器...")
        
        self.playwright = await async_playwright().start()
        
        # 检查是否使用持久化上下文
        use_persistent = self.browser_config.get('use_persistent_context', True)
        user_data_dir = self.browser_config.get('user_data_dir', './browser_profile/boss_zhipin')
        
        if use_persistent:
            # 创建用户数据目录
            user_data_path = Path(user_data_dir).absolute()
            user_data_path.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"📁 使用持久化浏览器配置: {user_data_path}")
            
            # 检查是否是首次使用
            is_first_run = not (user_data_path / "Default").exists()
            if is_first_run:
                logger.info("🆕 检测到首次运行，将引导您进行登录...")
                logger.info("👤 请在打开的浏览器窗口中手动登录Boss直聘")
                logger.info("✅ 登录成功后，您的登录状态将被自动保存")
            
            # 使用持久化上下文启动浏览器
            logger.info(f"🚀 正在启动浏览器，headless模式: {self.headless}")
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_path),
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--start-maximized'
                ],
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # 获取或创建页面
            pages = self.context.pages
            self.page = pages[0] if pages else await self.context.new_page()
            logger.info(f"✅ 浏览器启动成功！headless={self.headless}, 页面数: {len(pages)}")
            
        else:
            # 传统方式启动浏览器
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--start-maximized'
                ]
            )
            
            # 创建新上下文
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            self.page = await self.context.new_page()
        
        logger.info("🖥️ Chrome浏览器窗口已打开，你应该能看到它！")
        
        # 确保窗口在前台
        await self.page.bring_to_front()
        logger.info("📱 浏览器窗口已设置为前台显示")
        
        logger.info("✅ Playwright浏览器启动成功")
        return True
    
    async def search_jobs(self, keyword: str, city: str, max_jobs: int = 20) -> List[Dict]:
        """搜索岗位 - 带完善的错误处理和重试机制"""
        
        # 使用重试机制执行核心搜索逻辑
        search_config = RetryConfig(
            max_attempts=3,
            base_delay=5.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            allowed_error_types=[
                ErrorType.NETWORK_ERROR,
                ErrorType.TIMEOUT_ERROR, 
                ErrorType.PAGE_LOAD_ERROR,
                ErrorType.ELEMENT_NOT_FOUND
            ]
        )
        
        try:
            return await self.retry_handler.execute_with_retry(
                self._search_jobs_core,
                keyword, city, max_jobs,
                config=search_config,
                context={'operation': 'search_jobs', 'keyword': keyword, 'city': city}
            )
        except Exception as e:
            logger.error(f"❌ 搜索岗位最终失败: {e}")
            # 记录详细的错误信息用于分析
            await self._log_search_failure(keyword, city, e)
            return []
    
    async def _search_jobs_core(self, keyword: str, city: str, max_jobs: int) -> List[Dict]:
        """核心搜索逻辑（内部方法，供重试使用）"""
        if not self.page:
            raise RuntimeError("浏览器未启动")
        
        # 首先确保已登录
        logger.info("🔐 检查登录状态...")
        if not await self._ensure_logged_in():
            raise RuntimeError("登录失败，无法继续搜索")
        
        # 获取城市代码
        city_code = self.city_codes.get(city, "101210100")  # 默认上海
        
        logger.info(f"🔍 开始搜索: {keyword} | 城市: {city} ({city_code}) | 数量: {max_jobs}")
        
        # 使用更自然的搜索方式
        logger.info(f"🔍 准备搜索: {keyword}")
        
        # 确保在首页（登录后可能还在登录页或其他页面）
        logger.info("🏠 导航到Boss直聘首页...")
        try:
            await self.page.goto("https://www.zhipin.com", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
        except Exception as e:
            logger.warning(f"首页加载超时，尝试继续: {e}")
        
        # 直接使用URL导航（更稳定高效）
        logger.info("🔍 使用URL导航进行搜索...")
        encoded_keyword = urllib.parse.quote(keyword)
        search_url = f"https://www.zhipin.com/web/geek/job?query={encoded_keyword}&city={city_code}"
        await self._navigate_to_search_page(search_url)
        
        # 处理页面加载和预处理（传递目标岗位数量）
        await self._prepare_search_page(max_jobs)
        
        # 根据岗位数量选择合适的抓取策略
        if max_jobs <= 30:
            # 小规模抓取：使用增强提取器
            logger.info("🚀 启用增强数据提取引擎（小规模模式）...")
            jobs = await self.enhanced_extractor.extract_job_listings_enhanced(self.page, max_jobs)
        else:
            # 大规模抓取：使用大规模爬虫引擎
            logger.info(f"🏭 启用大规模抓取引擎（目标: {max_jobs} 个岗位）...")
            large_scale_crawler = LargeScaleCrawler(self.page, self.session_manager, self.retry_handler)
            jobs = await large_scale_crawler.extract_large_scale_jobs(max_jobs)
        
        # 验证结果
        if not jobs:
            await self._handle_no_jobs_found()
            return []
        
        logger.info(f"✅ 成功提取 {len(jobs)} 个岗位基础信息")
        
        # 获取详情页信息
        logger.info("📄 开始获取岗位详情...")
        jobs_with_details = await self._fetch_job_details(jobs)
        
        logger.info(f"✅ 完成详情获取，共 {len(jobs_with_details)} 个岗位")
        return jobs_with_details
    
    @retry_on_error(max_attempts=3, base_delay=2.0)
    async def _navigate_to_search_page(self, search_url: str) -> None:
        """导航到搜索页面"""
        logger.info("🔗 正在导航到Boss直聘搜索页面...")
        logger.info("👀 请观察浏览器窗口，你应该能看到页面加载过程")
        
        await self.page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
    
    async def _prepare_search_page(self, target_jobs: int = 20) -> None:
        """准备搜索页面（页面加载、滚动等）
        
        Args:
            target_jobs: 目标岗位数量
        """
        # 等待页面完全加载完成
        logger.info("⏳ 等待页面完全加载...")
        
        # 检查页面是否还在加载状态
        max_wait_time = 60  # 最大等待60秒
        wait_start = time.time()
        
        while time.time() - wait_start < max_wait_time:
            try:
                # 检查页面标题是否还是"请稍候"
                title = await self.page.title()
                if title != "请稍候":
                    logger.info(f"✅ 页面加载完成，标题: {title}")
                    break
                
                # 检查是否有岗位内容出现
                job_indicators = await self.page.query_selector_all('li, .job-card, [data-jobid], .job-item')
                if job_indicators:
                    logger.info(f"✅ 检测到 {len(job_indicators)} 个潜在岗位元素")
                    break
                
                logger.info("⏳ 页面仍在加载中，继续等待...")
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.debug(f"检查页面状态时出错: {e}")
                await asyncio.sleep(2)
        
        # 额外等待确保动态内容加载
        await asyncio.sleep(5)
        
        # 智能滚动页面以加载更多岗位
        logger.info(f"📜 滚动页面以触发更多岗位加载（目标: {target_jobs} 个）...")
        await self._smart_scroll_page(target_jobs)
        
        # 滚动回顶部
        await self.page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(3)
        
        logger.info("📄 页面已准备完成，开始处理可能的弹窗...")
        
        # 检查是否需要登录或有验证码
        await self._handle_login_or_captcha()
    
    async def _smart_scroll_page(self, target_jobs: int = 20) -> None:
        """智能滚动页面策略（优化版）
        
        Args:
            target_jobs: 目标岗位数量
        """
        try:
            # 先检查页面是否稳定
            await self._wait_for_page_stable()
            
            # 获取当前岗位数量
            current_job_count = await self._count_current_jobs()
            logger.info(f"📊 当前页面岗位数: {current_job_count}，目标: {target_jobs}")
            
            # 如果已经达到目标数量，直接返回
            if current_job_count >= target_jobs:
                logger.info(f"✅ 已达到目标岗位数量")
                return
            
            # 安全地获取页面高度
            initial_height = await self.page.evaluate("""
                () => {
                    return Math.max(
                        document.body?.scrollHeight || 0,
                        document.documentElement?.scrollHeight || 0,
                        window.innerHeight || 0
                    );
                }
            """)
            
            logger.info(f"📜 开始智能滚动，初始高度: {initial_height}")
            
            # 根据需要的岗位数量动态调整滚动次数
            max_scroll_attempts = max(8, (target_jobs // 8) + 3)  # 至少8次尝试，每8个岗位增加3次
            no_change_count = 0  # 连续无变化计数
            
            for scroll_attempt in range(max_scroll_attempts):
                # 检查是否仍在同一页面
                current_url = self.page.url
                
                # 渐进式滚动，避免触发页面跳转
                scroll_steps = 3
                for step in range(scroll_steps):
                    await self.page.evaluate(f"""
                        () => {{
                            const targetY = window.scrollY + (window.innerHeight * 0.8);
                            window.scrollTo({{
                                top: targetY,
                                behavior: 'smooth'
                            }});
                        }}
                    """)
                    await asyncio.sleep(0.5)
                
                # 缓慢滚动到底部以更好地触发懒加载
                await self.page.evaluate("""
                    () => {
                        const targetY = document.body.scrollHeight;
                        const currentY = window.scrollY;
                        const step = (targetY - currentY) / 3;
                        
                        // 分3步滚动到底部
                        let steps = 0;
                        function smoothScroll() {
                            if (steps < 3) {
                                steps++;
                                window.scrollTo({
                                    top: currentY + (step * steps),
                                    behavior: 'smooth'
                                });
                                setTimeout(smoothScroll, 800);
                            }
                        }
                        smoothScroll();
                    }
                """)
                await asyncio.sleep(4)  # 给更多时间让内容加载
                
                # 检查是否发生了页面跳转
                if self.page.url != current_url:
                    logger.warning("⚠️ 检测到页面跳转，停止滚动")
                    break
                
                # 安全地检查是否有新内容加载
                new_height = await self.page.evaluate("""
                    () => {
                        return Math.max(
                            document.body?.scrollHeight || 0,
                            document.documentElement?.scrollHeight || 0,
                            window.innerHeight || 0
                        );
                    }
                """)
                
                logger.info(f"   滚动 {scroll_attempt + 1}/{max_scroll_attempts}，页面高度: {initial_height} -> {new_height}")
                
                # 如果页面高度没有显著变化
                if abs(new_height - initial_height) < 100:
                    no_change_count += 1
                    logger.info(f"   页面高度变化不大 (连续{no_change_count}次)")
                    
                    # 检查当前岗位数量
                    current_job_count = await self._count_current_jobs()
                    logger.info(f"   当前岗位数: {current_job_count}/{target_jobs}")
                    
                    if current_job_count >= target_jobs:
                        logger.info(f"✅ 已达到目标岗位数量")
                        break
                    
                    # 如果连续3次没有变化且岗位数量还不够，尝试其他策略
                    if no_change_count >= 3:
                        if current_job_count < target_jobs:
                            logger.info("   尝试查找加载更多按钮或翻页...")
                            # 尝试查找加载更多按钮
                            try:
                                load_more_buttons = await self.page.query_selector_all(
                                    'button:has-text("加载更多"), a:has-text("查看更多"), '
                                    '.load-more, .more-btn, [class*="more"], [class*="load"]'
                                )
                                if load_more_buttons:
                                    for btn in load_more_buttons[:1]:  # 只点击第一个
                                        if await btn.is_visible():
                                            await btn.click()
                                            logger.info("   点击了加载更多按钮")
                                            await asyncio.sleep(3)
                                            no_change_count = 0
                                            break
                                else:
                                    # 尝试查找下一页按钮
                                    next_page = await self.page.query_selector(
                                        'a:has-text("下一页"), .next-page, [class*="next"]'
                                    )
                                    if next_page and await next_page.is_visible():
                                        await next_page.click()
                                        logger.info("   点击了下一页按钮")
                                        await asyncio.sleep(5)
                                        no_change_count = 0
                                    else:
                                        logger.info("   未找到加载更多或翻页按钮，已到达最后一页")
                                        break
                            except Exception as e:
                                logger.debug(f"尝试加载更多时出错: {e}")
                                break
                        else:
                            logger.info("   已到达页面底部")
                            break
                else:
                    no_change_count = 0  # 重置计数
                    initial_height = new_height
                    
                    # 等待新内容加载
                    await asyncio.sleep(3)
                
        except Exception as e:
            if "Execution context was destroyed" in str(e):
                logger.info("⚠️ 页面导航导致滚动中断（正常现象）")
            else:
                logger.warning(f"⚠️ 智能滚动出现异常: {str(e)}")
            # 不再尝试降级滚动，避免触发更多错误
    
    async def _count_current_jobs(self) -> int:
        """统计当前页面的岗位数量"""
        try:
            # 使用多个选择器查找岗位元素，取最大值
            selectors = [
                'li.job-card-wrapper',
                'li[data-jid]', 
                '.job-card-left',
                'li:has(a[href*="job_detail"])',
                'li[class*="job"]',
                'div[class*="job-card"]',
                '.job-list-item',  # 添加更多可能的选择器
                '[data-jobid]',
                'a[ka*="search_list"]'
            ]
            
            max_count = 0
            counts = {}
            
            for selector in selectors:
                try:
                    jobs = await self.page.query_selector_all(selector)
                    count = len(jobs) if jobs else 0
                    counts[selector] = count
                    max_count = max(max_count, count)
                except Exception as e:
                    logger.debug(f"选择器 {selector} 查询失败: {e}")
                    continue
            
            # 记录详细的计数信息用于调试
            if max_count > 0:
                best_selector = max(counts, key=counts.get)
                logger.debug(f"岗位计数详情: {counts}, 最佳选择器: {best_selector}")
            
            return max_count
        except Exception as e:
            logger.debug(f"统计岗位数量失败: {e}")
            return 0
    
    async def _wait_for_page_stable(self) -> None:
        """等待页面稳定"""
        try:
            # 等待网络空闲
            await self.page.wait_for_load_state("networkidle", timeout=5000)
        except:
            # 如果网络一直不空闲，至少等待DOM加载完成
            await self.page.wait_for_load_state("domcontentloaded", timeout=3000)
    
    async def _handle_no_jobs_found(self) -> None:
        """处理未找到岗位的情况"""
        screenshot_path = await self.take_screenshot()
        logger.warning(f"⚠️ 未找到岗位，已截图: {screenshot_path}")
        
        # 检查页面是否有错误信息
        error_indicators = [
            '.empty-result', '.no-result', '.error-page', 
            ':has-text("没有找到")', ':has-text("暂无数据")'
        ]
        
        for selector in error_indicators:
            try:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    error_text = await element.inner_text()
                    logger.warning(f"页面显示错误信息: {error_text}")
                    break
            except:
                continue
        
        logger.error("❌ 真实抓取失败，未找到任何岗位数据")
        logger.info("🚫 不生成示例数据，保持数据真实性")
    
    async def _log_search_failure(self, keyword: str, city: str, exception: Exception) -> None:
        """记录搜索失败的详细信息"""
        try:
            failure_info = {
                'timestamp': time.time(),
                'keyword': keyword,
                'city': city,
                'error_type': type(exception).__name__,
                'error_message': str(exception),
                'page_url': self.page.url if self.page else 'unknown',
                'retry_stats': self.retry_handler.get_retry_stats()
            }
            
            # 保存失败信息到文件
            import json
            failure_file = f"search_failure_{int(time.time())}.json"
            with open(failure_file, 'w', encoding='utf-8') as f:
                json.dump(failure_info, f, ensure_ascii=False, indent=2)
            
            logger.info(f"🔍 搜索失败详情已保存: {failure_file}")
            
        except Exception as e:
            logger.debug(f"记录搜索失败信息时出错: {e}")
    
    async def _ensure_logged_in(self) -> bool:
        """确保已登录Boss直聘 - 支持持久化登录状态"""
        try:
            # 首先导航到Boss直聘首页
            logger.info("🏠 导航到Boss直聘首页...")
            try:
                await self.page.goto("https://www.zhipin.com", wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                logger.warning(f"首页加载超时，尝试继续: {e}")
                # 即使超时也尝试继续，因为页面可能已经部分加载
            await asyncio.sleep(3)
            
            # 如果使用持久化上下文，先检查是否已经登录
            use_persistent = self.browser_config.get('use_persistent_context', True)
            if use_persistent:
                # 定义登录状态检查的选择器
                login_indicators = [
                    'a[href*="/web/geek/chat"]',  # 聊天入口
                    '.nav-figure img',  # 用户头像
                    'a[ka="header-username"]',  # 用户名链接
                    '.header-login-name'  # 登录名
                ]
                
                # 更严格的登录状态检查
                # 先检查是否有登录按钮（如果有说明未登录）
                login_button = await self.page.query_selector('a[ka="header-login"], .btn-sign, .sign-in')
                if login_button:
                    logger.info("❌ 检测到登录按钮，用户未登录")
                else:
                    # 检查登录状态的多种方式（更严格）
                    for indicator in login_indicators:
                        try:
                            element = await self.page.query_selector(indicator)
                            if element:
                                logger.info(f"✅ 检测到登录标识: {indicator}")
                                logger.info("✅ 使用持久化登录状态，无需重新登录")
                                return True
                        except:
                            continue
                
                # 如果没有检测到登录状态，引导用户登录
                logger.info("❌ 未检测到登录状态")
                logger.info("🔐 请手动登录Boss直聘...")
                logger.info("👉 登录步骤：")
                logger.info("   1. 点击页面右上角的'登录'按钮")
                logger.info("   2. 使用手机号验证码或扫码登录")
                logger.info("   3. 登录成功后，在控制台按Enter继续")
                
                # 等待用户登录 - 使用异步等待而非阻塞输入
                logger.info("\n⏸️  请在浏览器中完成登录...")
                logger.info("💡 提示：登录成功后，程序会自动检测并继续")
                
                # 循环检测登录状态，每5秒检查一次
                max_wait_time = 300  # 最多等待5分钟
                check_interval = 5   # 每5秒检查一次
                waited_time = 0
                
                while waited_time < max_wait_time:
                    await asyncio.sleep(check_interval)
                    waited_time += check_interval
                    
                    # 检查是否已登录
                    for indicator in login_indicators:
                        try:
                            element = await self.page.query_selector(indicator)
                            if element:
                                logger.info(f"✅ 检测到登录成功！")
                                await asyncio.sleep(2)  # 等待页面稳定
                                return True
                        except:
                            continue
                    
                    # 显示等待进度
                    remaining_time = max_wait_time - waited_time
                    logger.info(f"⏳ 等待登录中... (剩余 {remaining_time} 秒)")
                
                logger.error("❌ 登录超时，请重试")
                return False
                
            else:
                # 使用传统的会话管理方式
                # 尝试加载已保存的会话
                if await self.session_manager.load_session(self.page.context, "zhipin.com"):
                    logger.info("🍪 已加载保存的会话，刷新页面...")
                    await self.page.reload()
                    await asyncio.sleep(3)
                    
                    # 检查是否登录成功
                    if await self.session_manager.check_login_status(self.page, "zhipin.com"):
                        logger.info("✅ 使用保存的会话登录成功!")
                        return True
                    else:
                        logger.warning("⚠️ 保存的会话已失效，需要重新登录")
                
                # 等待用户手动登录
                if await self.session_manager.wait_for_login(self.page, timeout=300, domain="zhipin.com"):
                    # 保存新的会话
                    await self.session_manager.save_session(self.page.context, self.page, "zhipin.com")
                    return True
                else:
                    logger.error("❌ 登录失败")
                    return False
            
        except Exception as e:
            logger.error(f"❌ 登录过程出错: {e}")
            return False
    
    def get_session_info(self) -> Dict:
        """获取当前会话信息"""
        return self.session_manager.get_session_info()
    
    async def _fetch_job_details(self, jobs: List[Dict]) -> List[Dict]:
        """获取岗位详细信息"""
        jobs_with_details = []
        
        for i, job in enumerate(jobs):
            try:
                logger.info(f"📋 获取第 {i+1}/{len(jobs)} 个岗位详情: {job.get('title', '未知岗位')}")
                
                # 检查是否有有效的URL
                job_url = job.get('url', '')
                if not job_url or not job_url.startswith('http'):
                    logger.warning(f"⚠️ 岗位 {i+1} 没有有效URL，跳过详情获取")
                    jobs_with_details.append(job)
                    continue
                
                # 获取详情页数据
                details = await self._extract_job_detail_page(job_url)
                
                # 合并基础信息和详情信息
                enhanced_job = {**job, **details}
                jobs_with_details.append(enhanced_job)
                
                # 添加延迟避免请求过于频繁
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ 获取岗位 {i+1} 详情失败: {e}")
                # 保留原始数据
                jobs_with_details.append(job)
                continue
        
        return jobs_with_details
    
    async def _extract_job_detail_page(self, job_url: str) -> Dict:
        """提取岗位详情页信息"""
        try:
            logger.debug(f"🔗 访问详情页: {job_url}")
            
            # 导航到详情页
            await self.page.goto(job_url, wait_until="domcontentloaded", timeout=30000)  # 增加到30秒
            await asyncio.sleep(2)
            
            # 等待页面加载完成
            await self._wait_for_detail_page_load()
            
            # 提取工作职责
            job_description = await self._extract_job_description()
            
            # 提取任职资格  
            job_requirements = await self._extract_job_requirements()
            
            # 提取公司信息
            company_details = await self._extract_company_details()
            
            # 提取福利待遇
            benefits = await self._extract_benefits()
            
            # 提取完整薪资信息
            salary_info = await self._extract_salary_info()
            
            result = {
                'job_description': job_description,
                'job_requirements': job_requirements, 
                'company_details': company_details,
                'benefits': benefits,
                'detail_extraction_success': True
            }
            
            # 如果提取到了更完整的薪资信息，更新它
            if salary_info and salary_info != "薪资面议":
                result['salary'] = salary_info
                
            return result
            
        except Exception as e:
            logger.error(f"❌ 提取详情页失败: {e}")
            return {
                'job_description': '详情页加载失败，请直接访问岗位链接查看',
                'job_requirements': '详情页加载失败，请直接访问岗位链接查看',
                'company_details': '详情页加载失败',
                'benefits': '详情页加载失败',
                'detail_extraction_success': False
            }
    
    async def _wait_for_detail_page_load(self) -> None:
        """等待详情页加载完成"""
        try:
            # 等待关键元素出现
            key_selectors = [
                '.job-sec-text',  # 岗位描述区域
                '.job-detail-section',  # 详情区域
                '.job-primary',  # 主要信息区域
                '.job-banner'  # 横幅区域
            ]
            
            # 尝试等待任意一个关键选择器出现
            for selector in key_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=3000)
                    logger.debug(f"✅ 详情页关键元素已加载: {selector}")
                    break
                except:
                    continue
            
            # 额外等待确保动态内容加载
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.debug(f"等待详情页加载时出错: {e}")
    
    async def _extract_job_description(self) -> str:
        """提取工作职责"""
        selectors = [
            '.job-sec-text',  # Boss直聘常用的职责描述选择器
            '.job-detail-text .text',
            '.job-description .text-desc',
            '.job-detail .job-sec .text-desc',
            '[class*="job-sec"] .text',
            '.text-desc',
            '.job-content .text'
        ]
        
        for selector in selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    # 获取所有匹配元素的文本
                    texts = []
                    for element in elements:
                        text = await element.inner_text()
                        if text and text.strip():
                            texts.append(text.strip())
                    
                    if texts:
                        # 查找包含"职责"、"工作内容"等关键词的部分
                        for text in texts:
                            if any(keyword in text for keyword in ['职责', '工作内容', '岗位职责', '主要工作']):
                                logger.debug(f"✅ 找到工作职责: {selector}")
                                return text
                        
                        # 如果没有找到特定关键词，返回第一个较长的文本
                        for text in texts:
                            if len(text) > 50:  # 职责描述通常较长
                                logger.debug(f"✅ 找到工作描述: {selector}")
                                return text
                                
            except Exception as e:
                logger.debug(f"提取工作职责失败 {selector}: {e}")
                continue
        
        return "工作职责信息未找到，请查看岗位详情页"
    
    async def _extract_job_requirements(self) -> str:
        """提取任职资格"""
        selectors = [
            '.job-sec-text',
            '.job-detail-text .text', 
            '.job-requirements .text-desc',
            '.job-detail .job-sec .text-desc',
            '[class*="job-sec"] .text',
            '.text-desc',
            '.job-content .text'
        ]
        
        for selector in selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    texts = []
                    for element in elements:
                        text = await element.inner_text()
                        if text and text.strip():
                            texts.append(text.strip())
                    
                    if texts:
                        # 查找包含"要求"、"资格"、"条件"等关键词的部分
                        for text in texts:
                            if any(keyword in text for keyword in ['任职', '要求', '资格', '条件', '技能', '经验']):
                                logger.debug(f"✅ 找到任职要求: {selector}")
                                return text
                        
                        # 如果有多个文本块，取第二个（第一个通常是职责）
                        if len(texts) >= 2:
                            logger.debug(f"✅ 找到任职要求（第二段）: {selector}")
                            return texts[1]
                            
            except Exception as e:
                logger.debug(f"提取任职要求失败 {selector}: {e}")
                continue
        
        return "任职要求信息未找到，请查看岗位详情页"
    
    async def _extract_company_details(self) -> str:
        """提取公司详情"""
        selectors = [
            '.company-info .company-text',
            '.company-description',
            '.company-detail-text',
            '.company-info .text'
        ]
        
        for selector in selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and text.strip():
                        logger.debug(f"✅ 找到公司详情: {selector}")
                        return text.strip()
            except Exception as e:
                logger.debug(f"提取公司详情失败 {selector}: {e}")
                continue
        
        return "公司详情信息未找到"
    
    async def _extract_salary_info(self) -> str:
        """提取薪资信息"""
        # Boss直聘详情页的薪资选择器
        selectors = [
            '.salary',
            '.job-primary .info-primary .salary',
            '.info-primary h1 + .salary',
            '.job-detail .salary',
            '[class*="salary"]',
            '.job-primary .name + .salary',
            'span.salary'
        ]
        
        for selector in selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and text.strip():
                        salary = text.strip()
                        # 清理薪资文本
                        salary = salary.replace('·', '-').replace('薪', '')
                        # 验证是否是有效的薪资格式
                        if any(k in salary for k in ['K', '万', '千']) and len(salary) > 2:
                            logger.debug(f"✅ 找到薪资信息: {selector} → {salary}")
                            return salary
            except Exception as e:
                logger.debug(f"提取薪资失败 {selector}: {e}")
                continue
        
        # 尝试从页面文本中查找薪资
        try:
            page_text = await self.page.content()
            import re
            # 匹配薪资模式: 15K-25K, 15-25K, 1.5万-2.5万等
            salary_pattern = r'\b(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)\s*([Kk千万])\b'
            match = re.search(salary_pattern, page_text)
            if match:
                salary = match.group(0)
                logger.debug(f"✅ 从页面文本中找到薪资: {salary}")
                return salary
        except:
            pass
        
        return ""
    
    async def _extract_benefits(self) -> str:
        """提取福利待遇"""
        selectors = [
            '.job-tags .tag',
            '.welfare-list .welfare-item',
            '.job-welfare .tag-item',
            '.benefits .benefit-item'
        ]
        
        benefits = []
        for selector in selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                for element in elements:
                    text = await element.inner_text()
                    if text and text.strip():
                        benefits.append(text.strip())
            except Exception as e:
                logger.debug(f"提取福利待遇失败 {selector}: {e}")
                continue
        
        if benefits:
            logger.debug(f"✅ 找到福利待遇: {len(benefits)} 项")
            return " | ".join(benefits[:10])  # 限制数量避免过长
        
        return "福利待遇信息未找到"
    
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
            if "Execution context was destroyed" in str(e):
                logger.debug("⚠️ 页面导航导致登录检查中断（正常现象）")
            else:
                logger.warning(f"⚠️ 处理登录/验证码时出错: {e}")
    
    async def get_performance_report(self) -> Dict:
        """获取爬虫性能报告"""
        return self.enhanced_extractor.get_performance_report()
    
    def get_system_status(self) -> Dict:
        """获取系统整体状态报告"""
        return {
            'crawler_status': {
                'browser_active': self.browser is not None,
                'page_active': self.page is not None,
                'current_url': self.page.url if self.page else None
            },
            'session_info': self.session_manager.get_session_info(),
            'retry_stats': self.retry_handler.get_retry_stats(),
            'extractor_performance': self.enhanced_extractor.get_performance_report(),
            'city_codes': self.city_codes,
            'enhancement_status': {
                'smart_selector_enabled': True,
                'enhanced_extractor_enabled': True,
                'session_manager_enabled': True,
                'retry_handler_enabled': True,
                'version': 'v2.0-enhanced'
            }
        }
    
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
            # 对于持久化上下文，只需要关闭上下文
            if self.context:
                await self.context.close()
            # 对于非持久化模式，需要关闭浏览器
            elif self.browser:
                if self.page:
                    await self.page.close()
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