#!/usr/bin/env python3
"""
真正的Playwright自动化Boss直聘爬虫
实现可见的浏览器操作和真实数据提取
"""

import asyncio
import base64
import hashlib
import inspect
import logging
import re
import urllib.parse
import time
import os
from pathlib import Path
from typing import Any, Callable, List, Dict, Optional
# 使用 patchright（Playwright 反检测分支）：从驱动层避免 Runtime.enable 等 CDP 痕迹，
# 绕过 Boss 的 security.html?code=37 反爬挑战。API 与 playwright 完全兼容。
from patchright.async_api import async_playwright, Browser, Page, BrowserContext
from .enhanced_extractor import EnhancedDataExtractor
from .session_manager import SessionManager
from .retry_handler import RetryHandler, RetryConfig, ErrorType, RetryStrategy, retry_on_error
from .large_scale_crawler import LargeScaleCrawler, LargeScaleProgressTracker

logger = logging.getLogger(__name__)


class RealPlaywrightBossSpider:
    """真正的Playwright Boss直聘爬虫"""
    
    def __init__(
        self,
        headless: bool = False,
        profile_dir: Optional[str] = None,
        qr_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
        login_wait_seconds: Optional[float] = None,
        qr_poll_interval: Optional[float] = None,
    ):
        """
        参数：
            headless - 是否无头模式
            profile_dir - 覆盖 config 的 user_data_dir（per-user UUID profile 用）；
                          不传则用 config 的全局默认（向后兼容单用户场景）
            qr_callback - 登录二维码状态回调；不传时保持原本地浏览器轮询行为
            login_wait_seconds - 登录等待时限；主要用于部署调优和快速测试
            qr_poll_interval - 登录状态与二维码变化的轮询间隔
        """
        self.headless = headless
        self.profile_dir_override = profile_dir  # 由 profile_manager 注入
        self.qr_callback = qr_callback
        self.login_wait_seconds = (
            float(login_wait_seconds)
            if login_wait_seconds is not None
            else (180.0 if qr_callback is not None else 300.0)
        )
        self.qr_poll_interval = (
            float(qr_poll_interval)
            if qr_poll_interval is not None
            else (3.0 if qr_callback is not None else 5.0)
        )
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.enhanced_extractor = EnhancedDataExtractor()  # 集成增强提取器
        self.session_manager = SessionManager()  # 集成会话管理器
        self.retry_handler = RetryHandler()  # 集成重试处理器
        self.current_search_url: Optional[str] = None

        # 加载配置
        try:
            from config.config_manager import ConfigManager
            self.config_manager = ConfigManager()
            self.browser_config = self.config_manager.get_app_config('crawler', {}).get('browser', {})
        except:
            logger.warning("无法加载配置管理器，使用默认配置")
            self.config_manager = None
            self.browser_config = {}

        self.diagnostic_logging = bool(self.browser_config.get('diagnostic_logging', False))
        
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
        logger.info("🎭 启动Playwright浏览器...")
        
        self.playwright = await async_playwright().start()
        
        # 检查是否使用持久化上下文
        use_persistent = self.browser_config.get('use_persistent_context', True)
        # 优先用 __init__ 注入的 per-user profile_dir（profile_manager 提供），
        # 否则回落到 config 全局默认（向后兼容单用户场景）
        user_data_dir = self.profile_dir_override or self.browser_config.get(
            'user_data_dir',
            os.path.expanduser('~/Library/Application Support/boss_automation/browser_profile/boss_zhipin'),
        )
        
        if use_persistent:
            # 创建用户数据目录
            user_data_path = Path(os.path.expanduser(str(user_data_dir))).resolve()
            user_data_path.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"📁 使用持久化浏览器配置: {user_data_path}")
            
            # 检查是否是首次使用
            is_first_run = not (user_data_path / "Default").exists()
            if is_first_run:
                logger.info("🆕 检测到首次运行，将引导您进行登录...")
                logger.info("👤 请在打开的浏览器窗口中手动登录Boss直聘")
                logger.info("✅ 登录成功后，您的登录状态将被自动保存")
            
            # patchright 官方最佳实践：用真实 Chrome（channel="chrome"）+ 干净配置。
            # 关键：不要叠加自定义 args / user_agent / stealth——patchright 已内置反检测，
            # 额外"化妆"反而与真 Chrome 指纹冲突、制造破绽。no_viewport 让窗口用自然尺寸。
            logger.info(f"🚀 正在启动浏览器（patchright + 真实 Chrome），headless={self.headless}")
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_path),
                channel="chrome",
                headless=self.headless,
                no_viewport=True,
            )

            # 监听跳转（默认关闭，避免日志噪音）
            if self.diagnostic_logging:
                self.context.on('page', lambda p: logger.debug(f"[诊断] 新页面打开: {p.url}"))

            # 获取或创建页面
            pages = self.context.pages
            self.page = pages[0] if pages else await self.context.new_page()
            if self.diagnostic_logging:
                self.page.on('framenavigated', lambda f: logger.debug(f"[诊断] 页面跳转: {f.url}") if f == self.page.main_frame else None)
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

        # 获取城市代码
        city_code = self.city_codes.get(city, "101210100")  # 默认上海

        logger.info(f"🔍 开始搜索: {keyword} | 城市: {city} ({city_code}) | 数量: {max_jobs}")

        # 直接导航搜索页（绕过首页——首页会触发反爬 about:blank）
        # 未登录状态下也可获取前~15条结果；已登录可获取完整列表
        encoded_keyword = urllib.parse.quote(keyword)
        search_url = f"https://www.zhipin.com/web/geek/jobs?query={encoded_keyword}&city={city_code}"
        self.current_search_url = search_url
        logger.info(f"🔍 直接导航到搜索页: {search_url}")
        await self._navigate_to_search_page(search_url)

        # 强制登录门：未登录只能拿残血数据（薪资缺失/列表受限），先登录再抓
        await self._require_login(search_url)

        # 最小交互快照：尽快抓取一次，防止后续被反爬重定向导致整批丢失
        early_snapshot_jobs = await self.enhanced_extractor.extract_job_listings_quick_snapshot(self.page, max_jobs)
        if early_snapshot_jobs:
            logger.info(f"⚡ 搜索页早期快照拿到 {len(early_snapshot_jobs)} 个岗位")

        # 处理页面加载和预处理（传递目标岗位数量）
        await self._prepare_search_page(max_jobs, search_url)
        # 提取前再次确认当前活动页可用，避免标签页被切到 about:blank
        await self._ensure_search_page_ready(search_url, stage="提取前")

        # 首次按规模选择策略抓取
        jobs = await self._extract_jobs_by_strategy(max_jobs, early_snapshot_jobs)

        # 会话过期自愈：提取为空且被弹回登录页时触发。Boss 反爬的安全校验重定向
        # 常在提取阶段才完成（URL 此时才稳定为 /web/user/ 登录页），故在提取后
        # 检测最可靠；早于此（导航后/prepare 后）检测会因重定向未完成而漏判。
        if not jobs and await self._recover_session_if_needed(search_url):
            await self._prepare_search_page(max_jobs, search_url)
            await self._ensure_search_page_ready(search_url, stage="重登后提取前")
            early_snapshot_jobs = await self.enhanced_extractor.extract_job_listings_quick_snapshot(self.page, max_jobs)
            jobs = await self._extract_jobs_by_strategy(max_jobs, early_snapshot_jobs)

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

    async def _extract_jobs_by_strategy(self, max_jobs: int, early_snapshot_jobs: List[Dict]) -> List[Dict]:
        """按目标数量选择抓取策略并提取岗位

        参数：
            max_jobs           - 目标岗位数（<=30 走增强提取器，否则走大规模引擎）
            early_snapshot_jobs - 搜索页早期快照结果，作为增强提取失败时的兜底
        返回：
            List[Dict] - 提取到的岗位基础信息列表（可能为空）
        """
        if max_jobs <= 30:
            # 小规模抓取：使用增强提取器
            logger.info("🚀 启用增强数据提取引擎（小规模模式）...")
            jobs = await self.enhanced_extractor.extract_job_listings_enhanced(self.page, max_jobs)
            if not jobs:
                logger.warning("⚠️ 首次提取为空，尝试恢复页面后重试一次...")
                await self._ensure_search_page_ready(self.current_search_url, stage="提取重试前")
                jobs = await self.enhanced_extractor.extract_job_listings_enhanced(self.page, max_jobs)
            if not jobs and early_snapshot_jobs:
                logger.warning("⚠️ 增强提取仍为空，回退使用搜索页早期快照结果")
                jobs = early_snapshot_jobs
            return jobs

        # 大规模抓取：使用大规模爬虫引擎
        logger.info(f"🏭 启用大规模抓取引擎（目标: {max_jobs} 个岗位）...")
        large_scale_crawler = LargeScaleCrawler(self.page, self.session_manager, self.retry_handler)
        return await large_scale_crawler.extract_large_scale_jobs(max_jobs)

    @retry_on_error(max_attempts=3, base_delay=2.0)
    async def _navigate_to_search_page(self, search_url: str) -> None:
        """导航到搜索页面"""
        logger.info("🔗 正在导航到Boss直聘搜索页面...")
        logger.info("👀 请观察浏览器窗口，你应该能看到页面加载过程")

        await self.page.goto(search_url, wait_until="domcontentloaded", timeout=15000)

    async def _is_login_ui_present(self) -> bool:
        """DOM 判定是否未登录：登录浮层或页头登录按钮可见

        未登录访问搜索 URL 有两种形态：
        a) 被异步重定向到 /web/user/ 登录页（URL 可判，调用方处理）
        b) 停留在搜索页但只有残血数据，并弹出登录浮层（.login-dialog）
        本方法检测形态 b 的 DOM 信号。

        返回：bool - True 表示未登录（登录 UI 可见）
        """
        for selector in ('.login-dialog', '.dialog-wrap',
                         '.header-login-btn', 'a[ka="header-login"]',
                         '[class*="login-btn"]'):
            try:
                el = await self.page.query_selector(selector)
                if el and await el.is_visible():
                    return True
            except Exception:
                continue
        return False

    async def _is_logged_in_api(self):
        """问 Boss 自身接口判定登录态（最权威信号）

        实测：未登录时 /wapi/zpuser/wap/getUserInfo.json 返回
        {code: 7, message: "当前登录状态已失效"}；已登录返回 code 0。
        URL/DOM 判定都有假阴性（未登录也停留在搜索页、浮层出现时机不定），
        此接口来自 Boss 自己，无时机竞态。

        返回：True 已登录 / False 未登录 / None 探测失败（调用方走 DOM 兜底）
        """
        try:
            r = await self.page.evaluate("""async () => {
                try {
                    const resp = await fetch(
                        "/wapi/zpuser/wap/getUserInfo.json",
                        {credentials: "include"});
                    const j = await resp.json();
                    return {code: j.code};
                } catch (e) { return {error: 1}; }
            }""")
            if isinstance(r, dict) and "code" in r:
                logged = (r["code"] == 0)
                logger.info(f"🔍 登录状态（Boss API）: code={r['code']} → "
                            f"{'已登录' if logged else '未登录'}")
                return logged
        except Exception as e:
            logger.debug(f"登录态 API 探测失败，转 DOM 兜底: {e}")
        return None

    async def _require_login(self, search_url: str) -> None:
        """搜索前强制登录门：未登录先登录，保证抓到全量信息

        未登录状态 Boss 只给残血数据（薪资缺失、详情不全、列表限 ~15 条）。
        判定三层：settle 等 URL 落定（登录页 → 直接登录）→ Boss getUserInfo
        API（权威）→ 登录浮层 DOM（兜底）。未登录走 _ensure_logged_in
        （云端自动推 QR 到用户网页，本机可见浏览器人肉扫码），成功后回到
        目标搜索页。

        参数：search_url - 目标搜索页 URL
        异常：RuntimeError - 登录失败/超时（消息含"登录超时"，app 层据此
              把任务标记为 login_timeout）
        """
        settled = await self._wait_until_page_settled()

        needs_login = settled == 'login'
        if not needs_login:
            api_logged = await self._is_logged_in_api()
            if api_logged is False:
                needs_login = True
            elif api_logged is None:
                needs_login = await self._is_login_ui_present()

        if not needs_login:
            logger.info("🔓 已登录，直接抓取全量信息")
            return

        logger.info(f"🔑 未登录（落点={settled}），先行登录以抓取全量信息...")
        logged_in = await self._ensure_logged_in()
        if not logged_in:
            raise RuntimeError("登录超时：用户未在时限内扫码，无法抓取全量信息")

        # 登录成功后 Boss 可能落在任意页，确保回到目标搜索页
        if not self._url_matches_search_target(self.page.url or '', search_url):
            logger.info("🔗 登录成功，重新导航到目标搜索页")
            await self._navigate_to_search_page(search_url)
    
    async def _prepare_search_page(self, target_jobs: int = 20, search_url: Optional[str] = None) -> None:
        """准备搜索页面 - 快速模式，避免触发延迟反爬检测"""
        # 缩短等待窗口，减少被延迟反爬跳转about:blank的概率
        logger.info("⏳ 等待搜索页面初始内容渲染（1.5秒）...")
        await asyncio.sleep(1.5)

        # 检查是否被反爬重定向，并尝试自动恢复
        await self._ensure_search_page_ready(search_url, stage="初始渲染后")
        current_url = self.page.url

        title = await self.page.title()
        logger.info(f"✅ 搜索页面就绪，URL: {current_url}，标题: {title}")

        # 诊断截图：默认关闭，避免每次任务产生无效文件
        if self.diagnostic_logging:
            diag_screenshot = f"search_diag_{int(time.time())}.png"
            try:
                await self.page.screenshot(path=diag_screenshot)
                logger.debug(f"[诊断] 提取前截图: {diag_screenshot}")
            except Exception as e:
                logger.debug(f"诊断截图失败: {e}")

        # 处理弹窗
        await self._handle_login_or_captcha()
        # 弹窗处理后再校验一次，避免被动跳到about:blank后直接进入提取
        await self._ensure_search_page_ready(search_url, stage="弹窗处理后")

    async def _switch_to_live_context_page(self, prefer_search: bool = True) -> bool:
        """当当前页无效时，尝试切换到同一context中仍存活的页面"""
        if not self.context:
            return False

        try:
            candidates = []
            for candidate in reversed(self.context.pages):
                if candidate.is_closed():
                    continue
                url = (candidate.url or "").strip()
                if not url or "about:blank" in url or "zhipin.com" not in url:
                    continue

                score = 0
                if "zhipin.com/web/geek/jobs" in url:
                    score = 30 if prefer_search else 20
                elif "zhipin.com/job_detail" in url:
                    score = 20
                elif "zhipin.com" in url:
                    score = 10
                else:
                    score = 1
                candidates.append((score, candidate, url))

            if not candidates:
                return False

            candidates.sort(key=lambda item: item[0], reverse=True)
            _, best_page, best_url = candidates[0]
            if self.page != best_page:
                self.page = best_page
                await self.page.bring_to_front()
                logger.warning(f"⚠️ 已切换到可用标签页: {best_url}")
            return True
        except Exception as e:
            logger.debug(f"切换可用标签页失败: {e}")
            return False

    async def _ensure_search_page_ready(self, fallback_url: Optional[str], stage: str = "") -> None:
        """确保当前页不是 about:blank，必要时自动回跳搜索页"""
        if not self.page or self.page.is_closed():
            if not await self._switch_to_live_context_page(prefer_search=True):
                if not self.context:
                    raise RuntimeError(f"{stage} 浏览器上下文不可用，无法恢复页面")
                self.page = await self.context.new_page()

        current_url = self.page.url if self.page else ""
        if current_url and 'about:blank' not in current_url and 'zhipin.com' in current_url:
            return

        if await self._switch_to_live_context_page(prefer_search=True):
            current_url = self.page.url if self.page else ""
            if current_url and 'about:blank' not in current_url and 'zhipin.com' in current_url:
                return

        target_url = fallback_url or self.current_search_url
        if not target_url:
            raise RuntimeError(f"{stage} 页面是about:blank，且没有可用回跳URL")

        logger.warning(f"⚠️ {stage} 页面变为about:blank，尝试恢复到搜索页...")
        for attempt in range(2):
            candidate = self.page
            if self.context:
                try:
                    candidate = await self.context.new_page()
                    await candidate.bring_to_front()
                except Exception:
                    candidate = self.page
            await candidate.goto(target_url, wait_until="domcontentloaded", timeout=20000)
            self.page = candidate
            await asyncio.sleep(1.5)
            current_url = self.page.url
            if current_url and 'about:blank' not in current_url and 'zhipin.com' in current_url:
                logger.info(f"✅ 已恢复搜索页: {current_url}")
                return
            if await self._switch_to_live_context_page(prefer_search=True):
                current_url = self.page.url if self.page else ""
                if current_url and 'about:blank' not in current_url and 'zhipin.com' in current_url:
                    logger.info(f"✅ 已从其他标签页恢复搜索页: {current_url}")
                    return
            logger.warning(f"⚠️ 第 {attempt + 1} 次恢复后仍为about:blank")

        raise RuntimeError(f"{stage} 页面被重定向到about:blank（URL: {self.page.url}）")
    
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
    
    async def _is_logged_in_by_url(self) -> bool:
        """通过URL判断登录状态（最可靠的方式）

        已登录用户访问 zhipin.com 会被重定向到 /web/geek/ 路径
        未登录用户会被重定向到城市首页（如 /shanghai/）

        注意：登录成功后 URL 常为 /web/geek/jobs?...&_security_check=N——_security_check
        只是 Boss 路由残留的查询参数，不代表校验未完成（Boss 不会自行清除它），
        故只要出现 /web/geek/ 即视为已登录。
        """
        current_url = self.page.url or ""
        logged_in = '/web/geek/' in current_url
        logger.info(f"🔍 登录状态检查（URL）: {current_url} → {'已登录' if logged_in else '未登录'}")
        return logged_in

    async def _classify_page_state(self) -> str:
        """按当前 URL 判定页面处于哪种状态（settle 轮询的基础）

        Boss 反爬重定向异步进行，页面会在数秒内经历多种中间态，故按"状态"
        而非"瞬时 URL 标记"判断更可靠。

        参数：无（读取 self.page.url）
        返回：str —
            'login'    登录注册页（/web/user/），需引导登录
            'security' 安全校验中间页（security.html），仍在跳转
            'blank'    about:blank 或空 URL，仍在跳转
            'results'  搜索结果页（/web/geek/jobs，即便残留 _security_check），可提取
            'other'    其它（按非确定态处理）
        """
        url = (self.page.url or "").lower()
        if not url or 'about:blank' in url:
            return 'blank'
        if 'security.html' in url:
            return 'security'
        if '/web/user/' in url:
            return 'login'
        if '/web/geek/jobs' in url:
            return 'results'
        return 'other'

    async def _wait_until_page_settled(self, timeout: float = 15.0, interval: float = 1.0) -> str:
        """轮询等待页面从反爬中间态稳定到确定态

        把 security/blank/other 视为"仍在跳转，继续等"，直到稳定到 login 或
        results。解决"单点瞬时检测移动靶"的竞态——以页面最终落点而非某一刻状态为准。

        参数：
            timeout  - 最长等待秒数
            interval - 轮询间隔秒数
        返回：
            str - 'login'（需登录）/ 'results'（可提取）/ 'timeout'（未稳定）
        """
        deadline = time.time() + timeout
        last_state = None
        while time.time() < deadline:
            state = await self._classify_page_state()
            if state != last_state:
                logger.info(f"⏳ 页面状态: {state}（URL={getattr(self.page, 'url', None)}）")
                last_state = state
            if state in ('login', 'results'):
                return state
            await asyncio.sleep(interval)
        logger.warning(f"⚠️ {timeout}s 内页面未稳定到确定态，最后状态={last_state}")
        return 'timeout'

    async def _recover_session_if_needed(self, search_url: str) -> bool:
        """提取为空后的自愈：等页面稳定，按落点决定登录或直接重抓

        修复缺陷：会话失效时爬虫原本默默抓 0 条后失败；且 Boss 反爬重定向异步
        耗时数秒，单点检测会漏判。现改为先 settle 轮询，再按稳定结果处理。

        参数：
            search_url - 目标搜索页 URL（登录后若不在结果页则导航到此）
        返回：
            bool - True 表示调用方应重新准备页面并重新抓取（登录后，或页面刚稳定
                   到结果页、首次提取过早）；False 仅当 settle 超时、无可恢复
        异常：
            RuntimeError - 引导登录失败或超时
        """
        settled = await self._wait_until_page_settled()

        if settled == 'results':
            # 页面稳定到结果页，但需校验 query 与目标 search_url 匹配；否则可能是
            # 上次搜索的旧关键词残留（Boss 反爬常把 fromUrl 落到错关键词页），
            # 直接重抓会拿到错的结果。
            if self._url_matches_search_target(self.page.url or '', search_url):
                logger.info("✅ 已稳定到目标搜索结果页（首次提取过早），将重新抓取")
                return True
            logger.warning(
                f"⚠️ 稳定到结果页但 query 不匹配目标，重新导航: {self.page.url} → {search_url}"
            )
            await self._navigate_to_search_page(search_url)
            return True

        if settled != 'login':
            logger.warning("⚠️ 页面未稳定到登录页或结果页，放弃本次会话恢复")
            return False

        logger.warning("🔑 会话已过期，需要重新登录后才能抓取")
        logged_in = await self._ensure_logged_in()
        if not logged_in:
            raise RuntimeError("会话已过期且重新登录失败/超时，请重试")

        # 登录成功后，Boss 通常已按 fromUrl 把页面跳回搜索结果页（/web/geek/jobs，
        # URL 可能残留 _security_check 参数）。此时若再 goto 一个干净 search_url 会
        # 再次触发反爬安全校验、把页面弹回登录页（实测非确定性）。
        # 但仅判 path 不够：实测见过 Boss 落到 /web/geek/jobs 但 query=<别的关键词>，
        # 那不是用户想要的结果。故还需校验 query 参数匹配目标 search_url。
        if self._url_matches_search_target(self.page.url or '', search_url):
            logger.info(f"✅ 重新登录成功，已在目标搜索页，无需重新导航: {self.page.url}")
        else:
            logger.info(f"✅ 重新登录成功，落点非目标搜索页，重新导航: {self.page.url} → {search_url}")
            await self._navigate_to_search_page(search_url)
        return True

    @staticmethod
    def _url_matches_search_target(current_url: str, search_url: str) -> bool:
        """判断 current_url 是否已是 search_url 指向的目标搜索结果页

        相等标准（按 Codex review 反馈精确化，避免 substring 误判）：
          - host 一致（避免跨域代理/钓鱼页通过）
          - path（去尾斜杠）严格等于 /web/geek/jobs（而非 substring，
            否则 /web/geek/jobs-old / /foo/web/geek/jobs 会被误判）
          - query 的 `query` 与 `city` 参数都匹配
        其它参数（_security_check 等反爬残留）忽略。

        参数：
            current_url - 当前页面 URL（可能含 _security_check 残留）
            search_url  - 目标搜索 URL（构造时只含 query 与 city）
        返回：bool - 已在目标页则 True
        """
        if not current_url or not search_url:
            return False
        try:
            cur = urllib.parse.urlparse(current_url)
            tgt = urllib.parse.urlparse(search_url)
        except Exception:
            return False
        # host 必须一致（双方为空时也视为不匹配，避免相对 URL 漏判）
        if (cur.netloc or '').lower() != (tgt.netloc or '').lower():
            return False
        if not cur.netloc:
            return False
        # path 严格相等（去尾斜杠归一化）
        cur_path = (cur.path or '').rstrip('/')
        tgt_path = (tgt.path or '').rstrip('/')
        if cur_path != '/web/geek/jobs' or tgt_path != '/web/geek/jobs':
            return False
        cur_qs = urllib.parse.parse_qs(cur.query)
        tgt_qs = urllib.parse.parse_qs(tgt.query)
        for key in ('query', 'city'):
            if tgt_qs.get(key) and cur_qs.get(key) != tgt_qs.get(key):
                return False
        return True

    async def _emit_qr_event(
        self, state: str, message: str, image_b64: Optional[str] = None
    ) -> None:
        """向上游发送结构稳定的 QR 事件；回调故障不能打断登录轮询。"""
        if self.qr_callback is None:
            return
        event = {"state": state, "image_b64": image_b64, "message": message}
        try:
            result = self.qr_callback(event)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            logger.warning("QR 状态回调失败 type=%s", type(exc).__name__)

    async def _refresh_expired_qr(self) -> None:
        """Boss 二维码 ~2 分钟失效后页面出现"刷新"按钮，自动点掉换新码

        best-effort：选择器命中就点（Boss 改版最多退化为用户手动重发搜索），
        点击后短暂等待新码渲染。
        """
        for selector in ('.qr-code-box .refresh', '.qr-img-box .refresh',
                         '.btn-refresh', '[class*="refresh"]'):
            try:
                el = await self.page.query_selector(selector)
                if el is not None and await el.is_visible():
                    await el.click()
                    await asyncio.sleep(1.5)
                    logger.info("🔄 二维码已失效，已自动点击刷新")
                    return
            except Exception:
                continue

    async def _switch_to_qr_login(self) -> None:
        """把登录页从默认的手机验证码视图切到 APP 扫码视图

        实测（2026-07）：Boss 登录页默认显示短信验证码表单，二维码在点击
        右上角 `.switch-tip`（文本 "APP扫码登录"）后才渲染（.qr-img-box）。
        不切换的话截到的是验证码表单而非二维码。幂等：已在扫码视图
        （.qr-img-box 可见）则不动。
        """
        try:
            qr_box = await self.page.query_selector(".qr-img-box")
            if qr_box is not None and await qr_box.is_visible():
                return  # 已在扫码视图
            tip = await self.page.query_selector(".switch-tip")
            if tip is not None and await tip.is_visible():
                await tip.click()
                await asyncio.sleep(2)
                logger.info("🔁 登录页已切换到 APP 扫码视图")
        except Exception as exc:
            logger.warning("切换扫码视图失败 type=%s（继续尝试截图）",
                           type(exc).__name__)

    async def _capture_qr_image(self) -> Optional[bytes]:
        """优先截取二维码元素；元素定位失败时降级为当前登录页截图。"""
        await self._switch_to_qr_login()
        selectors = (
            ".qr-img-box",
            ".qr-img-box img",
            ".qr-code img",
            ".login-qrcode img",
            "img[class*='qr']",
            "canvas[class*='qr']",
        )
        for selector in selectors:
            try:
                element = await self.page.query_selector(selector)
                if element is not None and await element.is_visible():
                    image = await element.screenshot(type="png")
                    if image:
                        return image
            except Exception:
                continue
        try:
            return await self.page.screenshot(type="png")
        except Exception as exc:
            logger.warning("二维码截图失败 type=%s", type(exc).__name__)
            return None

    async def _qr_scanned(self) -> bool:
        """检测 Boss 登录页的“已扫码/待手机确认”覆盖层。"""
        selectors = (
            ".scan-success",
            ".qrcode-confirm",
            "[class*='scan']",
            "text=已扫描",
        )
        for selector in selectors:
            try:
                element = await self.page.query_selector(selector)
                if element is not None and await element.is_visible():
                    return True
            except Exception:
                continue
        return False

    async def _ensure_logged_in(self) -> bool:
        """引导用户完成登录（直接跳登录页，不导航首页以避免反爬）"""
        try:
            logger.info("🔐 跳转到登录页，请完成登录...")
            # 注意：不导航首页！首页会触发 Boss 直聘反爬，重定向到 about:blank
            try:
                await self.page.goto(
                    "https://www.zhipin.com/web/user/?ka=header-login",
                    wait_until="domcontentloaded", timeout=30000
                )
            except Exception as e:
                logger.warning(f"登录页加载异常: {e}")
            await asyncio.sleep(min(2.0, max(self.qr_poll_interval, 0.01)))

            # [诊断] 监听登录阶段每一次页面跳转/刷新，定位"登录页不停刷新"的根因
            nav_count = {'n': 0}

            def _on_login_nav(frame):
                try:
                    if self.page and frame == self.page.main_frame:
                        nav_count['n'] += 1
                        logger.info(f"[诊断] 🔄 登录阶段第 {nav_count['n']} 次页面跳转/刷新 → {frame.url}")
                except Exception:
                    pass

            try:
                self.page.on('framenavigated', _on_login_nav)
            except Exception:
                pass
            tab_n = len(self.context.pages) if self.context else '?'
            logger.info(f"[诊断] 登录开始：标签页数量={tab_n}，当前URL={self.page.url}")

            logger.info("🔐 请在浏览器中完成登录（扫码或手机号）")
            logger.info("💡 登录成功后，程序会自动检测并继续")

            max_wait_time = self.login_wait_seconds
            check_interval = max(self.qr_poll_interval, 0.01)

            # 部署模式：把二维码图像和状态向上游推送。截图内容做指纹去重，
            # Boss 自动刷新二维码时，图像变化会自然触发下一次 qr_ready。
            last_qr_hash = None
            scanned_emitted = False
            polls_since_push = 0
            if self.qr_callback is not None:
                image = await self._capture_qr_image()
                if not image:
                    await self._emit_qr_event(
                        "qr_capture_failed", "无法获取登录二维码，请稍后重试"
                    )
                    return False
                last_qr_hash = hashlib.sha256(image).hexdigest()
                await self._emit_qr_event(
                    "qr_ready", "请使用 Boss 直聘 App 扫码登录",
                    base64.b64encode(image).decode("ascii"),
                )

            deadline = time.monotonic() + max_wait_time
            while time.monotonic() < deadline:
                # 登录成功判定双通道：URL（/web/geek/）或 Boss API（code 0）。
                # 实测扫码确认后 Boss 常跳到首页 www.zhipin.com/（非 /web/geek/），
                # 只看 URL 会漏判、死等到超时；API 判定在任意 zhipin 页面都有效。
                logged = await self._is_logged_in_by_url()
                if not logged:
                    logged = (await self._is_logged_in_api()) is True
                if logged:
                    logger.info("✅ 检测到登录成功！")
                    if self.qr_callback is not None:
                        await self._emit_qr_event("logged_in", "登录成功，开始搜索岗位")
                    else:
                        await asyncio.sleep(min(2.0, check_interval))
                    return True

                if self.qr_callback is not None:
                    if not scanned_emitted and await self._qr_scanned():
                        scanned_emitted = True
                        await self._emit_qr_event("scanned", "二维码已扫描，请在手机上确认")

                    await self._refresh_expired_qr()
                    image = await self._capture_qr_image()
                    if image:
                        image_hash = hashlib.sha256(image).hexdigest()
                        # 指纹变化 → 新码立即推；未变化也每 5 轮强制重推一次，
                        # 让刷新页面后重新连上的前端能拿到当前二维码。
                        polls_since_push += 1
                        if image_hash != last_qr_hash or polls_since_push >= 5:
                            if image_hash != last_qr_hash:
                                scanned_emitted = False
                            last_qr_hash = image_hash
                            polls_since_push = 0
                            await self._emit_qr_event(
                                "qr_ready", "请用 Boss 直聘 App 扫码",
                                base64.b64encode(image).decode("ascii"),
                            )

                remaining_time = max(0, int(deadline - time.monotonic()))
                tab_n = len(self.context.pages) if self.context else '?'
                logger.info(
                    f"⏳ 等待登录中... (剩余 {remaining_time} 秒，标签页={tab_n}，"
                    f"本阶段跳转 {nav_count['n']} 次)"
                )
                await asyncio.sleep(min(check_interval, max(0, deadline - time.monotonic())))

            logger.error("❌ 登录超时，请重试")
            if self.qr_callback is not None:
                await self._emit_qr_event("login_timeout", "扫码登录超时，请重新发起搜索")
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
    
    @staticmethod
    def _job_id_from_url(job_url: str) -> str:
        """从岗位 URL 提取岗位 id（用于定位列表卡片）

        参数：job_url - 形如 .../job_detail/<id>.html[?query]（绝对或相对）
        返回：str - 岗位 id；无法解析时返回空串
        """
        if not job_url or '/job_detail/' not in job_url:
            return ""
        return job_url.split('/job_detail/')[-1].split('.html')[0].split('?')[0]

    @staticmethod
    def _company_from_boss_attr(boss_attr: str) -> str:
        """从面板 '公司 · 角色' 文本提取公司名

        参数：boss_attr - 如 "大神网络科技 · 人事"
        返回：str - 公司名（'·' 前段，去空白）；空输入返回空串
        """
        if not boss_attr:
            return ""
        return boss_attr.split('·')[0].strip()

    # 薪资格式校验：必须含 数字 + (K|k|万|薪|元) 之一。
    # 用于过滤面板里"薪资范围说明 / tip / wrapper"类非真实薪资文本，
    # 否则会覆盖列表卡片真实值（Codex review 指出 [class*="salary"] 太宽）。
    _SALARY_VALID_RE = re.compile(r'\d.*[Kk万薪元]', re.IGNORECASE)

    async def _extract_panel_salary(self) -> str:
        """从详情面板按候选选择器抓取薪资文本并做格式校验

        Codex review 反馈：
          - 原 `[class*="salary"]` 选择器太宽，可能命中 tip/wrapper/说明节点
          - 命中后即覆盖列表卡片真实薪资，比"保留兜底"更坏
        改进：只保留两个具体选择器，外加正则校验"含数字+(K|万|薪|元)"
        才视为真实薪资；否则视同未命中，返回空串让调用方保留列表卡片原值。

        返回：str - 通过校验的薪资文本（如 "30-50K·14薪"）；否则空串
        """
        for selector in (
            '.job-detail-box .salary',
            '.job-detail-box .job-banner .salary',
        ):
            text = await self._panel_text(selector)
            if text and self._SALARY_VALID_RE.search(text):
                return text
        return ""

    async def _panel_text(self, selector: str) -> str:
        """读取详情面板某元素的可见文本

        inner_text 只取可见文本，自动排除 Boss 反爬注入的隐藏水印 span（直聘/kanzhun），
        因此得到干净 JD。元素不存在或异常时返回空串。
        参数：selector - CSS 选择器
        返回：str - 去空白后的可见文本；无则空串
        """
        try:
            loc = self.page.locator(selector)
            if await loc.count() == 0:
                return ""
            return (await loc.first.inner_text(timeout=3000)).strip()
        except Exception:
            return ""

    async def _extract_job_detail_page(self, job_url: str) -> Dict:
        """点击列表卡片，从右侧详情面板 .job-detail-box 提取岗位详情

        Boss /web/geek/jobs 是 SPA：点击 a.job-name 卡片会就地在右侧面板加载 JD，
        不导航到 /job_detail/（直接 goto 详情页会被反爬静默弹回）。故全程停留列表页、
        逐个点击卡片读面板。inner_text 自动排除隐藏水印，得到干净 JD。
        """
        job_id = self._job_id_from_url(job_url)
        try:
            # 点击卡片，让 SPA 在右侧面板加载该岗位详情
            card = self.page.locator(f'a.job-name[href*="{job_id}"]').first
            await card.click(timeout=8000)
            # 等面板 JD 文本块出现
            await self.page.wait_for_selector('.job-detail-box .desc', timeout=8000)
            await asyncio.sleep(0.6)

            jd = await self._panel_text('.job-detail-box .desc')
            boss_attr = await self._panel_text('.job-detail-box .boss-info-attr')
            company = self._company_from_boss_attr(boss_attr)
            address = await self._panel_text('.job-detail-box .job-address-desc')
            salary = await self._extract_panel_salary()

            jd_found = bool(jd) and '未找到' not in jd
            logger.info(f"📄 详情提取 job_id={job_id} jd_found={jd_found} JD长度={len(jd)} 公司={company or '?'} 薪资={salary or '?'}")

            result = {
                # Boss 面板的职位描述与任职要求合并在同一段，统一作为 JD 文本供 AI 评分
                'job_description': jd or '职位描述未找到',
                'job_requirements': jd or '任职要求未找到',
                'detail_extraction_success': jd_found,
            }
            if company:
                result['company'] = company           # 修正列表误取的公司名
                result['company_details'] = boss_attr
            if address:
                result['work_location'] = address
            if salary:
                # 列表卡片在反爬/未登录态常拿不到薪资被兜底为 '薪资面议'；
                # 面板抓到真实薪资时覆盖（{**job, **details} 合并行为）。
                # 仅当面板有非空值才写字段，否则保留列表卡片原值。
                result['salary'] = salary
            return result

        except Exception as e:
            logger.warning(f"❌ 详情提取失败 job_id={job_id}: {e}")
            return {
                'job_description': '详情提取失败，请直接访问岗位链接查看',
                'job_requirements': '详情提取失败，请直接访问岗位链接查看',
                'detail_extraction_success': False
            }

    async def _handle_login_or_captcha(self):
        """处理登录或验证码"""
        try:
            if not self.page:
                return

            if 'about:blank' in self.page.url:
                logger.warning("⚠️ 当前页已是about:blank，跳过弹窗处理")
                return

            # 检查是否有登录弹窗
            login_modal = await self.page.query_selector('.login-dialog, .dialog-wrap')
            if login_modal and await login_modal.is_visible():
                # 不主动点击登录弹窗，避免触发反爬脚本把页面打到about:blank
                logger.warning("⚠️ 检测到登录弹窗，保持页面不做点击操作")
                await asyncio.sleep(0.3)
            
            # 检查验证码
            captcha = await self.page.query_selector('.captcha, .verify-wrap')
            if captcha and await captcha.is_visible():
                logger.warning("🔒 检测到验证码，继续执行但结果可能为空")
                
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
