#!/usr/bin/env python3
"""
大规模岗位抓取优化引擎
支持50-100+岗位高效抓取，包含智能分页、批量处理和性能优化
"""

import asyncio
import logging
import time
import math
from typing import List, Dict, Optional, Tuple
from playwright.async_api import Page, Browser
from .enhanced_extractor import EnhancedDataExtractor
from .session_manager import SessionManager
from .retry_handler import RetryHandler, retry_on_error

logger = logging.getLogger(__name__)


class LargeScaleCrawler:
    """大规模岗位抓取引擎"""
    
    def __init__(self, page: Page, session_manager: SessionManager, retry_handler: RetryHandler):
        self.page = page
        self.session_manager = session_manager
        self.retry_handler = retry_handler
        self.enhanced_extractor = EnhancedDataExtractor()
        
        # 大规模抓取配置
        self.batch_size = 20  # 每批处理的岗位数量
        self.max_scroll_attempts = 15  # 最大滚动尝试次数
        self.scroll_delay = 2.0  # 滚动延迟
        self.page_load_timeout = 30  # 页面加载超时
        
        # 性能监控
        self.performance_stats = {
            "total_jobs_found": 0,
            "successful_extractions": 0,
            "total_pages_processed": 0,
            "total_scroll_attempts": 0,
            "avg_page_processing_time": 0.0,
            "start_time": time.time()
        }
    
    async def extract_large_scale_jobs(self, max_jobs: int = 80) -> List[Dict]:
        """
        大规模岗位抓取主入口
        
        Args:
            max_jobs: 目标岗位数量（50-100+）
            
        Returns:
            提取的岗位数据列表
        """
        logger.info(f"🚀 启动大规模岗位抓取引擎，目标: {max_jobs} 个岗位")
        start_time = time.time()
        
        try:
            # 第一阶段：智能页面准备和内容发现
            await self._prepare_large_scale_extraction()
            
            # 第二阶段：智能滚动和内容加载
            total_jobs_loaded = await self._intelligent_scroll_and_load(max_jobs)
            
            # 第三阶段：批量数据提取
            all_jobs = await self._batch_extract_jobs(max_jobs)
            
            # 第四阶段：数据质量验证和去重
            validated_jobs = await self._validate_and_deduplicate(all_jobs)
            
            extraction_time = time.time() - start_time
            self._update_performance_stats(len(validated_jobs), extraction_time)
            
            logger.info(f"✅ 大规模抓取完成: {len(validated_jobs)} 个岗位，耗时 {extraction_time:.2f}s")
            logger.info(f"📊 抓取效率: {len(validated_jobs)/extraction_time:.1f} 岗位/秒")
            
            return validated_jobs[:max_jobs]  # 确保不超过目标数量
            
        except Exception as e:
            logger.error(f"❌ 大规模抓取失败: {e}")
            return []
    
    async def _prepare_large_scale_extraction(self) -> None:
        """大规模抓取页面准备"""
        logger.info("🔧 准备大规模抓取环境...")
        
        # 优化页面性能设置
        await self.page.evaluate("""
            () => {
                // 禁用不必要的动画以提升性能
                const style = document.createElement('style');
                style.textContent = `
                    *, *::before, *::after {
                        animation-duration: 0.01s !important;
                        animation-delay: 0.01s !important;
                        transition-duration: 0.01s !important;
                        transition-delay: 0.01s !important;
                    }
                `;
                document.head.appendChild(style);
                
                // 优化滚动性能
                document.documentElement.style.scrollBehavior = 'auto';
            }
        """)
        
        # 等待初始内容加载
        await asyncio.sleep(3)
        
        # 检查并处理可能的反爬虫机制
        await self._handle_anti_crawling_measures()
        
        logger.info("✅ 大规模抓取环境准备完成")
    
    async def _handle_anti_crawling_measures(self) -> None:
        """处理反爬虫措施"""
        try:
            # 检查验证码
            captcha_selectors = ['.captcha', '.verify-wrap', '[class*="captcha"]', '.geetest']
            for selector in captcha_selectors:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    logger.warning("🔒 检测到验证码，暂停等待处理...")
                    await asyncio.sleep(10)
                    break
            
            # 检查登录要求
            login_selectors = ['.login-dialog', '.dialog-wrap', '.modal[class*="login"]']
            for selector in login_selectors:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    logger.info("🔐 检测到登录要求，使用会话管理...")
                    if not await self.session_manager.check_login_status(self.page, "zhipin.com"):
                        logger.warning("⚠️ 需要登录才能继续大规模抓取")
                    break
                    
        except Exception as e:
            logger.debug(f"处理反爬虫措施时出错: {e}")
    
    async def _intelligent_scroll_and_load(self, target_jobs: int) -> int:
        """
        智能滚动和内容加载策略
        
        Returns:
            已加载的岗位数量
        """
        logger.info(f"📜 开始智能滚动加载，目标: {target_jobs} 个岗位")
        
        jobs_loaded = 0
        scroll_attempts = 0
        consecutive_no_new_content = 0
        
        while jobs_loaded < target_jobs and scroll_attempts < self.max_scroll_attempts:
            scroll_attempts += 1
            self.performance_stats["total_scroll_attempts"] += 1
            
            # 获取当前岗位数量
            current_jobs = await self._count_current_jobs()
            
            logger.info(f"   滚动 {scroll_attempts}/{self.max_scroll_attempts}: 当前发现 {current_jobs} 个岗位")
            
            # 检查是否有新内容加载
            if current_jobs > jobs_loaded:
                jobs_loaded = current_jobs
                consecutive_no_new_content = 0
            else:
                consecutive_no_new_content += 1
                
                # 如果连续多次没有新内容，尝试不同的滚动策略
                if consecutive_no_new_content >= 3:
                    logger.info("🔄 尝试替代滚动策略...")
                    await self._alternative_scroll_strategy()
                    consecutive_no_new_content = 0
            
            # 检查是否已经找到足够的岗位
            if jobs_loaded >= target_jobs:
                logger.info(f"✅ 已找到足够岗位: {jobs_loaded}")
                break
            
            # 继续滚动加载更多内容
            await self._smart_scroll_step()
            
            # 如果连续多次没有新内容，可能已经到底了
            if consecutive_no_new_content >= 5:
                logger.info("📄 可能已经到达页面底部，结束滚动")
                break
        
        logger.info(f"📜 滚动完成: 总共发现 {jobs_loaded} 个岗位")
        return jobs_loaded
    
    async def _count_current_jobs(self) -> int:
        """统计当前页面的岗位数量"""
        job_selectors = [
            'li[data-jobid]',
            '.job-card',
            '.job-item',
            '[class*="job-primary"]',
            '.job-list li',
            'li:has(.job-title)',
            'li:has(.job-name)'
        ]
        
        max_count = 0
        for selector in job_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                count = len(elements)
                if count > max_count:
                    max_count = count
            except:
                continue
        
        return max_count
    
    async def _smart_scroll_step(self) -> None:
        """智能滚动步骤"""
        try:
            # 获取当前页面高度
            current_height = await self.page.evaluate("document.body.scrollHeight")
            
            # 滚动到页面底部
            await self.page.evaluate("""
                () => {
                    window.scrollTo(0, document.body.scrollHeight);
                }
            """)
            
            # 等待内容加载
            await asyncio.sleep(self.scroll_delay)
            
            # 检查是否有新内容加载
            new_height = await self.page.evaluate("document.body.scrollHeight")
            
            # 如果页面高度增加，说明有新内容加载
            if new_height > current_height:
                logger.debug(f"   页面高度增加: {current_height} -> {new_height}")
                # 额外等待确保内容完全加载
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.debug(f"滚动步骤失败: {e}")
    
    async def _alternative_scroll_strategy(self) -> None:
        """替代滚动策略（当标准滚动无效时）"""
        try:
            # 策略1: 分段滚动
            viewport_height = await self.page.evaluate("window.innerHeight")
            for i in range(3):
                scroll_position = viewport_height * (i + 1)
                await self.page.evaluate(f"window.scrollTo(0, {scroll_position})")
                await asyncio.sleep(1)
            
            # 策略2: 尝试点击"加载更多"按钮
            load_more_selectors = [
                '.load-more',
                '.more-btn',
                '[class*="load-more"]',
                'button:has-text("更多")',
                'button:has-text("加载")'
            ]
            
            for selector in load_more_selectors:
                try:
                    button = await self.page.query_selector(selector)
                    if button and await button.is_visible():
                        logger.info(f"🔘 找到加载更多按钮: {selector}")
                        await button.click()
                        await asyncio.sleep(3)
                        return
                except:
                    continue
            
            # 策略3: 键盘滚动
            await self.page.keyboard.press('End')
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.debug(f"替代滚动策略失败: {e}")
    
    async def _batch_extract_jobs(self, max_jobs: int) -> List[Dict]:
        """批量提取岗位数据"""
        logger.info(f"🔄 开始批量提取岗位数据，目标: {max_jobs}")
        
        # 使用增强提取器获取所有岗位
        all_jobs = await self.enhanced_extractor.extract_job_listings_enhanced(
            self.page, max_jobs
        )
        
        logger.info(f"📊 批量提取完成: {len(all_jobs)} 个岗位")
        return all_jobs
    
    async def _validate_and_deduplicate(self, jobs: List[Dict]) -> List[Dict]:
        """数据质量验证和去重"""
        logger.info(f"🔍 开始数据验证和去重，原始数据: {len(jobs)} 个岗位")
        
        validated_jobs = []
        seen_urls = set()
        seen_titles_companies = set()
        
        for job in jobs:
            try:
                # 基本字段验证
                if not self._validate_job_data(job):
                    continue
                
                # URL去重
                job_url = job.get('url', '')
                if job_url and job_url in seen_urls:
                    continue
                seen_urls.add(job_url)
                
                # 标题+公司去重
                title = job.get('title', '').strip()
                company = job.get('company', '').strip()
                title_company_key = f"{title}_{company}"
                
                if title_company_key in seen_titles_companies:
                    continue
                seen_titles_companies.add(title_company_key)
                
                # 添加提取索引和时间戳
                job['extraction_index'] = len(validated_jobs)
                job['extraction_timestamp'] = time.time()
                job['engine_source'] = 'Large Scale Crawler'
                job['extraction_method'] = 'batch'
                
                validated_jobs.append(job)
                
            except Exception as e:
                logger.debug(f"验证岗位数据失败: {e}")
                continue
        
        logger.info(f"✅ 验证完成: {len(validated_jobs)} 个有效岗位")
        return validated_jobs
    
    def _validate_job_data(self, job: Dict) -> bool:
        """验证单个岗位数据的有效性"""
        required_fields = ['title', 'company']
        
        # 检查必需字段
        for field in required_fields:
            if not job.get(field) or not job[field].strip():
                return False
        
        # 检查数据质量
        title = job.get('title', '').strip()
        if len(title) < 2 or len(title) > 100:
            return False
        
        company = job.get('company', '').strip()
        if len(company) < 2 or len(company) > 100:
            return False
        
        return True
    
    def _update_performance_stats(self, successful_jobs: int, total_time: float) -> None:
        """更新性能统计"""
        self.performance_stats.update({
            "successful_extractions": successful_jobs,
            "total_processing_time": total_time,
            "extraction_rate": successful_jobs / total_time if total_time > 0 else 0,
            "efficiency_score": min(successful_jobs / 50, 1.0)  # 以50个岗位为基准计算效率
        })
    
    def get_performance_report(self) -> Dict:
        """获取性能报告"""
        return {
            "large_scale_crawler_stats": self.performance_stats,
            "configuration": {
                "batch_size": self.batch_size,
                "max_scroll_attempts": self.max_scroll_attempts,
                "scroll_delay": self.scroll_delay,
                "page_load_timeout": self.page_load_timeout
            },
            "status": "optimized_for_large_scale"
        }


