#!/usr/bin/env python3
"""
统一爬虫接口
提供统一的搜索接口，使用简化后的统一爬虫引擎
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


@dataclass
class SearchParams:
    """搜索参数"""
    keyword: str
    city: str = "shanghai"
    max_jobs: int = 20
    priority: int = 1
    use_cache: bool = True


@dataclass 
class SearchResult:
    """搜索结果"""
    jobs: List[Dict]
    total_found: int
    success: bool
    error_message: Optional[str] = None
    execution_time: float = 0.0
    cache_hit: bool = False


class UnifiedCrawlerInterface:
    """统一爬虫接口 - 简化版"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.crawler_config = self.config_manager.get_app_config('crawler', {})
        self.city_mapping = {
            # 支持多种城市格式
            "shanghai": {"name": "上海", "code": "101020100"},
            "beijing": {"name": "北京", "code": "101010100"}, 
            "shenzhen": {"name": "深圳", "code": "101280600"},
            "hangzhou": {"name": "杭州", "code": "101210100"}
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
                use_cache=params.get("use_cache", True)
            )
        else:
            search_params = params
            search_params.city = self.normalize_city(search_params.city)
        
        # 参数验证
        if not search_params.keyword.strip():
            return SearchResult(
                jobs=[],
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
                total_found=0,
                success=False,
                error_message=str(e),
                execution_time=time.time() - start_time
            )
    
    async def _execute_search(self, params: SearchParams) -> SearchResult:
        """执行具体搜索逻辑 - 使用统一爬虫引擎"""
        return await self._search_with_unified_spider(params)
    
    async def _search_with_unified_spider(self, params: SearchParams) -> SearchResult:
        """使用Real Playwright Spider搜索"""
        try:
            from .real_playwright_spider import RealPlaywrightBossSpider
            
            # 创建爬虫实例
            spider = RealPlaywrightBossSpider(headless=False)  # 使用有头模式
            
            try:
                # 启动爬虫
                await spider.start()
                
                # 执行搜索
                jobs = await spider.search_jobs(
                    keyword=params.keyword,
                    city=params.city,
                    max_jobs=params.max_jobs
                )
                
                # 添加引擎标识
                for job in jobs:
                    job['engine_source'] = 'Real Playwright Spider'
                
                return SearchResult(
                    jobs=jobs,
                    total_found=len(jobs),
                    success=True,
                    cache_hit=False
                )
                
            finally:
                # 关闭爬虫
                await spider.close()
                
        except Exception as e:
            raise Exception(f"Real Playwright Spider搜索失败: {e}")
    
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
        """获取支持的引擎列表 - 已简化为单一引擎"""
        return ["unified_spider"]
    
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
    
    def recommend_engine(self, requirements: Dict[str, Any]) -> str:
        """
        根据需求推荐最佳引擎 - 现在只有一个统一引擎
        
        Args:
            requirements: 需求字典（保留以便向后兼容）
            
        Returns:
            推荐的引擎
        """
        logger.info("使用统一爬虫引擎")
        return "unified_spider"


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
    **kwargs
) -> List[Dict]:
    """
    统一搜索接口（便捷函数）
    
    Args:
        keyword: 搜索关键词
        city: 城市
        max_jobs: 最大岗位数
        **kwargs: 其他参数
        
    Returns:
        岗位列表
    """
    crawler = get_unified_crawler()
    
    params = SearchParams(
        keyword=keyword,
        city=city,
        max_jobs=max_jobs,
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
            "error_recovery": True,
            "session_management": True
        },
        "version": "3.0-simplified"
    }