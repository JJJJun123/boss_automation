#!/usr/bin/env python3
"""
智能选择器系统
提供动态选择器检测、自适应机制和数据质量验证
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from playwright.async_api import Page, ElementHandle

logger = logging.getLogger(__name__)


@dataclass
class SelectorResult:
    """选择器测试结果"""
    selector: str
    success_rate: float
    avg_quality_score: float
    found_elements: int
    extraction_time: float
    errors: List[str]


@dataclass
class ExtractedField:
    """提取的字段数据"""
    value: str
    confidence: float  # 0-1 置信度
    source_selector: str
    validation_errors: List[str]


class SmartSelector:
    """智能选择器管理器"""
    
    def __init__(self):
        # 预定义的选择器配置，按优先级排序
        self.selector_configs = {
            "job_container": {
                "primary": [
                    'li.job-card-wrapper',            # Boss直聘最新结构
                    'li[data-jid]',                   # Boss直聘岗位ID
                    '.job-card-left',                 # 左侧卡片
                    'li:has(a[href*="job_detail"])',  # 包含岗位链接的li
                    '.job-detail-box',                # Boss直聘特有
                    'a[ka*="search_list"]',           # ka属性标识
                    '[data-jobid]',                   # 数据属性标识
                    '.job-list-item',                 # 列表项目
                ],
                "fallback": [
                    '.job-card-wrapper', '.job-card-container',
                    'li.job-card-container', '.job-card-left', 
                    '.job-info-box', '.job-list-box .job-card-body',
                    '.job-card', '.job-item', '.search-job-result',
                    'div[data-jobid]', 'a[data-jobid]'
                ],
                "generic": [
                    'li[class*="job"]', 'div[class*="job-card"]',
                    '.job-primary', '.job-content',
                    'li', 'article', '.result-item',
                    'div[class*="item"]', 'div[class*="card"]'
                ]
            },
            "job_title": {
                "primary": [
                    '.job-name', '.job-title', 
                    'a .job-name', 'h3.job-name',
                    '.job-card-body .name a',  # Boss直聘新结构
                    'span.job-name',            # 可能是span元素
                    '.job-info .name'           # 岗位信息名称
                ],
                "fallback": [
                    '.job-info h3', '.job-primary .name',
                    '.job-card-body .job-name', '[class*="job"][class*="name"]',
                    'a[href*="job_detail"]:first-child',  # 第一个岗位链接
                    '.name:not(.company-name)',           # 排除公司名的name类
                    'h3:first-child'                      # 第一个h3元素
                ],
                "generic": [
                    '.position-name', 'h3', '.title',
                    'a:first-child', 'span:first-child'  # 第一个链接或span
                ]
            },
            "company_name": {
                "primary": [
                    '.company-name', '.company-text',
                    '.job-company', '.company-info .name'
                ],
                "fallback": [
                    'h3:not(.job-name):not([class*="salary"])',
                    '.company-info h3', '.job-info .company'
                ],
                "generic": [
                    'span:not([class*="salary"]):not([class*="location"])',
                    'div:not([class*="salary"]):not([class*="location"])'
                ]
            },
            "salary": {
                "primary": [
                    '.job-salary',                    # Boss直聘主要薪资类名
                    'span.job-salary',                # span版本
                    '[class*="salary"]',              # 包含salary的类
                    '.red',                           # 红色文字（薪资常用）
                    '.salary',                        # 通用salary类
                    '.job-limit .red',                # 岗位限制中的红色文字
                    '.job-primary .red',              # 主要信息中的红色文字
                    '.text-warning',                  # 警告色文字
                    '.text-orange'                    # 橙色文字
                ],
                "fallback": [
                    'span:has-text("K")',             # 包含K的span
                    'span:has-text("万")',            # 包含万的span
                    'div:has-text("K")',              # 包含K的div
                    '.job-info span.red',             # 岗位信息中的红色span
                    '.job-info .salary'               # 岗位信息中的薪资
                ],
                "generic": [
                    'em', 'span[class*="pay"]', '.money', '.price',
                    'span[class*="wage"]', 'span[class*="salary"]'
                ]
            },
            "location": {
                "primary": [
                    '[class*="location"]', '[class*="area"]', 
                    '.job-area', '.work-addr', '.job-location'
                ],
                "fallback": [
                    '.job-primary .job-area', '.job-area-wrapper',
                    '.area-district', '.job-city', 'span[class*="area"]'
                ],
                "generic": [
                    'span:last-child', 'div:last-child'
                ]
            },
            "job_link": {
                "primary": [
                    'a.job-card-body', 'a.job-card-left',
                    'a[ka^="search_list"]', 'a[href*="job_detail"]'
                ],
                "fallback": [
                    '.job-card-wrapper > a', '.job-primary > a',
                    'a:has(.job-name)', 'a:has(.job-title)'
                ],
                "generic": [
                    'a[href*="/job"]', 'a'
                ]
            }
        }
        
        # 数据验证规则
        self.validation_rules = {
            "job_title": {
                "min_length": 2,
                "max_length": 50, 
                "forbidden_words": ["筛选", "排序", "更多", "加载", "搜索"],
                "required_pattern": None
            },
            "company_name": {
                "min_length": 2,
                "max_length": 30,
                "forbidden_words": ["K·薪", "万·薪", "经验", "学历", "岗位", "区", "市"],
                "forbidden_chars": ["·", "年"]
            },
            "salary": {
                "min_length": 2,
                "max_length": 20,
                "required_chars": ["K", "k", "万", "千", "元", "¥", "$"],
                "pattern": r'\d+[KkWw万千]'
            },
            "location": {
                "min_length": 2,
                "max_length": 50,
                "required_words": ["市", "区", "县", "街", "路", "镇", "村", "·"],
                "forbidden_words": ["K", "经验", "学历", "岗位", "职位", "万", "千"]
            }
        }
        
        # 选择器性能统计
        self.selector_stats = {}
        
    async def find_best_selectors(self, page: Page, field_type: str, sample_size: int = 5) -> List[str]:
        """
        动态测试选择器，找出当前页面最有效的选择器组合
        
        Args:
            page: Playwright页面对象
            field_type: 字段类型（job_container, job_title等）
            sample_size: 测试样本数量
            
        Returns:
            按效果排序的选择器列表
        """
        if field_type not in self.selector_configs:
            logger.warning(f"未知字段类型: {field_type}")
            return []
        
        selectors = self.selector_configs[field_type]
        all_selectors = selectors["primary"] + selectors["fallback"] + selectors["generic"]
        
        results = []
        
        for selector in all_selectors:
            try:
                result = await self._test_selector(page, selector, field_type, sample_size)
                results.append(result)
                logger.debug(f"选择器测试: {selector} -> 成功率: {result.success_rate:.2f}, 质量: {result.avg_quality_score:.2f}")
                
            except Exception as e:
                logger.debug(f"选择器测试失败: {selector} - {e}")
        
        # 按综合评分排序（成功率 * 0.6 + 质量分 * 0.4）
        results.sort(key=lambda x: x.success_rate * 0.6 + x.avg_quality_score * 0.4, reverse=True)
        
        best_selectors = [r.selector for r in results[:3] if r.success_rate > 0.3]
        
        if best_selectors:
            logger.info(f"找到最佳{field_type}选择器: {best_selectors}")
        else:
            logger.warning(f"未找到有效的{field_type}选择器")
            
        return best_selectors
    
    async def _test_selector(self, page: Page, selector: str, field_type: str, sample_size: int) -> SelectorResult:
        """测试单个选择器的效果"""
        import time
        start_time = time.time()
        
        try:
            elements = await page.query_selector_all(selector)
            found_count = len(elements)
            
            if found_count == 0:
                return SelectorResult(
                    selector=selector,
                    success_rate=0.0,
                    avg_quality_score=0.0,
                    found_elements=0,
                    extraction_time=time.time() - start_time,
                    errors=["未找到元素"]
                )
            
            # 测试前几个元素的数据质量
            test_elements = elements[:min(sample_size, found_count)]
            quality_scores = []
            errors = []
            
            for element in test_elements:
                try:
                    text = await element.inner_text()
                    quality_score = self._calculate_quality_score(text.strip(), field_type)
                    quality_scores.append(quality_score)
                except Exception as e:
                    errors.append(f"文本提取失败: {e}")
                    quality_scores.append(0.0)
            
            success_rate = len([s for s in quality_scores if s > 0.3]) / len(quality_scores)
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
            
            return SelectorResult(
                selector=selector,
                success_rate=success_rate,
                avg_quality_score=avg_quality,
                found_elements=found_count,
                extraction_time=time.time() - start_time,
                errors=errors
            )
            
        except Exception as e:
            return SelectorResult(
                selector=selector,
                success_rate=0.0,
                avg_quality_score=0.0,
                found_elements=0,
                extraction_time=time.time() - start_time,
                errors=[str(e)]
            )
    
    def _calculate_quality_score(self, text: str, field_type: str) -> float:
        """计算文本数据的质量评分（0-1）"""
        if not text:
            return 0.0
        
        rules = self.validation_rules.get(field_type, {})
        score = 1.0
        
        # 长度检查
        if "min_length" in rules and len(text) < rules["min_length"]:
            score -= 0.3
        if "max_length" in rules and len(text) > rules["max_length"]:
            score -= 0.2
        
        # 禁用词检查
        if "forbidden_words" in rules:
            for word in rules["forbidden_words"]:
                if word in text:
                    score -= 0.4
                    break
        
        # 禁用字符检查
        if "forbidden_chars" in rules:
            for char in rules["forbidden_chars"]:
                if char in text:
                    score -= 0.2
        
        # 必需字符/词检查
        if "required_chars" in rules:
            if not any(char in text for char in rules["required_chars"]):
                score -= 0.5
        
        if "required_words" in rules:
            if not any(word in text for word in rules["required_words"]):
                score -= 0.3
        
        # 模式匹配检查
        if "pattern" in rules and rules["pattern"]:
            if not re.search(rules["pattern"], text):
                score -= 0.4
        
        return max(0.0, score)
    
    async def extract_field_smart(self, element: ElementHandle, field_type: str, 
                                best_selectors: List[str] = None) -> ExtractedField:
        """
        智能提取字段数据
        
        Args:
            element: 页面元素
            field_type: 字段类型
            best_selectors: 预先确定的最佳选择器列表
            
        Returns:
            提取的字段数据和置信度
        """
        if not best_selectors:
            # 如果没有提供最佳选择器，使用默认选择器
            selectors = self.selector_configs.get(field_type, {})
            best_selectors = selectors.get("primary", []) + selectors.get("fallback", [])
        
        for selector in best_selectors:
            try:
                sub_element = await element.query_selector(selector)
                if sub_element:
                    text = await sub_element.inner_text()
                    if text and text.strip():
                        clean_text = text.strip()
                        quality_score = self._calculate_quality_score(clean_text, field_type)
                        
                        # 对于job_title，增加调试信息
                        if field_type == "job_title":
                            logger.debug(f"职位标题选择器 {selector} 找到文本: '{clean_text}', 质量分: {quality_score}")
                        
                        if quality_score > 0.3:  # 质量阈值
                            # 进行字段特定的清洗
                            cleaned_text = self._clean_field_text(clean_text, field_type)
                            validation_errors = self._validate_field(cleaned_text, field_type)
                            
                            return ExtractedField(
                                value=cleaned_text,
                                confidence=quality_score,
                                source_selector=selector,
                                validation_errors=validation_errors
                            )
                        elif field_type == "job_title" and quality_score > 0:
                            # 对于职位标题，放宽质量要求
                            cleaned_text = self._clean_field_text(clean_text, field_type)
                            return ExtractedField(
                                value=cleaned_text,
                                confidence=quality_score,
                                source_selector=selector,
                                validation_errors=["质量分较低"]
                            )
            except Exception as e:
                logger.debug(f"选择器 {selector} 提取失败: {e}")
                continue
        
        # 如果所有选择器都失败，返回默认值
        default_value = self._get_default_value(field_type)
        return ExtractedField(
            value=default_value,
            confidence=0.0,
            source_selector="default",
            validation_errors=["所有选择器都未能提取到有效数据"]
        )
    
    def _clean_field_text(self, text: str, field_type: str) -> str:
        """对提取的文本进行字段特定的清洗"""
        if field_type == "salary":
            # 清理薪资文本中的异常字符
            text = text.replace('·', '-').replace('薪', '').strip()
            
            # 修复"-K"这种显示异常（Boss直聘的反爬虫导致的不完整显示）
            if re.match(r'^-[Kk]$', text) or re.match(r'^[Kk]-$', text):
                # 这种情况下薪资信息不完整，标记为需要从详情页获取
                logger.debug(f"检测到不完整的薪资格式: {text}")
                return "薪资待更新"  # 特殊标记，后续从详情页更新
            
            # 尝试从更完整的文本中提取
            match = re.search(r'\d+[KkWw万千][\-~]\d+[KkWw万千]', text)
            if match:
                text = match.group()
        
        elif field_type == "company_name":
            # 移除公司名中的多余信息
            text = re.sub(r'\s*\(.*?\)\s*', '', text)  # 去掉括号内容
            text = re.sub(r'\s*（.*?）\s*', '', text)  # 去掉中文括号内容
        
        elif field_type == "location":
            # 地点信息标准化
            if '·' not in text:
                # 为没有·分隔符的地点添加格式化
                cities = ['北京', '上海', '广州', '深圳', '杭州', '南京', '武汉', '成都']
                for city in cities:
                    if city in text and not text.startswith(city):
                        # 将城市名移到前面
                        text = re.sub(city, '', text)
                        text = f"{city}·{text.strip()}"
                        break
        
        elif field_type == "job_title":
            # 岗位标题清洗
            if '-' in text and len(text.split('-')) >= 2:
                # 处理"职位名称-地点"格式
                parts = text.split('-')
                if len(parts[0].strip()) > len(parts[1].strip()):
                    text = parts[0].strip()  # 取较长的部分作为职位名称
        
        return text.strip()
    
    def _validate_field(self, text: str, field_type: str) -> List[str]:
        """验证字段数据，返回错误列表"""
        errors = []
        rules = self.validation_rules.get(field_type, {})
        
        if "min_length" in rules and len(text) < rules["min_length"]:
            errors.append(f"文本长度过短（{len(text)} < {rules['min_length']}）")
        
        if "max_length" in rules and len(text) > rules["max_length"]:
            errors.append(f"文本长度过长（{len(text)} > {rules['max_length']}）")
        
        return errors
    
    def _get_default_value(self, field_type: str) -> str:
        """获取字段的默认值"""
        defaults = {
            "job_title": "职位信息获取失败",
            "company_name": "公司信息获取失败", 
            "salary": "薪资面议",
            "location": "地点待确认",
            "job_link": ""
        }
        return defaults.get(field_type, "信息获取失败")
    
    def update_selector_stats(self, field_type: str, selector: str, success: bool, quality_score: float):
        """更新选择器性能统计"""
        if field_type not in self.selector_stats:
            self.selector_stats[field_type] = {}
        
        if selector not in self.selector_stats[field_type]:
            self.selector_stats[field_type][selector] = {
                "total_attempts": 0,
                "successful_attempts": 0,
                "total_quality": 0.0,
                "avg_quality": 0.0
            }
        
        stats = self.selector_stats[field_type][selector]
        stats["total_attempts"] += 1
        if success:
            stats["successful_attempts"] += 1
        stats["total_quality"] += quality_score
        stats["avg_quality"] = stats["total_quality"] / stats["total_attempts"]
    
    def get_selector_recommendations(self, field_type: str) -> List[str]:
        """基于历史统计数据推荐最佳选择器"""
        if field_type not in self.selector_stats:
            return self.selector_configs.get(field_type, {}).get("primary", [])
        
        stats = self.selector_stats[field_type]
        
        # 按成功率和平均质量排序
        sorted_selectors = sorted(
            stats.items(),
            key=lambda x: (x[1]["successful_attempts"] / x[1]["total_attempts"]) * 0.7 + x[1]["avg_quality"] * 0.3,
            reverse=True
        )
        
        return [selector for selector, _ in sorted_selectors if _["total_attempts"] >= 3]