#!/usr/bin/env python3
"""
统一爬虫接口
提供统一的搜索接口，消除代码重复，支持多种爬虫引擎
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass
from config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class CrawlerEngine(Enum):
    """爬虫引擎枚举"""
    ENHANCED_PLAYWRIGHT = "enhanced_playwright"  # 增强Playwright管理器 (推荐)
    REAL_PLAYWRIGHT = "real_playwright"         # 直接Playwright爬虫  
    MCP_PLAYWRIGHT = "mcp_playwright"           # MCP Playwright爬虫


@dataclass
class SearchParams:
    """搜索参数"""
    keyword: str
    city: str = "shanghai"
    max_jobs: int = 20
    priority: int = 1
    use_cache: bool = True
    fetch_details: bool = False
    engine: CrawlerEngine = CrawlerEngine.ENHANCED_PLAYWRIGHT


@dataclass 
class SearchResult:
    """搜索结果"""
    jobs: List[Dict]
    engine_used: str
    total_found: int
    success: bool
    error_message: Optional[str] = None
    execution_time: float = 0.0
    cache_hit: bool = False


class UnifiedCrawlerInterface:
    """统一爬虫接口"""
    
    def __init__(self):
        self.engine_cache = {}  # 引擎实例缓存
        self.config_manager = ConfigManager()
        self.crawler_config = self.config_manager.get_app_config('crawler')
        self.browser_config = self.crawler_config.get('browser', {})
        self.city_mapping = {
            # 支持多种城市代码格式
            "shanghai": {"name": "上海", "code": "101020100"},
            "beijing": {"name": "北京", "code": "101010100"}, 
            "shenzhen": {"name": "深圳", "code": "101280600"},
            "hangzhou": {"name": "杭州", "code": "101210100"},
            # 兼容城市代码
            "101020100": {"name": "上海", "code": "101020100"},
            "101010100": {"name": "北京", "code": "101010100"},
            "101280600": {"name": "深圳", "code": "101280600"},
            "101210100": {"name": "杭州", "code": "101210100"}
        }
        
    def normalize_city(self, city: Union[str, int]) -> str:
        """标准化城市名称"""
        city_str = str(city).lower()
        
        # 直接匹配
        if city_str in self.city_mapping:
            return city_str if len(city_str) < 10 else "shanghai"
        
        # 模糊匹配
        city_keywords = {
            "shanghai": ["上海", "sh", "shanghai"],
            "beijing": ["北京", "bj", "beijing"],
            "shenzhen": ["深圳", "sz", "shenzhen"], 
            "hangzhou": ["杭州", "hz", "hangzhou"]
        }
        
        for standard_city, keywords in city_keywords.items():
            if any(keyword in city_str for keyword in keywords):
                return standard_city
        
        # 默认返回上海
        logger.warning(f"未识别的城市: {city}，使用默认城市上海")
        return "shanghai"
    
    async def search_jobs(self, params: Union[SearchParams, Dict[str, Any]]) -> SearchResult:
        """
        统一搜索接口
        
        Args:
            params: 搜索参数，可以是SearchParams对象或字典
            
        Returns:
            SearchResult对象
        """
        # 参数标准化
        if isinstance(params, dict):
            search_params = SearchParams(
                keyword=params.get("keyword", ""),
                city=self.normalize_city(params.get("city", "shanghai")),
                max_jobs=params.get("max_jobs", 20),
                priority=params.get("priority", 1),
                use_cache=params.get("use_cache", True),
                fetch_details=params.get("fetch_details", False),
                engine=CrawlerEngine(params.get("engine", "enhanced_playwright"))
            )
        else:
            search_params = params
            search_params.city = self.normalize_city(search_params.city)
        
        # 参数验证
        if not search_params.keyword.strip():
            return SearchResult(
                jobs=[],
                engine_used="none",
                total_found=0,
                success=False,
                error_message="搜索关键词不能为空"
            )
        
        # 执行搜索
        import time
        start_time = time.time()
        
        try:
            result = await self._execute_search(search_params)
            result.execution_time = time.time() - start_time
            return result
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return SearchResult(
                jobs=[],
                engine_used=search_params.engine.value,
                total_found=0,
                success=False,
                error_message=str(e),
                execution_time=time.time() - start_time
            )
    
    async def _execute_search(self, params: SearchParams) -> SearchResult:
        """执行具体搜索逻辑"""
        engine = params.engine
        
        if engine == CrawlerEngine.ENHANCED_PLAYWRIGHT:
            return await self._search_with_enhanced_playwright(params)
        elif engine == CrawlerEngine.REAL_PLAYWRIGHT:
            return await self._search_with_real_playwright(params) 
        elif engine == CrawlerEngine.MCP_PLAYWRIGHT:
            return await self._search_with_mcp_playwright(params)
        else:
            raise ValueError(f"不支持的爬虫引擎: {engine}")
    
    async def _search_with_enhanced_playwright(self, params: SearchParams) -> SearchResult:
        """使用增强Playwright管理器搜索"""
        try:
            from .enhanced_crawler_manager import enhanced_search_jobs
            
            jobs = await enhanced_search_jobs(
                keyword=params.keyword,
                city=params.city,
                max_jobs=params.max_jobs,
                priority=params.priority,
                use_cache=params.use_cache
            )
            
            # 检查是否命中缓存
            cache_hit = any(
                job.get("engine_source", "").find("缓存") != -1 
                for job in jobs
            )
            
            return SearchResult(
                jobs=jobs,
                engine_used="Enhanced Playwright Manager",
                total_found=len(jobs),
                success=True,
                cache_hit=cache_hit
            )
            
        except Exception as e:
            raise Exception(f"增强Playwright管理器搜索失败: {e}")
    
    async def _search_with_real_playwright(self, params: SearchParams) -> SearchResult:
        """使用直接Playwright爬虫搜索"""
        try:
            from .real_playwright_spider import RealPlaywrightBossSpider
            
            headless = self.browser_config.get('headless', False)
            spider = RealPlaywrightBossSpider(headless=headless)
            
            try:
                await spider.start()
                jobs = await spider.search_jobs(
                    params.keyword,
                    params.city, 
                    params.max_jobs
                )
                
                # 添加引擎标识
                for job in jobs:
                    job['engine_source'] = 'Real Playwright Spider'
                
                return SearchResult(
                    jobs=jobs,
                    engine_used="Real Playwright Spider",
                    total_found=len(jobs),
                    success=True
                )
                
            finally:
                await spider.close()
                
        except Exception as e:
            raise Exception(f"Real Playwright爬虫搜索失败: {e}")
    
    async def _search_with_mcp_playwright(self, params: SearchParams) -> SearchResult:
        """使用MCP Playwright爬虫搜索"""
        try:
            from .mcp_client import PlaywrightMCPSync
            
            # 城市名称转换为代码
            city_info = self.city_mapping.get(params.city, {"code": "101020100"})
            city_code = city_info["code"]
            
            spider = PlaywrightMCPSync(headless=False)
            
            try:
                if not spider.start():
                    raise Exception("MCP爬虫启动失败")
                
                jobs = spider.search_jobs(
                    params.keyword,
                    city_code,
                    params.max_jobs
                )
                
                # 添加引擎标识
                for job in jobs:
                    job['engine_source'] = 'Playwright MCP'
                
                return SearchResult(
                    jobs=jobs,
                    engine_used="Playwright MCP",
                    total_found=len(jobs),
                    success=True
                )
                
            finally:
                spider.close()
                
        except Exception as e:
            raise Exception(f"MCP Playwright爬虫搜索失败: {e}")
    
    async def batch_search(self, search_requests: List[Union[SearchParams, Dict[str, Any]]]) -> Dict[str, SearchResult]:
        """
        批量搜索
        
        Args:
            search_requests: 搜索请求列表
            
        Returns:
            请求ID到搜索结果的映射
        """
        results = {}
        
        # 并发执行搜索
        tasks = []
        for i, request in enumerate(search_requests):
            task = asyncio.create_task(self.search_jobs(request))
            tasks.append((f"request_{i}", task))
        
        # 等待所有任务完成
        for request_id, task in tasks:
            try:
                result = await task
                results[request_id] = result
            except Exception as e:
                logger.error(f"批量搜索任务 {request_id} 失败: {e}")
                results[request_id] = SearchResult(
                    jobs=[],
                    engine_used="unknown",
                    total_found=0,
                    success=False,
                    error_message=str(e)
                )
        
        return results
    
    def get_supported_engines(self) -> List[str]:
        """获取支持的引擎列表"""
        return [engine.value for engine in CrawlerEngine]
    
    def get_supported_cities(self) -> List[Dict[str, str]]:
        """获取支持的城市列表"""
        cities = []
        added_cities = set()
        
        for city_key, city_info in self.city_mapping.items():
            if len(city_key) < 10 and city_key not in added_cities:  # 过滤掉城市代码
                cities.append({
                    "key": city_key,
                    "name": city_info["name"],
                    "code": city_info["code"]
                })
                added_cities.add(city_key)
        
        return cities
    
    def recommend_engine(self, requirements: Dict[str, Any]) -> CrawlerEngine:
        """
        根据需求推荐最佳引擎
        
        Args:
            requirements: 需求字典，包含performance, cache, stability等偏好
            
        Returns:
            推荐的引擎
        """
        performance_priority = requirements.get("performance", 0.5)
        cache_priority = requirements.get("cache", 0.7)
        stability_priority = requirements.get("stability", 0.8)
        
        # 计算引擎评分
        engine_scores = {
            CrawlerEngine.ENHANCED_PLAYWRIGHT: (
                performance_priority * 0.9 +  # 高性能
                cache_priority * 1.0 +         # 完整缓存支持
                stability_priority * 0.9       # 高稳定性
            ),
            CrawlerEngine.REAL_PLAYWRIGHT: (
                performance_priority * 0.7 +   # 中等性能
                cache_priority * 0.0 +         # 无缓存
                stability_priority * 0.8       # 较高稳定性
            ),
            CrawlerEngine.MCP_PLAYWRIGHT: (
                performance_priority * 0.6 +   # 较低性能
                cache_priority * 0.0 +         # 无缓存
                stability_priority * 0.6       # 中等稳定性
            )
        }
        
        # 返回评分最高的引擎
        best_engine = max(engine_scores.items(), key=lambda x: x[1])[0]
        
        logger.info(f"根据需求推荐引擎: {best_engine.value}")
        return best_engine


# 全局统一接口实例
_unified_crawler = None


def get_unified_crawler() -> UnifiedCrawlerInterface:
    """获取统一爬虫接口实例"""
    global _unified_crawler
    if _unified_crawler is None:
        _unified_crawler = UnifiedCrawlerInterface()
    return _unified_crawler


# 便捷函数接口
async def unified_search_jobs(
    keyword: str,
    city: str = "shanghai", 
    max_jobs: int = 20,
    engine: str = "enhanced_playwright",
    **kwargs
) -> List[Dict]:
    """
    统一搜索接口（便捷函数）
    
    Args:
        keyword: 搜索关键词
        city: 城市
        max_jobs: 最大岗位数
        engine: 爬虫引擎
        **kwargs: 其他参数
        
    Returns:
        岗位列表
    """
    crawler = get_unified_crawler()
    
    params = SearchParams(
        keyword=keyword,
        city=city,
        max_jobs=max_jobs,
        engine=CrawlerEngine(engine),
        **kwargs
    )
    
    result = await crawler.search_jobs(params)
    
    if result.success:
        return result.jobs
    else:
        logger.error(f"搜索失败: {result.error_message}")
        return []


async def unified_batch_search(search_requests: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
    """
    统一批量搜索接口（便捷函数）
    
    Args:
        search_requests: 搜索请求列表
        
    Returns:
        搜索结果映射
    """
    crawler = get_unified_crawler()
    results = await crawler.batch_search(search_requests)
    
    # 简化结果格式
    simplified_results = {}
    for request_id, result in results.items():
        simplified_results[request_id] = result.jobs if result.success else []
    
    return simplified_results


def get_crawler_capabilities() -> Dict[str, Any]:
    """获取爬虫系统能力信息"""
    crawler = get_unified_crawler()
    
    return {
        "supported_engines": crawler.get_supported_engines(),
        "supported_cities": crawler.get_supported_cities(),
        "features": {
            "caching": True,
            "concurrent_search": True,
            "performance_monitoring": True,
            "auto_optimization": True,
            "error_recovery": True,
            "session_management": True
        },
        "version": "2.0-unified"
    }