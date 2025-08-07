#!/usr/bin/env python3
"""
并发管理器
实现并发抓取、缓存机制和性能优化
"""

import asyncio
import logging
import time
import hashlib
import json
import os
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
from playwright.async_api import Browser, Page, BrowserContext

logger = logging.getLogger(__name__)


@dataclass
class CacheItem:
    """缓存项数据结构"""
    key: str
    data: Any
    timestamp: float
    expires_at: float
    access_count: int = 0
    last_access: float = 0.0
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() > self.expires_at
    
    def is_fresh(self, max_age: int = 3600) -> bool:
        """检查数据是否新鲜"""
        return time.time() - self.timestamp < max_age


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    keyword: str
    city: str
    max_jobs: int
    priority: int = 1
    created_at: float = 0.0
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[List[Dict]] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, cache_dir: str = None, max_size: int = 1000):
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(__file__), 'cache')
        self.max_size = max_size
        self.memory_cache: Dict[str, CacheItem] = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'disk_reads': 0,
            'disk_writes': 0
        }
        self.ensure_cache_dir()
    
    def ensure_cache_dir(self):
        """确保缓存目录存在"""
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _generate_cache_key(self, keyword: str, city: str, max_jobs: int) -> str:
        """生成缓存键"""
        key_data = f"{keyword}:{city}:{max_jobs}"
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()
    
    def _get_cache_file_path(self, cache_key: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    async def get(self, keyword: str, city: str, max_jobs: int, max_age: int = 3600) -> Optional[List[Dict]]:
        """
        获取缓存数据
        
        Args:
            keyword: 搜索关键词
            city: 城市
            max_jobs: 最大岗位数
            max_age: 最大缓存时间（秒）
            
        Returns:
            缓存的岗位数据，如果没有或过期则返回None
        """
        cache_key = self._generate_cache_key(keyword, city, max_jobs)
        
        # 首先检查内存缓存
        if cache_key in self.memory_cache:
            cache_item = self.memory_cache[cache_key]
            cache_item.access_count += 1
            cache_item.last_access = time.time()
            
            if not cache_item.is_expired() and cache_item.is_fresh(max_age):
                self.cache_stats['hits'] += 1
                logger.info(f"✅ 内存缓存命中: {keyword}@{city}")
                return cache_item.data
            else:
                # 过期数据，从内存中移除
                del self.memory_cache[cache_key]
        
        # 检查磁盘缓存
        cache_file = self._get_cache_file_path(cache_key)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                cache_item = CacheItem(
                    key=cache_key,
                    data=cache_data['data'],
                    timestamp=cache_data['timestamp'],
                    expires_at=cache_data['expires_at']
                )
                
                if not cache_item.is_expired() and cache_item.is_fresh(max_age):
                    # 将磁盘缓存加载到内存
                    self.memory_cache[cache_key] = cache_item
                    self.cache_stats['hits'] += 1
                    self.cache_stats['disk_reads'] += 1
                    logger.info(f"✅ 磁盘缓存命中: {keyword}@{city}")
                    return cache_item.data
                else:
                    # 过期文件，删除
                    os.remove(cache_file)
                    
            except Exception as e:
                logger.debug(f"读取缓存文件失败: {e}")
                try:
                    os.remove(cache_file)
                except:
                    pass
        
        self.cache_stats['misses'] += 1
        logger.debug(f"❌ 缓存未命中: {keyword}@{city}")
        return None
    
    async def set(self, keyword: str, city: str, max_jobs: int, data: List[Dict], ttl: int = 7200) -> bool:
        """
        设置缓存数据
        
        Args:
            keyword: 搜索关键词
            city: 城市
            max_jobs: 最大岗位数
            data: 要缓存的数据
            ttl: 生存时间（秒）
            
        Returns:
            是否成功设置缓存
        """
        if not data:
            return False
        
        cache_key = self._generate_cache_key(keyword, city, max_jobs)
        current_time = time.time()
        expires_at = current_time + ttl
        
        cache_item = CacheItem(
            key=cache_key,
            data=data,
            timestamp=current_time,
            expires_at=expires_at
        )
        
        try:
            # 设置内存缓存
            self.memory_cache[cache_key] = cache_item
            
            # 检查内存缓存大小，必要时清理
            if len(self.memory_cache) > self.max_size:
                await self._evict_memory_cache()
            
            # 保存到磁盘
            cache_file = self._get_cache_file_path(cache_key)
            cache_data = {
                'key': cache_key,
                'data': data,
                'timestamp': current_time,
                'expires_at': expires_at,
                'keyword': keyword,
                'city': city,
                'max_jobs': max_jobs
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            self.cache_stats['disk_writes'] += 1
            logger.info(f"💾 缓存已保存: {keyword}@{city} ({len(data)} 个岗位)")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存缓存失败: {e}")
            return False
    
    async def _evict_memory_cache(self):
        """清理内存缓存"""
        if len(self.memory_cache) <= self.max_size:
            return
        
        # 按最后访问时间排序，移除最旧的项目
        sorted_items = sorted(
            self.memory_cache.items(),
            key=lambda x: x[1].last_access or x[1].timestamp
        )
        
        # 移除25%的最旧项目
        evict_count = max(1, len(sorted_items) // 4)
        for i in range(evict_count):
            key = sorted_items[i][0]
            del self.memory_cache[key]
            self.cache_stats['evictions'] += 1
        
        logger.info(f"🧹 清理内存缓存: 移除 {evict_count} 个项目")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = self.cache_stats['hits'] / total_requests if total_requests > 0 else 0.0
        
        return {
            'memory_cache_size': len(self.memory_cache),
            'hit_rate': hit_rate,
            'total_requests': total_requests,
            **self.cache_stats
        }
    
    async def clear_expired_cache(self):
        """清理过期缓存"""
        # 清理内存缓存
        expired_keys = [
            key for key, item in self.memory_cache.items()
            if item.is_expired()
        ]
        for key in expired_keys:
            del self.memory_cache[key]
        
        # 清理磁盘缓存
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.cache_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                        
                        expires_at = cache_data.get('expires_at', 0)
                        if time.time() > expires_at:
                            os.remove(file_path)
                    except:
                        # 如果文件损坏，直接删除
                        try:
                            os.remove(file_path)
                        except:
                            pass
        
        if expired_keys:
            logger.info(f"🧹 清理过期缓存: {len(expired_keys)} 个项目")


class ConcurrentManager:
    """并发管理器"""
    
    def __init__(self, max_concurrent_tasks: int = 3, max_browsers: int = 2):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_browsers = max_browsers
        self.cache_manager = CacheManager()
        
        # 任务管理
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.active_tasks: Dict[str, TaskInfo] = {}
        self.completed_tasks: Dict[str, TaskInfo] = {}
        
        # 浏览器池
        self.browser_pool: List[Browser] = []
        self.browser_semaphore = asyncio.Semaphore(max_browsers)
        self.context_pool: List[BrowserContext] = []
        
        # 统计信息
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'cache_hits': 0,
            'concurrent_peak': 0,
            'avg_task_time': 0.0
        }
        
        # 工作线程
        self.worker_tasks: List[asyncio.Task] = []
        self.is_running = False
    
    async def start(self):
        """启动并发管理器"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info(f"🚀 启动并发管理器 (最大任务: {self.max_concurrent_tasks}, 最大浏览器: {self.max_browsers})")
        
        # 启动工作线程
        for i in range(self.max_concurrent_tasks):
            worker = asyncio.create_task(self._worker(f"worker-{i+1}"))
            self.worker_tasks.append(worker)
        
        # 启动缓存清理任务
        cache_cleaner = asyncio.create_task(self._cache_cleaner())
        self.worker_tasks.append(cache_cleaner)
    
    async def stop(self):
        """停止并发管理器"""
        if not self.is_running:
            return
        
        self.is_running = False
        logger.info("🛑 停止并发管理器...")
        
        # 停止工作线程
        for task in self.worker_tasks:
            task.cancel()
        
        # 等待所有任务完成
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        
        # 关闭浏览器池
        await self._cleanup_browser_pool()
        
        logger.info("✅ 并发管理器已停止")
    
    async def submit_task(self, keyword: str, city: str, max_jobs: int, priority: int = 1) -> str:
        """
        提交抓取任务
        
        Args:
            keyword: 搜索关键词
            city: 城市
            max_jobs: 最大岗位数
            priority: 优先级（数字越大优先级越高）
            
        Returns:
            任务ID
        """
        task_id = f"{keyword}_{city}_{max_jobs}_{int(time.time())}"
        
        task_info = TaskInfo(
            task_id=task_id,
            keyword=keyword,
            city=city,
            max_jobs=max_jobs,
            priority=priority
        )
        
        # 首先检查缓存
        cached_data = await self.cache_manager.get(keyword, city, max_jobs, max_age=3600)
        if cached_data:
            task_info.status = "completed"
            task_info.result = cached_data
            self.completed_tasks[task_id] = task_info
            self.stats['cache_hits'] += 1
            logger.info(f"✅ 任务 {task_id} 直接从缓存返回结果")
            return task_id
        
        # 添加到任务队列
        await self.task_queue.put(task_info)
        self.active_tasks[task_id] = task_info
        self.stats['total_tasks'] += 1
        
        logger.info(f"📝 已提交任务: {task_id} (优先级: {priority})")
        return task_id
    
    async def get_task_result(self, task_id: str, timeout: int = 300) -> Optional[List[Dict]]:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）
            
        Returns:
            任务结果数据
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 检查已完成任务
            if task_id in self.completed_tasks:
                task_info = self.completed_tasks[task_id]
                if task_info.status == "completed":
                    return task_info.result
                elif task_info.status == "failed":
                    logger.error(f"❌ 任务 {task_id} 执行失败: {task_info.error}")
                    return None
            
            await asyncio.sleep(1)
        
        logger.error(f"⏰ 任务 {task_id} 等待超时")
        return None
    
    async def _worker(self, worker_name: str):
        """工作线程"""
        logger.info(f"👷 工作线程 {worker_name} 已启动")
        
        while self.is_running:
            try:
                # 获取任务
                task_info = await asyncio.wait_for(self.task_queue.get(), timeout=5.0)
                
                # 更新统计
                current_active = len([t for t in self.active_tasks.values() if t.status == "running"])
                self.stats['concurrent_peak'] = max(self.stats['concurrent_peak'], current_active + 1)
                
                # 执行任务
                await self._execute_task(task_info, worker_name)
                
                # 标记任务完成
                self.task_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"❌ 工作线程 {worker_name} 出错: {e}")
                continue
        
        logger.info(f"👷 工作线程 {worker_name} 已停止")
    
    async def _execute_task(self, task_info: TaskInfo, worker_name: str):
        """执行单个任务"""
        task_info.status = "running"
        start_time = time.time()
        
        try:
            logger.info(f"🏃 {worker_name} 开始执行任务: {task_info.task_id}")
            
            # 获取浏览器实例
            async with self.browser_semaphore:
                browser, context = await self._get_browser_context()
                
                try:
                    # 导入爬虫类
                    from .real_playwright_spider import RealPlaywrightBossSpider
                    
                    # 创建爬虫实例，使用共享浏览器
                    spider = RealPlaywrightBossSpider(headless=True)
                    spider.browser = browser
                    spider.playwright = None  # 使用共享浏览器，不需要独立playwright实例
                    
                    # 创建新页面
                    spider.page = await context.new_page()
                    
                    # 执行搜索
                    results = await spider.search_jobs(
                        task_info.keyword,
                        task_info.city,
                        task_info.max_jobs
                    )
                    
                    # 关闭页面
                    await spider.page.close()
                    
                    if results:
                        # 保存到缓存
                        await self.cache_manager.set(
                            task_info.keyword,
                            task_info.city,
                            task_info.max_jobs,
                            results
                        )
                        
                        task_info.result = results
                        task_info.status = "completed"
                        self.stats['completed_tasks'] += 1
                        
                        execution_time = time.time() - start_time
                        self._update_avg_task_time(execution_time)
                        
                        logger.info(f"✅ {worker_name} 任务完成: {task_info.task_id} ({len(results)} 个岗位, {execution_time:.2f}s)")
                    else:
                        raise Exception("未找到任何岗位数据")
                
                finally:
                    # 返回浏览器上下文到池中
                    await self._return_browser_context(browser, context)
        
        except Exception as e:
            task_info.status = "failed"
            task_info.error = str(e)
            self.stats['failed_tasks'] += 1
            logger.error(f"❌ {worker_name} 任务失败: {task_info.task_id} - {e}")
        
        finally:
            # 移动到已完成任务
            if task_info.task_id in self.active_tasks:
                del self.active_tasks[task_info.task_id]
            self.completed_tasks[task_info.task_id] = task_info
    
    async def _get_browser_context(self) -> tuple[Browser, BrowserContext]:
        """获取浏览器上下文"""
        if not self.browser_pool:
            # 创建新浏览器
            from playwright.async_api import async_playwright
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            self.browser_pool.append(browser)
        
        browser = self.browser_pool[0]  # 简化版本，使用第一个浏览器
        
        # 创建新的上下文
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        return browser, context
    
    async def _return_browser_context(self, browser: Browser, context: BrowserContext):
        """返回浏览器上下文"""
        try:
            await context.close()
        except Exception as e:
            logger.debug(f"关闭浏览器上下文失败: {e}")
    
    async def _cleanup_browser_pool(self):
        """清理浏览器池"""
        for browser in self.browser_pool:
            try:
                await browser.close()
            except Exception as e:
                logger.debug(f"关闭浏览器失败: {e}")
        
        self.browser_pool.clear()
    
    async def _cache_cleaner(self):
        """缓存清理任务"""
        while self.is_running:
            try:
                await self.cache_manager.clear_expired_cache()
                await asyncio.sleep(3600)  # 每小时清理一次
            except Exception as e:
                logger.debug(f"缓存清理出错: {e}")
                await asyncio.sleep(300)  # 出错后5分钟重试
    
    def _update_avg_task_time(self, execution_time: float):
        """更新平均任务执行时间"""
        if self.stats['completed_tasks'] == 1:
            self.stats['avg_task_time'] = execution_time
        else:
            # 使用移动平均
            alpha = 0.1  # 平滑因子
            self.stats['avg_task_time'] = (
                alpha * execution_time + 
                (1 - alpha) * self.stats['avg_task_time']
            )
    
    def get_status(self) -> Dict[str, Any]:
        """获取管理器状态"""
        return {
            'is_running': self.is_running,
            'active_tasks': len(self.active_tasks),
            'queue_size': self.task_queue.qsize(),
            'completed_tasks': len(self.completed_tasks),
            'browser_pool_size': len(self.browser_pool),
            'cache_stats': self.cache_manager.get_cache_stats(),
            'performance_stats': self.stats.copy()
        }
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task_info = self.active_tasks.get(task_id) or self.completed_tasks.get(task_id)
        if task_info:
            result = asdict(task_info)
            # 不返回完整结果数据，只返回统计信息
            if result.get('result'):
                result['result_count'] = len(result['result'])
                result['result'] = None
            return result
        return None


# 全局单例
_concurrent_manager: Optional[ConcurrentManager] = None


async def get_concurrent_manager() -> ConcurrentManager:
    """获取全局并发管理器实例"""
    global _concurrent_manager
    if _concurrent_manager is None:
        _concurrent_manager = ConcurrentManager()
        await _concurrent_manager.start()
    return _concurrent_manager


async def concurrent_search_jobs(keyword: str, city: str = "shanghai", 
                                max_jobs: int = 20, priority: int = 1) -> List[Dict]:
    """
    并发搜索岗位（对外接口）
    
    Args:
        keyword: 搜索关键词
        city: 城市
        max_jobs: 最大岗位数
        priority: 优先级
        
    Returns:
        岗位数据列表
    """
    manager = await get_concurrent_manager()
    task_id = await manager.submit_task(keyword, city, max_jobs, priority)
    result = await manager.get_task_result(task_id)
    return result or []