class LargeScaleProgressTracker:
    """大规模抓取进度跟踪器"""
    
    def __init__(self, total_target: int):
        self.total_target = total_target
        self.current_progress = 0
        self.phase_progress = {}
        self.start_time = time.time()
    
    def update_phase(self, phase_name: str, progress: int, total: int):
        """更新阶段进度"""
        percentage = (progress / total) * 100 if total > 0 else 0
        self.phase_progress[phase_name] = {
            'current': progress,
            'total': total,
            'percentage': percentage
        }
        
        logger.info(f"📈 {phase_name}: {progress}/{total} ({percentage:.1f}%)")
    
    def get_overall_progress(self) -> Dict:
        """获取整体进度"""
        elapsed_time = time.time() - self.start_time
        
        return {
            "target_jobs": self.total_target,
            "current_jobs": self.current_progress,
            "overall_percentage": (self.current_progress / self.total_target) * 100,
            "elapsed_time": elapsed_time,
            "estimated_remaining": self._estimate_remaining_time(),
            "phase_details": self.phase_progress
        }
    
    def _estimate_remaining_time(self) -> float:
        """估算剩余时间"""
        elapsed = time.time() - self.start_time
        if self.current_progress > 0:
            rate = self.current_progress / elapsed
            remaining_jobs = self.total_target - self.current_progress
            return remaining_jobs / rate if rate > 0 else 0
        return 0