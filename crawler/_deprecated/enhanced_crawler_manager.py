#!/usr/bin/env python3
"""
增强爬虫管理器
统一管理所有爬虫优化组件，提供高级接口
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import asdict
from .concurrent_manager import ConcurrentManager, get_concurrent_manager
from .performance_monitor import PerformanceMonitor, CrawlerPerformance
from .real_playwright_spider import RealPlaywrightBossSpider
from config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class EnhancedCrawlerManager:
    """增强爬虫管理器 - 统一管理接口"""
    
    def __init__(self):
        self.concurrent_manager: Optional[ConcurrentManager] = None
        self.performance_monitor = PerformanceMonitor()
        self.is_initialized = False
        
        # 获取配置
        self.config_manager = ConfigManager()
        self.crawler_config = self.config_manager.get_app_config('crawler')
        self.browser_config = self.crawler_config.get('browser', {})
        
        # 管理器配置
        self.config = {
            "max_concurrent_tasks": 3,
            "max_browsers": 2,
            "cache_enabled": True,
            "performance_monitoring": True,
            "auto_optimization": True
        }
        
        # 回调函数
        self.callbacks = {
            "on_task_start": [],
            "on_task_complete": [],
            "on_task_error": [],
            "on_performance_alert": []
        }
        
        # 运行统计
        self.runtime_stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "cached_results": 0,
            "avg_response_time": 0.0,
            "uptime_start": time.time()
        }
    
    async def initialize(self, config: Dict[str, Any] = None):
        """初始化管理器"""
        if self.is_initialized:
            return
        
        # 更新配置
        if config:
            self.config.update(config)
        
        logger.info("🚀 初始化增强爬虫管理器...")
        
        # 初始化并发管理器
        self.concurrent_manager = ConcurrentManager(
            max_concurrent_tasks=self.config["max_concurrent_tasks"],
            max_browsers=self.config["max_browsers"]
        )
        await self.concurrent_manager.start()
        
        # 启动性能监控
        if self.config["performance_monitoring"]:
            await self.performance_monitor.start_monitoring()
        
        self.is_initialized = True
        logger.info("✅ 增强爬虫管理器初始化完成")
    
    async def shutdown(self):
        """关闭管理器"""
        if not self.is_initialized:
            return
        
        logger.info("🛑 关闭增强爬虫管理器...")
        
        # 关闭并发管理器
        if self.concurrent_manager:
            await self.concurrent_manager.stop()
        
        # 停止性能监控
        await self.performance_monitor.stop_monitoring()
        
        self.is_initialized = False
        logger.info("✅ 增强爬虫管理器已关闭")
    
    async def search_jobs_enhanced(
        self,
        keyword: str,
        city: str = "shanghai",
        max_jobs: int = 20,
        priority: int = 1,
        use_cache: bool = None,
        callback: Callable = None
    ) -> List[Dict]:
        """
        增强岗位搜索接口
        
        Args:
            keyword: 搜索关键词
            city: 城市
            max_jobs: 最大岗位数
            priority: 优先级
            use_cache: 是否使用缓存
            callback: 进度回调函数
            
        Returns:
            岗位数据列表
        """
        if not self.is_initialized:
            await self.initialize()
        
        search_start_time = time.time()
        
        try:
            # 触发开始回调
            await self._trigger_callbacks("on_task_start", {
                "keyword": keyword,
                "city": city,
                "max_jobs": max_jobs,
                "start_time": search_start_time
            })
            
            # 更新统计
            self.runtime_stats["total_searches"] += 1
            
            # 检查是否使用缓存
            if use_cache is None:
                use_cache = self.config["cache_enabled"]
            
            if use_cache:
                # 使用并发管理器（包含缓存）
                results = await self._search_with_concurrent_manager(
                    keyword, city, max_jobs, priority, callback
                )
            else:
                # 直接使用爬虫（不使用缓存）
                results = await self._search_direct(
                    keyword, city, max_jobs, callback
                )
            
            # 计算性能指标
            search_duration = time.time() - search_start_time
            success = len(results) > 0
            
            if success:
                self.runtime_stats["successful_searches"] += 1
            
            # 更新平均响应时间
            self._update_avg_response_time(search_duration)
            
            # 记录性能数据
            if self.config["performance_monitoring"]:
                await self._record_performance_data(
                    keyword, city, max_jobs, search_start_time, 
                    time.time(), results, success
                )
            
            # 触发完成回调
            await self._trigger_callbacks("on_task_complete", {
                "keyword": keyword,
                "city": city,
                "results_count": len(results),
                "duration": search_duration,
                "success": success
            })
            
            logger.info(f"🎯 搜索完成: {keyword}@{city} - {len(results)} 个岗位 ({search_duration:.2f}s)")
            return results
            
        except Exception as e:
            # 触发错误回调
            await self._trigger_callbacks("on_task_error", {
                "keyword": keyword,
                "city": city,
                "error": str(e),
                "duration": time.time() - search_start_time
            })
            
            logger.error(f"❌ 搜索失败: {keyword}@{city} - {e}")
            return []
    
    async def _search_with_concurrent_manager(
        self, keyword: str, city: str, max_jobs: int, 
        priority: int, callback: Callable
    ) -> List[Dict]:
        """使用并发管理器搜索"""
        from .concurrent_manager import concurrent_search_jobs
        
        if callback:
            callback("正在提交并发任务...")
        
        results = await concurrent_search_jobs(keyword, city, max_jobs, priority)
        
        if callback:
            callback(f"并发搜索完成，找到 {len(results)} 个岗位")
        
        return results
    
    async def _search_direct(
        self, keyword: str, city: str, max_jobs: int, callback: Callable
    ) -> List[Dict]:
        """直接搜索（不使用缓存）"""
        if callback:
            callback("启动直接搜索模式...")
        
        headless = self.browser_config.get('headless', False)
        spider = RealPlaywrightBossSpider(headless=headless)
        
        try:
            if callback:
                callback("正在启动浏览器...")
            
            await spider.start()
            
            if callback:
                callback("正在搜索岗位...")
            
            results = await spider.search_jobs(keyword, city, max_jobs)
            
            if callback:
                callback(f"搜索完成，找到 {len(results)} 个岗位")
            
            return results
            
        finally:
            await spider.close()
    
    async def _record_performance_data(
        self, keyword: str, city: str, max_jobs: int,
        start_time: float, end_time: float, results: List[Dict],
        success: bool
    ):
        """记录性能数据"""
        try:
            # 分析结果质量
            cache_hit = any(
                job.get("engine_source", "").find("缓存") != -1 
                for job in results
            )
            
            # 估算页面加载时间和提取时间（简化版）
            total_duration = end_time - start_time
            estimated_page_load = min(total_duration * 0.6, 10.0)
            estimated_extraction = min(total_duration * 0.4, 5.0)
            
            performance = CrawlerPerformance(
                task_id=f"{keyword}_{city}_{int(start_time)}",
                keyword=keyword,
                city=city,
                start_time=start_time,
                end_time=end_time,
                total_jobs=len(results),
                success_rate=1.0 if success else 0.0,
                avg_page_load_time=estimated_page_load,
                avg_extraction_time=estimated_extraction,
                cache_hit_rate=1.0 if cache_hit else 0.0,
                retry_count=0,  # 简化版，实际应该从爬虫获取
                error_types={},
                bottlenecks=[]
            )
            
            await self.performance_monitor.record_crawler_performance(performance)
            
        except Exception as e:
            logger.debug(f"记录性能数据失败: {e}")
    
    def _update_avg_response_time(self, duration: float):
        """更新平均响应时间"""
        if self.runtime_stats["successful_searches"] == 1:
            self.runtime_stats["avg_response_time"] = duration
        else:
            # 移动平均
            alpha = 0.1
            self.runtime_stats["avg_response_time"] = (
                alpha * duration + 
                (1 - alpha) * self.runtime_stats["avg_response_time"]
            )
    
    async def _trigger_callbacks(self, event_type: str, data: Dict[str, Any]):
        """触发回调函数"""
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.debug(f"回调函数执行失败: {e}")
    
    def add_callback(self, event_type: str, callback: Callable):
        """添加回调函数"""
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
        else:
            logger.warning(f"未知事件类型: {event_type}")
    
    def remove_callback(self, event_type: str, callback: Callable):
        """移除回调函数"""
        if event_type in self.callbacks and callback in self.callbacks[event_type]:
            self.callbacks[event_type].remove(callback)
    
    async def batch_search(
        self, search_tasks: List[Dict[str, Any]], 
        max_concurrent: int = None
    ) -> Dict[str, List[Dict]]:
        """
        批量搜索岗位
        
        Args:
            search_tasks: 搜索任务列表，每个任务包含keyword, city, max_jobs等参数
            max_concurrent: 最大并发数
            
        Returns:
            任务ID到结果的映射
        """
        if not self.is_initialized:
            await self.initialize()
        
        if max_concurrent is None:
            max_concurrent = self.config["max_concurrent_tasks"]
        
        semaphore = asyncio.Semaphore(max_concurrent)
        results = {}
        
        async def search_single(task_info: Dict[str, Any]) -> tuple[str, List[Dict]]:
            async with semaphore:
                task_id = f"{task_info.get('keyword')}_{task_info.get('city')}_{int(time.time())}"
                result = await self.search_jobs_enhanced(**task_info)
                return task_id, result
        
        logger.info(f"🚀 开始批量搜索: {len(search_tasks)} 个任务")
        
        # 并发执行所有搜索任务
        tasks = [search_single(task_info) for task_info in search_tasks]
        completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 整理结果
        for task_result in completed_tasks:
            if isinstance(task_result, Exception):
                logger.error(f"批量搜索任务失败: {task_result}")
                continue
            
            task_id, task_results = task_result
            results[task_id] = task_results
        
        successful_count = len([r for r in results.values() if r])
        logger.info(f"✅ 批量搜索完成: {successful_count}/{len(search_tasks)} 成功")
        
        return results
    
    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        status = {
            "initialized": self.is_initialized,
            "uptime": time.time() - self.runtime_stats["uptime_start"],
            "config": self.config.copy(),
            "runtime_stats": self.runtime_stats.copy()
        }
        
        if self.concurrent_manager:
            status["concurrent_manager"] = self.concurrent_manager.get_status()
        
        if self.performance_monitor:
            status["performance_monitor"] = self.performance_monitor.get_current_performance()
        
        return status
    
    async def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """获取性能报告"""
        if not self.performance_monitor:
            return {"error": "性能监控未启用"}
        
        return self.performance_monitor.get_performance_report(hours)
    
    async def optimize_system(self) -> Dict[str, Any]:
        """自动系统优化"""
        if not self.config["auto_optimization"]:
            return {"message": "自动优化已禁用"}
        
        optimization_actions = []
        
        # 获取当前性能状态
        current_performance = self.performance_monitor.get_current_performance()
        performance_score = current_performance.get("performance_score", 100)
        
        # 根据性能评分进行优化
        if performance_score < 70:
            # 性能较差，需要优化
            if current_performance.get("system", {}).get("cpu_percent", 0) > 80:
                # CPU使用率过高，减少并发任务
                old_concurrent = self.config["max_concurrent_tasks"]
                self.config["max_concurrent_tasks"] = max(1, old_concurrent - 1)
                optimization_actions.append(f"减少并发任务数: {old_concurrent} -> {self.config['max_concurrent_tasks']}")
            
            if current_performance.get("system", {}).get("memory_percent", 0) > 85:
                # 内存使用率过高，清理缓存
                if self.concurrent_manager:
                    await self.concurrent_manager.cache_manager.clear_expired_cache()
                    optimization_actions.append("清理过期缓存")
        
        elif performance_score > 90:
            # 性能良好，可以增加并发
            if self.config["max_concurrent_tasks"] < 5:
                old_concurrent = self.config["max_concurrent_tasks"]
                self.config["max_concurrent_tasks"] += 1
                optimization_actions.append(f"增加并发任务数: {old_concurrent} -> {self.config['max_concurrent_tasks']}")
        
        return {
            "performance_score": performance_score,
            "optimization_actions": optimization_actions,
            "optimized_config": self.config.copy()
        }
    
    def get_recommendations(self) -> List[str]:
        """获取优化建议"""
        recommendations = []
        
        # 基于运行统计的建议
        success_rate = (
            self.runtime_stats["successful_searches"] / 
            max(1, self.runtime_stats["total_searches"])
        )
        
        if success_rate < 0.8:
            recommendations.append("成功率较低，建议检查网络连接或增加重试机制")
        
        if self.runtime_stats["avg_response_time"] > 30:
            recommendations.append("平均响应时间较长，建议优化爬虫逻辑或增加并发数")
        
        # 基于性能监控的建议
        if self.performance_monitor:
            current_perf = self.performance_monitor.get_current_performance()
            if current_perf.get("performance_score", 100) < 80:
                recommendations.append("系统性能评分较低，建议运行自动优化")
        
        if not recommendations:
            recommendations.append("系统运行良好，暂无优化建议")
        
        return recommendations


# 全局管理器实例
_enhanced_crawler_manager: Optional[EnhancedCrawlerManager] = None


async def get_enhanced_crawler_manager() -> EnhancedCrawlerManager:
    """获取全局增强爬虫管理器实例"""
    global _enhanced_crawler_manager
    if _enhanced_crawler_manager is None:
        _enhanced_crawler_manager = EnhancedCrawlerManager()
        await _enhanced_crawler_manager.initialize()
    return _enhanced_crawler_manager


# 对外高级接口
async def enhanced_search_jobs(
    keyword: str, 
    city: str = "shanghai", 
    max_jobs: int = 20,
    **kwargs
) -> List[Dict]:
    """
    增强岗位搜索（高级接口）
    
    Args:
        keyword: 搜索关键词
        city: 城市
        max_jobs: 最大岗位数
        **kwargs: 其他参数
        
    Returns:
        岗位数据列表
    """
    manager = await get_enhanced_crawler_manager()
    return await manager.search_jobs_enhanced(keyword, city, max_jobs, **kwargs)


async def batch_enhanced_search(search_requests: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
    """
    批量增强搜索（高级接口）
    
    Args:
        search_requests: 搜索请求列表
        
    Returns:
        搜索结果映射
    """
    manager = await get_enhanced_crawler_manager()
    return await manager.batch_search(search_requests)


async def get_crawler_status() -> Dict[str, Any]:
    """获取爬虫系统状态"""
    manager = await get_enhanced_crawler_manager()
    return await manager.get_system_status()


async def optimize_crawler_system() -> Dict[str, Any]:
    """优化爬虫系统"""
    manager = await get_enhanced_crawler_manager()
    return await manager.optimize_system()