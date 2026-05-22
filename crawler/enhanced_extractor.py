#!/usr/bin/env python3
"""
增强数据提取引擎
整合智能选择器系统，提供高质量的数据提取和验证
"""

import logging
import asyncio
import time
import re
from typing import List, Dict, Optional, Tuple
from playwright.async_api import Page, ElementHandle
from .smart_selector import SmartSelector, ExtractedField

logger = logging.getLogger(__name__)


class EnhancedDataExtractor:
    """增强数据提取引擎"""
    
    def __init__(self):
        self.smart_selector = SmartSelector()
        self.extraction_cache = {}  # 缓存提取结果
        self.performance_stats = {
            "total_extractions": 0,
            "successful_extractions": 0,
            "avg_extraction_time": 0.0,
            "field_success_rates": {}
        }
        
    async def extract_job_listings_enhanced(self, page: Page, max_jobs: int = 20) -> List[Dict]:
        """
        使用增强算法提取岗位列表
        
        Args:
            page: Playwright页面对象
            max_jobs: 最大提取岗位数量
            
        Returns:
            提取的岗位数据列表
        """
        start_time = time.time()
        
        try:
            logger.info("🚀 启动增强数据提取引擎...")
            page = await self._adopt_live_page(page, stage="提取开始前")
            early_snapshot_jobs = await self._extract_jobs_fast_snapshot(page, max_jobs)
            if early_snapshot_jobs:
                logger.info(f"⚡ 早期快照提取到 {len(early_snapshot_jobs)} 个岗位")
            
            # 第一步：页面预处理和智能等待
            try:
                page = await self._prepare_page_for_extraction(page)
            except Exception:
                # 预处理失败但已有真实快照数据时，直接返回快照结果，避免整批丢失
                if early_snapshot_jobs:
                    logger.warning("⚠️ 页面预处理失败，直接使用早期快照结果")
                    validated = await self._validate_and_enhance_jobs(early_snapshot_jobs, page)
                    extraction_time = time.time() - start_time
                    self._update_performance_stats(len(validated), extraction_time)
                    return validated
                raise
            
            # 第二步：动态发现最佳岗位容器选择器
            logger.info("🔍 分析页面结构，寻找最佳选择器...")
            best_container_selectors = await self.smart_selector.find_best_selectors(
                page, "job_container", sample_size=3
            )
            
            if not best_container_selectors:
                logger.warning("⚠️ 智能选择器未找到有效选择器，尝试降级策略...")
                # 降级策略：使用最基础的元素选择
                fallback_result = await self._fallback_extraction(page, max_jobs)
                if fallback_result:
                    return fallback_result
                if early_snapshot_jobs:
                    logger.warning("⚠️ 智能选择器与降级策略均失败，回退到早期快照结果")
                    validated = await self._validate_and_enhance_jobs(early_snapshot_jobs, page)
                    extraction_time = time.time() - start_time
                    self._update_performance_stats(len(validated), extraction_time)
                    return validated
                logger.error("❌ 所有提取策略都失败了")
                return []
            
            # 第三步：提取岗位容器元素
            page = await self._adopt_live_page(page, stage="提取岗位容器前")
            job_elements = await self._get_job_elements(page, best_container_selectors)
            logger.info(f"📋 找到 {len(job_elements)} 个岗位容器")
            
            if not job_elements:
                await self._debug_page_content(page)
                return []
            
            # 第四步：先做一次快速DOM快照提取（抗about:blank中断）
            snapshot_jobs = await self._extract_jobs_fast_snapshot(page, max_jobs)
            if snapshot_jobs:
                logger.info(f"⚡ 快速快照提取到 {len(snapshot_jobs)} 个岗位")
            elif early_snapshot_jobs:
                snapshot_jobs = early_snapshot_jobs

            # 第五步：预先发现各字段的最佳选择器
            field_selectors = await self._discover_field_selectors(page, job_elements[:3])
            
            # 第六步：批量提取岗位数据
            jobs = await self._extract_jobs_batch(job_elements[:max_jobs], field_selectors)

            # 提取不足时，用快照结果补齐（常见于中途被跳转到about:blank）
            if len(jobs) < max_jobs and snapshot_jobs:
                logger.warning(f"⚠️ 增强提取仅得到 {len(jobs)} 个岗位，使用快照结果补齐到目标 {max_jobs}")
                jobs = self._merge_jobs(jobs, snapshot_jobs, max_jobs)

            # 仍不足时，尝试降级提取再补齐
            if len(jobs) < max_jobs:
                page = await self._adopt_live_page(page, stage="降级提取前")
                fallback_jobs = await self._fallback_extraction(page, max_jobs)
                if fallback_jobs:
                    jobs = self._merge_jobs(jobs, fallback_jobs, max_jobs)
                elif early_snapshot_jobs:
                    jobs = self._merge_jobs(jobs, early_snapshot_jobs, max_jobs)
            
            # 第七步：数据质量验证和增强
            validated_jobs = await self._validate_and_enhance_jobs(jobs, page)
            
            extraction_time = time.time() - start_time
            self._update_performance_stats(len(validated_jobs), extraction_time)
            
            logger.info(f"✅ 增强提取完成: {len(validated_jobs)}/{len(job_elements)} 个岗位，耗时 {extraction_time:.2f}s")
            return validated_jobs
            
        except Exception as e:
            logger.error(f"❌ 增强数据提取失败: {e}")
            return []

    async def extract_job_listings_quick_snapshot(self, page: Page, max_jobs: int = 20) -> List[Dict]:
        """仅做一次快速DOM快照提取（最小交互，抗about:blank）"""
        try:
            page = await self._adopt_live_page(page, stage="快速快照")
            return await self._extract_jobs_fast_snapshot(page, max_jobs)
        except Exception as e:
            logger.debug(f"快速快照提取失败: {e}")
            return []
    
    async def _adopt_live_page(self, page: Page, stage: str = "") -> Page:
        """当前页失效时，优先切到context中仍可用的zhipin页"""
        try:
            if page and not page.is_closed():
                current_url = (page.url or "").strip()
                if current_url and "about:blank" not in current_url and "zhipin.com" in current_url:
                    return page

            context = page.context if page else None
            if not context:
                return page

            candidates: List[Tuple[int, Page, str]] = []
            for candidate in reversed(context.pages):
                if candidate.is_closed():
                    continue
                url = (candidate.url or "").strip()
                if not url or "about:blank" in url or "zhipin.com" not in url:
                    continue
                score = 0
                if "zhipin.com/web/geek/jobs" in url:
                    score = 30
                elif "zhipin.com/job_detail" in url:
                    score = 20
                elif "zhipin.com" in url:
                    score = 10
                else:
                    score = 1
                candidates.append((score, candidate, url))

            if not candidates:
                return page

            candidates.sort(key=lambda item: item[0], reverse=True)
            _, best_page, best_url = candidates[0]
            if page != best_page:
                await best_page.bring_to_front()
                logger.warning(f"⚠️ {stage} 检测到当前页不可用，已切换标签页: {best_url}")
            return best_page
        except Exception as e:
            logger.debug(f"切换可用标签页失败: {e}")
            return page

    async def _prepare_page_for_extraction(self, page: Page) -> Page:
        """页面预处理 - 快速模式，避免长时间等待触发反爬"""
        try:
            page = await self._adopt_live_page(page, stage="预处理前")
            stable_url = page.url

            # 检查是否被反爬重定向到about:blank
            if 'about:blank' in page.url:
                raise RuntimeError(f"页面是about:blank，无法提取（URL: {page.url}）")

            # 等待DOM加载（不等networkidle，避免给反爬留时间）
            await page.wait_for_load_state("domcontentloaded")

            # Boss直聘特有：等待骨架屏消失，真实内容加载
            await self._wait_for_content_load(page)

            # 获取页面高度
            initial_height = await page.evaluate("""
                () => {
                    if (!document.body) return window.innerHeight || 800;
                    return Math.max(
                        document.body.scrollHeight || 0,
                        document.documentElement.scrollHeight || 0,
                        window.innerHeight || 0
                    );
                }
            """)
            logger.info(f"页面初始高度: {initial_height}")

            # 高度 <= 800px 说明页面无内容（viewport大小），跳过滚动
            if initial_height <= 850:
                await asyncio.sleep(0.8)
                second_height = await page.evaluate("""
                    () => {
                        if (!document.body) return window.innerHeight || 800;
                        return Math.max(
                            document.body.scrollHeight || 0,
                            document.documentElement.scrollHeight || 0,
                            window.innerHeight || 0
                        );
                    }
                """)
                if second_height > initial_height:
                    initial_height = second_height
                    logger.info(f"页面高度二次检测: {initial_height}")
                if initial_height <= 850:
                    logger.warning(f"⚠️ 页面高度仅{initial_height}px，可能无内容，跳过JS滚动")
                page = await self._recover_if_blank(page, stable_url, stage="低高度预处理后")
                return page

            # 保守模式：禁用主动滚动，避免触发Boss反爬跳转about:blank
            # 首屏通常已经有足够岗位用于提取，滚动交给后续策略按需触发
            await asyncio.sleep(0.5)

            await self._handle_page_overlays(page)
            page = await self._recover_if_blank(page, stable_url, stage="预处理后")
            return page

        except Exception as e:
            logger.warning(f"页面预处理失败: {e}")
            raise

    async def _recover_if_blank(self, page: Page, fallback_url: str, stage: str = "") -> Page:
        """页面被重定向到about:blank时，自动恢复到搜索页"""
        page = await self._adopt_live_page(page, stage=stage)
        if 'about:blank' not in page.url:
            return page

        if not fallback_url or 'about:blank' in fallback_url:
            raise RuntimeError(f"{stage} 页面是about:blank，且无有效恢复URL")

        logger.warning(f"⚠️ {stage} 页面跳转到about:blank，尝试恢复...")
        for attempt in range(2):
            context = page.context if page else None
            candidate = page
            if context:
                try:
                    candidate = await context.new_page()
                    await candidate.bring_to_front()
                except Exception:
                    candidate = page
            await candidate.goto(fallback_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(1.0)
            page = await self._adopt_live_page(candidate, stage=f"{stage} 第{attempt + 1}次恢复后")
            if 'about:blank' not in page.url:
                logger.info(f"✅ 页面恢复成功: {page.url}")
                return page
            logger.warning(f"⚠️ 第 {attempt + 1} 次恢复后仍是about:blank")

        raise RuntimeError(f"{stage} 页面多次恢复失败，仍是about:blank")
    
    async def _wait_for_content_load(self, page: Page) -> None:
        """等待Boss直聘内容加载完成 - 快速模式，总等待 ≤ 3秒"""
        try:
            # 用组合选择器一次等待（任意一个出现即可），最多3秒
            combined = (
                '.job-card-wrapper, .job-list-item, li[data-jid], .job-primary, '
                '.job-card-left, [class*="job-card"]'
            )
            await page.wait_for_selector(combined, timeout=3000)
            logger.info("✅ 骨架屏已消失: .skeleton")  # 保持原有日志格式
        except Exception:
            # 超时说明可能无内容，记录但继续（让后续选择器兜底）
            logger.info("⏳ 内容加载等待超时（继续处理）")
    
    async def _handle_page_overlays(self, page: Page) -> None:
        """处理页面覆盖层（弹窗、加载中等）"""
        try:
            # 检查登录弹窗
            login_modal = await page.query_selector('.login-dialog, .dialog-wrap, .modal')
            if login_modal and await login_modal.is_visible():
                # 不主动点击弹窗，避免触发反爬跳转about:blank
                logger.warning("⚠️ 检测到登录弹窗，保持页面不做点击操作")
                await asyncio.sleep(0.3)
            
            # 检查加载中状态
            loading_selectors = ['.loading', '.spinner', '[class*="loading"]', '.skeleton']
            for selector in loading_selectors:
                loading_elem = await page.query_selector(selector)
                if loading_elem and await loading_elem.is_visible():
                    logger.info(f"⏳ 检测到加载状态: {selector}")
                    # 等待加载完成
                    try:
                        await page.wait_for_selector(selector, state="hidden", timeout=10000)
                    except:
                        pass  # 超时不影响继续执行
                    break
            
            # 检查验证码
            captcha = await page.query_selector('.captcha, .verify-wrap, [class*="captcha"]')
            if captcha and await captcha.is_visible():
                logger.warning("🔒 检测到验证码，需要人工处理")
                
        except Exception as e:
            logger.debug(f"处理页面覆盖层时出错: {e}")
    
    async def _get_job_elements(self, page: Page, selectors: List[str]) -> List[ElementHandle]:
        """获取岗位元素，使用最佳选择器"""
        all_elements = []
        seen_positions = set()  # 用于去重
        
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                logger.debug(f"选择器 '{selector}' 找到 {len(elements)} 个元素")
                
                for element in elements:
                    # 基于位置去重
                    try:
                        bbox = await element.bounding_box()
                        if bbox:
                            position_key = (round(bbox['x']), round(bbox['y']))
                            if position_key not in seen_positions:
                                seen_positions.add(position_key)
                                all_elements.append(element)
                    except:
                        # 如果获取位置失败，仍然包含元素
                        all_elements.append(element)
                        
            except Exception as e:
                logger.debug(f"选择器 '{selector}' 执行失败: {e}")
        
        # 过滤无效元素
        valid_elements = []
        for element in all_elements:
            try:
                # 检查元素是否可见且包含内容
                if await element.is_visible():
                    text = await element.inner_text()
                    if text and len(text.strip()) > 20:  # 岗位信息应该有一定长度
                        valid_elements.append(element)
            except:
                continue
        
        logger.info(f"从 {len(all_elements)} 个元素中筛选出 {len(valid_elements)} 个有效岗位")
        return valid_elements
    
    async def _discover_field_selectors(self, page: Page, sample_elements: List[ElementHandle]) -> Dict[str, List[str]]:
        """为每个字段发现最佳选择器"""
        field_selectors = {}
        field_types = ["job_title", "company_name", "salary", "location", "job_link"]
        
        logger.info("🔬 分析字段选择器...")
        
        for field_type in field_types:
            try:
                # 使用样本元素测试选择器
                best_selectors = []
                
                # 获取该字段的预定义选择器
                config = self.smart_selector.selector_configs.get(field_type, {})
                all_selectors = config.get("primary", []) + config.get("fallback", [])
                
                # 在样本元素上测试每个选择器
                selector_scores = {}
                
                for selector in all_selectors:
                    success_count = 0
                    quality_sum = 0.0
                    
                    for element in sample_elements:
                        try:
                            sub_element = await element.query_selector(selector)
                            if sub_element:
                                text = await sub_element.inner_text()
                                if text and text.strip():
                                    quality = self.smart_selector._calculate_quality_score(text.strip(), field_type)
                                    if quality > 0.3:
                                        success_count += 1
                                        quality_sum += quality
                        except:
                            continue
                    
                    if success_count > 0:
                        avg_quality = quality_sum / success_count
                        success_rate = success_count / len(sample_elements)
                        score = success_rate * 0.7 + avg_quality * 0.3
                        selector_scores[selector] = score
                
                # 选择最佳的选择器
                sorted_selectors = sorted(selector_scores.items(), key=lambda x: x[1], reverse=True)
                best_selectors = [sel for sel, score in sorted_selectors[:3] if score > 0.2]
                
                field_selectors[field_type] = best_selectors
                logger.debug(f"{field_type} 最佳选择器: {best_selectors}")
                
            except Exception as e:
                logger.warning(f"发现 {field_type} 选择器失败: {e}")
                field_selectors[field_type] = config.get("primary", [])
        
        return field_selectors
    
    async def _extract_jobs_batch(self, job_elements: List[ElementHandle], 
                                 field_selectors: Dict[str, List[str]]) -> List[Dict]:
        """批量提取岗位数据"""
        jobs = []
        
        for i, element in enumerate(job_elements):
            try:
                job_data = await self._extract_single_job_enhanced(element, field_selectors, i)
                if job_data:
                    jobs.append(job_data)
                    
                # 添加小延迟，避免过于频繁的DOM操作
                if i % 5 == 0:
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                logger.warning(f"提取第 {i+1} 个岗位失败: {e}")
                continue
        
        return jobs

    async def _extract_jobs_fast_snapshot(self, page: Page, max_jobs: int) -> List[Dict]:
        """使用单次DOM快照快速提取岗位，降低中途about:blank导致的丢数风险"""
        try:
            raw_jobs = await page.evaluate(
                """(maxJobs) => {
                    const selectors = [
                        'li.job-card-wrapper',
                        'li[data-jid]',
                        'li[class*="job"]',
                        '.job-card-left',
                        '.job-list-item',
                    ];
                    const nodes = [];
                    const seen = new Set();
                    for (const sel of selectors) {
                        for (const el of document.querySelectorAll(sel)) {
                            const key = (el.getAttribute('data-jid') || '') + '|' + (el.innerText || '').slice(0, 40);
                            if (!seen.has(key)) {
                                seen.add(key);
                                nodes.push(el);
                            }
                        }
                    }

                    const getText = (el) => (el && el.textContent ? el.textContent.replace(/\\s+/g, ' ').trim() : '');
                    const jobs = [];
                    for (const card of nodes.slice(0, maxJobs)) {
                        const titleEl = card.querySelector('.job-name, .job-title, .job-info h3, h3, a[href*="job_detail"]');
                        const companyEl = card.querySelector('.company-name, .company-text, .company-info .name, .company-info h3, .boss-name');
                        const salaryEl = card.querySelector('.job-salary, .salary, .red, [class*="salary"]');
                        const locationEl = card.querySelector('.job-area, [class*="location"], [class*="area"]');
                        const linkEl = card.querySelector('a[href*="job_detail"], a.job-card-left, a.job-card-body, a[ka*="search_list"]');

                        let url = linkEl && linkEl.getAttribute('href') ? linkEl.getAttribute('href') : '';
                        if (url && url.startsWith('/')) {
                            url = new URL(url, location.origin).href;
                        }

                        const title = getText(titleEl);
                        const company = getText(companyEl);
                        if (!title || !company) continue;

                        jobs.push({
                            title,
                            company,
                            salary: getText(salaryEl) || '薪资面议',
                            work_location: getText(locationEl) || '地点待确认',
                            url: url || '',
                            title_confidence: 0.8,
                            company_confidence: 0.8,
                            salary_confidence: 0.6,
                            work_location_confidence: 0.6,
                            extraction_method: 'dom_snapshot',
                            engine_source: 'Playwright快速快照提取',
                            extraction_timestamp: Date.now() / 1000,
                        });
                    }
                    return jobs;
                }""",
                max_jobs,
            )
            return raw_jobs or []
        except Exception as e:
            logger.debug(f"快速DOM快照提取失败: {e}")
            return []

    def _merge_jobs(self, primary_jobs: List[Dict], supplement_jobs: List[Dict], max_jobs: int) -> List[Dict]:
        """合并两批岗位并去重，优先保留primary_jobs"""
        merged: List[Dict] = []
        seen = set()

        def job_key(job: Dict) -> str:
            url = (job.get("url") or "").strip()
            if url:
                return f"url:{url}"
            title = (job.get("title") or "").strip()
            company = (job.get("company") or "").strip()
            return f"tc:{title}|{company}"

        for job in (primary_jobs + supplement_jobs):
            key = job_key(job)
            if key in seen:
                continue
            seen.add(key)
            merged.append(job)
            if len(merged) >= max_jobs:
                break

        return merged
    
    async def _extract_single_job_enhanced(self, element: ElementHandle, 
                                          field_selectors: Dict[str, List[str]], 
                                          index: int) -> Optional[Dict]:
        """使用增强算法提取单个岗位"""
        try:
            job_data = {}
            
            logger.debug(f"开始提取岗位 {index+1}")
            
            # 提取各字段数据
            for field_type, selectors in field_selectors.items():
                if not selectors:
                    logger.debug(f"字段 {field_type} 没有可用选择器")
                    continue
                    
                extracted_field = await self.smart_selector.extract_field_smart(
                    element, field_type, selectors
                )
                
                logger.debug(f"字段 {field_type} 提取结果: '{extracted_field.value}' (置信度: {extracted_field.confidence:.2f})")
                
                # 记录统计信息
                success = extracted_field.confidence > 0.3
                self.smart_selector.update_selector_stats(
                    field_type, extracted_field.source_selector, success, extracted_field.confidence
                )
                
                # 存储提取结果
                field_key = self._get_field_key(field_type)
                job_data[field_key] = extracted_field.value
                job_data[f"{field_key}_confidence"] = extracted_field.confidence
                job_data[f"{field_key}_selector"] = extracted_field.source_selector
                
                if extracted_field.validation_errors:
                    job_data[f"{field_key}_warnings"] = extracted_field.validation_errors
            
            # 添加元数据
            job_data.update({
                "extraction_index": index,
                "extraction_method": "enhanced",
                "engine_source": "Playwright增强提取",
                "extraction_timestamp": time.time()
            })
            
            logger.debug(f"岗位 {index+1} 完整数据: title='{job_data.get('title')}', company='{job_data.get('company')}'")
            
            # 基础验证
            if self._is_valid_job_data(job_data):
                logger.debug(f"✅ 岗位 {index+1} 验证通过")
                return job_data
            else:
                logger.debug(f"❌ 岗位 {index+1} 数据验证失败")
                # 如果验证失败，尝试降级提取
                logger.debug(f"尝试对岗位 {index+1} 进行降级文本提取...")
                try:
                    text_content = await element.inner_text()
                    fallback_job = await self._extract_basic_job_info(element, text_content, index)
                    if fallback_job:
                        logger.debug(f"✅ 岗位 {index+1} 降级提取成功")
                        return fallback_job
                except Exception as e:
                    logger.debug(f"岗位 {index+1} 降级提取也失败: {e}")
                return None
                
        except Exception as e:
            logger.error(f"提取岗位 {index+1} 时出错: {e}")
            return None
    
    def _get_field_key(self, field_type: str) -> str:
        """将字段类型转换为数据字典键名"""
        mapping = {
            "job_title": "title",
            "company_name": "company", 
            "salary": "salary",
            "location": "work_location",
            "job_link": "url"
        }
        return mapping.get(field_type, field_type)
    
    def _is_valid_job_data(self, job_data: Dict) -> bool:
        """验证岗位数据的基本有效性"""
        required_fields = ["title", "company"]
        
        for field in required_fields:
            value = job_data.get(field, "")
            if not value or value in [
                "信息获取失败", "职位信息获取失败", "公司信息获取失败"
            ]:
                logger.debug(f"岗位数据无效: {field} = '{value}'")
                return False
        
        # 检查数据置信度 - 降低阈值以提高通过率
        title_confidence = job_data.get("title_confidence", 0)
        company_confidence = job_data.get("company_confidence", 0)
        
        logger.debug(f"置信度检查: title={title_confidence:.2f}, company={company_confidence:.2f}")
        
        # 降低置信度要求
        if title_confidence < 0.1 or company_confidence < 0.1:
            logger.debug(f"岗位数据置信度过低")
            return False
        
        logger.debug(f"岗位数据验证通过: {job_data.get('title')} @ {job_data.get('company')}")
        return True
    
    async def _validate_and_enhance_jobs(self, jobs: List[Dict], page: Page) -> List[Dict]:
        """验证和增强岗位数据"""
        enhanced_jobs = []
        
        for job in jobs:
            try:
                # 数据清洗和格式化
                enhanced_job = self._clean_and_format_job(job)
                
                # 尝试获取缺失的重要字段
                if enhanced_job.get("salary") == "薪资面议" or not enhanced_job.get("work_location"):
                    enhanced_job = await self._fill_missing_fields(enhanced_job, page)
                
                # 添加默认字段
                enhanced_job = self._add_default_fields(enhanced_job)
                
                enhanced_jobs.append(enhanced_job)
                
            except Exception as e:
                logger.warning(f"增强岗位数据失败: {e}")
                enhanced_jobs.append(job)  # 保留原始数据
        
        return enhanced_jobs
    
    def _clean_and_format_job(self, job: Dict) -> Dict:
        """清洗和格式化岗位数据"""
        cleaned_job = job.copy()
        
        # 清理标题
        if "title" in cleaned_job:
            title = cleaned_job["title"]
            # 处理职位-地点格式
            if '-' in title and len(title.split('-')) >= 2:
                parts = title.split('-')
                # 选择更像职位名称的部分
                if len(parts[0]) > len(parts[1]) * 1.5:
                    cleaned_job["title"] = parts[0].strip()
                    # 如果地点信息缺失，尝试从标题提取
                    if not cleaned_job.get("work_location") or cleaned_job["work_location"] == "地点待确认":
                        location_part = parts[1].strip()
                        if any(city in location_part for city in ['北京', '上海', '深圳', '杭州', '广州']):
                            cleaned_job["work_location"] = location_part
        
        # 清理薪资格式
        if "salary" in cleaned_job:
            salary = cleaned_job["salary"]
            if salary and salary != "薪资面议":
                # 标准化薪资格式
                salary = salary.replace('·', '-').replace('薪', '')
                # 确保K的大小写一致
                salary = re.sub(r'k(?=[\d\-·])', 'K', salary, flags=re.IGNORECASE)
                cleaned_job["salary"] = salary
        
        # 清理地点信息
        if "work_location" in cleaned_job:
            location = cleaned_job["work_location"]
            if location and location != "地点待确认":
                # 标准化地点格式
                if '·' not in location and any(city in location for city in ['北京', '上海', '深圳', '杭州']):
                    # 为主要城市添加格式化
                    for city in ['北京', '上海', '深圳', '杭州', '广州']:
                        if city in location:
                            location = location.replace(city, f"{city}·")
                            break
                cleaned_job["work_location"] = location.strip()
        
        return cleaned_job
    
    async def _fill_missing_fields(self, job: Dict, page: Page) -> Dict:
        """尝试填充缺失的重要字段"""
        # 如果有URL，可以尝试访问详情页获取更多信息
        if job.get("url") and job["url"].startswith("http"):
            try:
                # 这里可以实现详情页抓取逻辑
                # 当前简化处理，只记录需要改进的地方
                logger.debug(f"岗位 {job.get('title', '')} 有URL，可进一步获取详情")
            except Exception as e:
                logger.debug(f"获取详情页失败: {e}")
        
        return job
    
    def _add_default_fields(self, job: Dict) -> Dict:
        """添加默认字段和标签"""
        # 严格真实模式：仅补齐字段结构，不补任何解释性/模板文案
        defaults = {
            "tags": [],
            "job_description": "",
            "job_requirements": "",
            "company_details": "",
            "benefits": "",
            "experience_required": "",
            "education_required": "",
        }
        
        for key, default_value in defaults.items():
            if key not in job or not job[key]:
                job[key] = default_value
        
        return job
    
    async def _debug_page_content(self, page: Page) -> None:
        """调试页面内容，帮助分析问题"""
        try:
            # 截图保存
            timestamp = int(time.time())
            screenshot_path = f"debug_extraction_{timestamp}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"📸 已保存调试截图: {screenshot_path}")
            
            # 保存页面HTML
            content = await page.content()
            html_path = f"debug_page_{timestamp}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"📄 已保存页面HTML: {html_path}")
            
            # 检查页面基本信息
            title = await page.title()
            url = page.url
            logger.info(f"🌐 页面信息 - 标题: {title}, URL: {url}")
            
            # 检查是否有常见的错误页面标识
            error_indicators = await page.query_selector_all('.error, .not-found, .empty, [class*="error"]')
            if error_indicators:
                logger.warning(f"⚠️ 检测到 {len(error_indicators)} 个错误指示元素")
            
        except Exception as e:
            logger.error(f"调试页面内容失败: {e}")
    
    def _update_performance_stats(self, successful_count: int, extraction_time: float) -> None:
        """更新性能统计"""
        self.performance_stats["total_extractions"] += 1
        if successful_count > 0:
            self.performance_stats["successful_extractions"] += 1
        
        # 更新平均提取时间
        total_time = self.performance_stats["avg_extraction_time"] * (self.performance_stats["total_extractions"] - 1)
        self.performance_stats["avg_extraction_time"] = (total_time + extraction_time) / self.performance_stats["total_extractions"]
    
    def get_performance_report(self) -> Dict:
        """获取性能报告"""
        stats = self.performance_stats.copy()
        if stats["total_extractions"] > 0:
            stats["success_rate"] = stats["successful_extractions"] / stats["total_extractions"]
        else:
            stats["success_rate"] = 0.0
        
        # 添加选择器统计
        stats["selector_stats"] = self.smart_selector.selector_stats
        
        return stats
    
    async def _fallback_extraction(self, page: Page, max_jobs: int) -> List[Dict]:
        """降级提取策略 - 当智能选择器失败时使用"""
        logger.info("🆘 启用降级提取策略...")
        
        try:
            # 策略1: 更智能的页面结构分析
            potential_containers = []
            
            # Boss直聘常见的页面结构模式
            boss_patterns = [
                'li[class*="job"]',     # 包含job的li元素
                'div[class*="job"]',    # 包含job的div元素
                'a[href*="job"]',       # 包含job链接的a元素
                '[data-*]',             # 任何data属性元素
                '.card, .item, .box',   # 常见容器类名
                'li, div[class], a[class]'  # 有类名的基础元素
            ]
            
            logger.info(f"🔍 尝试Boss直聘页面结构模式识别...")
            
            for pattern in boss_patterns:
                try:
                    elements = await page.query_selector_all(pattern)
                    logger.debug(f"模式 '{pattern}' 找到 {len(elements)} 个元素")
                    
                    for element in elements:
                        try:
                            if await element.is_visible():
                                text = await element.inner_text()
                                # 检查是否包含岗位相关关键词
                                if text and len(text) > 50:  # 内容足够长
                                    # 检查是否包含工作相关词汇  
                                    job_keywords = ['工程师', '开发', '经理', '专员', '主管', '总监', '分析师', 
                                                  '设计师', '产品', '运营', '市场', '销售', '财务', '人事',
                                                  'AI', '人工智能', '机器学习', '算法', '解决方案', '金融',
                                                  '咨询', '顾问', '架构师', '技术', '研发', '科技']
                                    
                                    if any(keyword in text for keyword in job_keywords):
                                        potential_containers.append(element)
                                        
                                if len(potential_containers) >= max_jobs:
                                    break
                        except:
                            continue
                    
                    if len(potential_containers) >= max_jobs:
                        break
                except Exception as e:
                    logger.debug(f"模式 '{pattern}' 处理失败: {e}")
                    continue
                
                if len(potential_containers) >= max_jobs:
                    break
            
            logger.info(f"🔍 降级策略找到 {len(potential_containers)} 个潜在岗位容器")
            
            if not potential_containers:
                logger.error("❌ 降级策略未找到任何岗位容器，返回空结果（可能未登录或页面被反爬拦截）")
                return []
            
            # 从潜在容器中提取基础信息
            jobs = []
            for i, container in enumerate(potential_containers[:max_jobs]):
                try:
                    text_content = await container.inner_text()
                    job_data = await self._extract_basic_job_info(container, text_content, i)
                    if job_data:
                        jobs.append(job_data)
                except Exception as e:
                    logger.debug(f"提取第 {i+1} 个降级容器失败: {e}")
                    continue
            
            logger.info(f"✅ 降级策略成功提取 {len(jobs)} 个岗位")
            return jobs
            
        except Exception as e:
            logger.error(f"❌ 降级提取策略失败: {e}")
            return []
    
    async def _extract_basic_job_info(self, container: ElementHandle, text_content: str, index: int) -> Optional[Dict]:
        """从容器中提取基础岗位信息"""
        try:
            # 尝试提取链接
            link_element = await container.query_selector('a[href]')
            job_url = ""
            if link_element:
                href = await link_element.get_attribute('href')
                if href:
                    job_url = href if href.startswith('http') else f"https://www.zhipin.com{href}"
            
            # 简单文本解析提取信息
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            
            # 尝试识别职位名称（通常是第一行或包含关键词的行）
            job_title = "职位信息获取失败"
            
            # 扩展职位关键词列表
            job_keywords = [
                '工程师', '开发', '经理', '专员', '主管', '分析师', '架构师', '总监',
                '风控', 'AI', '产品', '运营', '设计', '测试', '项目', '数据',
                '前端', '后端', '算法', '研发', '技术', '咨询', '顾问', '专家',
                'Java', 'Python', 'Go', 'C++', '解决方案', '售前', '售后'
            ]
            
            # 首先检查前3行是否包含职位关键词
            for i, line in enumerate(lines[:5]):  # 扩展到前5行
                if any(keyword.lower() in line.lower() for keyword in job_keywords):
                    job_title = line[:50]  # 限制长度
                    break
                # 如果第一行较短且不包含薪资/地点信息，可能是职位名
                elif i == 0 and len(line) < 30 and not any(x in line for x in ['K', '万', '元', '·']):
                    job_title = line[:50]
                    break
            
            # 尝试识别公司名称
            company_name = "公司信息获取失败"
            for line in lines:
                if len(line) > 2 and len(line) < 30:  # 合理的公司名长度
                    if not any(char in line for char in ['K', '万', '年', '经验', '学历']):
                        company_name = line
                        break
            
            # 尝试识别薪资
            salary = "薪资面议"
            for line in lines:
                if any(keyword in line for keyword in ['K', '万', '薪', '元']):
                    # 简单薪资格式验证
                    import re
                    if re.search(r'\d+[KkWw万千]', line):
                        salary = line[:20]
                        break
                        
            # 尝试识别地点
            location = "地点待确认"
            cities = ['北京', '上海', '广州', '深圳', '杭州', '南京', '武汉', '成都']
            for line in lines:
                for city in cities:
                    if city in line and len(line) < 50:
                        location = line
                        break
                if location != "地点待确认":
                    break
            
            return {
                "title": job_title,
                "company": company_name,
                "salary": salary,
                "work_location": location,
                "url": job_url,
                "tags": [],
                # 严格真实模式：不生成占位文案，缺失即留空
                "job_description": "",
                "job_requirements": "",
                "company_details": "",
                "benefits": "",
                "experience_required": "",
                "education_required": "",
                "extraction_index": index,
                "extraction_method": "fallback",
                "engine_source": "Playwright降级提取",
                "extraction_timestamp": time.time(),
                "fallback_extraction": True
            }
            
        except Exception as e:
            logger.debug(f"基础信息提取失败: {e}")
            return None
    
    async def _generate_minimal_fallback_data(self, max_jobs: int) -> List[Dict]:
        """严格真实模式下禁用示例数据"""
        logger.warning("严格真实模式：已禁用最小化示例数据生成")
        return []
