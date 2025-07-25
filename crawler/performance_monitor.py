#!/usr/bin/env python3
"""
性能监控器
提供实时性能分析、瓶颈检测和优化建议
"""

import logging
import time
import asyncio

# 可选依赖
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("psutil未安装，部分性能监控功能将被禁用")
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """性能指标"""
    timestamp: float
    metric_name: str
    value: float
    unit: str
    category: str = "general"
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class SystemSnapshot:
    """系统快照"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    active_threads: int
    open_files: int


@dataclass 
class CrawlerPerformance:
    """爬虫性能数据"""
    task_id: str
    keyword: str
    city: str
    start_time: float
    end_time: float
    total_jobs: int
    success_rate: float
    avg_page_load_time: float
    avg_extraction_time: float
    cache_hit_rate: float
    retry_count: int
    error_types: Dict[str, int]
    bottlenecks: List[str]


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, history_size: int = 1000):
        self.history_size = history_size
        self.metrics_history: deque = deque(maxlen=history_size)
        self.system_snapshots: deque = deque(maxlen=100)
        self.crawler_performances: deque = deque(maxlen=200)
        
        # 实时统计
        self.current_metrics: Dict[str, PerformanceMetric] = {}
        self.alert_thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'page_load_time': 15.0,
            'extraction_time': 30.0,
            'error_rate': 0.3,
            'cache_miss_rate': 0.7
        }
        
        # 性能分析器
        self.bottleneck_detector = BottleneckDetector()
        self.trend_analyzer = TrendAnalyzer()
        
        # 监控状态
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # 统计数据
        self.stats = {
            'total_monitored_tasks': 0,
            'avg_task_duration': 0.0,
            'peak_cpu_usage': 0.0,
            'peak_memory_usage': 0.0,
            'total_alerts': 0,
            'performance_score': 100.0
        }
    
    async def start_monitoring(self, interval: float = 5.0):
        """开始性能监控"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop(interval))
        logger.info(f"📊 性能监控已启动 (间隔: {interval}s)")
    
    async def stop_monitoring(self):
        """停止性能监控"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("📊 性能监控已停止")
    
    async def _monitor_loop(self, interval: float):
        """监控循环"""
        while self.is_monitoring:
            try:
                # 收集系统指标
                await self._collect_system_metrics()
                
                # 分析性能趋势
                await self._analyze_performance_trends()
                
                # 检测性能问题
                await self._detect_performance_issues()
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"❌ 性能监控出错: {e}")
                await asyncio.sleep(interval)
    
    async def _collect_system_metrics(self):
        """收集系统指标"""
        if not PSUTIL_AVAILABLE:
            # 如果psutil不可用，使用模拟数据
            snapshot = SystemSnapshot(
                timestamp=time.time(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                disk_io_read_mb=0.0,
                disk_io_write_mb=0.0,
                network_sent_mb=0.0,
                network_recv_mb=0.0,
                active_threads=1,
                open_files=0
            )
            self.system_snapshots.append(snapshot)
            return
        
        try:
            # CPU和内存
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # 磁盘IO
            disk_io = psutil.disk_io_counters()
            disk_read_mb = disk_io.read_bytes / 1024 / 1024 if disk_io else 0
            disk_write_mb = disk_io.write_bytes / 1024 / 1024 if disk_io else 0
            
            # 网络IO
            network_io = psutil.net_io_counters()
            network_sent_mb = network_io.bytes_sent / 1024 / 1024 if network_io else 0
            network_recv_mb = network_io.bytes_recv / 1024 / 1024 if network_io else 0
            
            # 进程信息
            process = psutil.Process()
            active_threads = process.num_threads()
            open_files = len(process.open_files())
            
            # 创建系统快照
            snapshot = SystemSnapshot(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / 1024 / 1024,
                disk_io_read_mb=disk_read_mb,
                disk_io_write_mb=disk_write_mb,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb,
                active_threads=active_threads,
                open_files=open_files
            )
            
            self.system_snapshots.append(snapshot)
            
            # 更新统计
            self.stats['peak_cpu_usage'] = max(self.stats['peak_cpu_usage'], cpu_percent)
            self.stats['peak_memory_usage'] = max(self.stats['peak_memory_usage'], memory.percent)
            
            # 记录关键指标
            self._record_metric("cpu_percent", cpu_percent, "percent", "system")
            self._record_metric("memory_percent", memory.percent, "percent", "system")
            self._record_metric("active_threads", active_threads, "count", "system")
            
        except Exception as e:
            logger.debug(f"收集系统指标失败: {e}")
    
    def _record_metric(self, name: str, value: float, unit: str, category: str, details: Dict = None):
        """记录性能指标"""
        metric = PerformanceMetric(
            timestamp=time.time(),
            metric_name=name,
            value=value,
            unit=unit,
            category=category,
            details=details or {}
        )
        
        self.metrics_history.append(metric)
        self.current_metrics[name] = metric
    
    async def record_crawler_performance(self, performance: CrawlerPerformance):
        """记录爬虫性能数据"""
        self.crawler_performances.append(performance)
        self.stats['total_monitored_tasks'] += 1
        
        # 更新平均任务持续时间
        duration = performance.end_time - performance.start_time
        if self.stats['total_monitored_tasks'] == 1:
            self.stats['avg_task_duration'] = duration
        else:
            # 移动平均
            alpha = 0.1
            self.stats['avg_task_duration'] = (
                alpha * duration + (1 - alpha) * self.stats['avg_task_duration']
            )
        
        # 记录性能指标
        self._record_metric("task_duration", duration, "seconds", "crawler", {
            "task_id": performance.task_id,
            "keyword": performance.keyword,
            "city": performance.city
        })
        
        self._record_metric("success_rate", performance.success_rate, "percent", "crawler")
        self._record_metric("cache_hit_rate", performance.cache_hit_rate, "percent", "crawler")
        
        # 分析瓶颈
        bottlenecks = await self.bottleneck_detector.analyze_crawler_performance(performance)
        if bottlenecks:
            logger.warning(f"🚨 检测到性能瓶颈: {', '.join(bottlenecks)}")
    
    async def _analyze_performance_trends(self):
        """分析性能趋势"""
        if len(self.system_snapshots) < 5:
            return
        
        recent_snapshots = list(self.system_snapshots)[-5:]
        
        # CPU趋势分析
        cpu_values = [s.cpu_percent for s in recent_snapshots]
        cpu_trend = self.trend_analyzer.analyze_trend(cpu_values)
        
        if cpu_trend == "increasing" and cpu_values[-1] > 70:
            self._trigger_alert("cpu_high_trend", "CPU使用率持续上升")
        
        # 内存趋势分析
        memory_values = [s.memory_percent for s in recent_snapshots]
        memory_trend = self.trend_analyzer.analyze_trend(memory_values)
        
        if memory_trend == "increasing" and memory_values[-1] > 80:
            self._trigger_alert("memory_high_trend", "内存使用率持续上升")
    
    async def _detect_performance_issues(self):
        """检测性能问题"""
        if not self.current_metrics:
            return
        
        # 检查阈值
        for metric_name, threshold in self.alert_thresholds.items():
            if metric_name in self.current_metrics:
                current_value = self.current_metrics[metric_name].value
                
                if current_value > threshold:
                    self._trigger_alert(
                        f"{metric_name}_threshold",
                        f"{metric_name} 超过阈值: {current_value:.2f} > {threshold}"
                    )
        
        # 检查爬虫性能异常
        if len(self.crawler_performances) >= 3:
            recent_performances = list(self.crawler_performances)[-3:]
            
            # 检查成功率下降
            success_rates = [p.success_rate for p in recent_performances]
            if all(rate < 0.7 for rate in success_rates):
                self._trigger_alert("low_success_rate", "最近3次任务成功率都低于70%")
            
            # 检查响应时间异常
            load_times = [p.avg_page_load_time for p in recent_performances]
            avg_load_time = sum(load_times) / len(load_times)
            if avg_load_time > 20:
                self._trigger_alert("slow_page_load", f"平均页面加载时间过长: {avg_load_time:.2f}s")
    
    def _trigger_alert(self, alert_type: str, message: str):
        """触发性能警报"""
        self.stats['total_alerts'] += 1
        logger.warning(f"🚨 性能警报 [{alert_type}]: {message}")
        
        # 记录警报指标
        self._record_metric(f"alert_{alert_type}", 1, "count", "alert", {
            "message": message,
            "alert_type": alert_type
        })
    
    def get_current_performance(self) -> Dict[str, Any]:
        """获取当前性能状态"""
        latest_snapshot = self.system_snapshots[-1] if self.system_snapshots else None
        
        current_performance = {
            "timestamp": time.time(),
            "monitoring_active": self.is_monitoring,
            "system": {},
            "crawler": {},
            "alerts": [],
            "performance_score": self._calculate_performance_score()
        }
        
        if latest_snapshot:
            current_performance["system"] = {
                "cpu_percent": latest_snapshot.cpu_percent,
                "memory_percent": latest_snapshot.memory_percent,
                "memory_used_mb": latest_snapshot.memory_used_mb,
                "active_threads": latest_snapshot.active_threads,
                "open_files": latest_snapshot.open_files
            }
        
        # 爬虫性能统计
        if self.crawler_performances:
            recent_performances = list(self.crawler_performances)[-10:]
            current_performance["crawler"] = {
                "avg_success_rate": sum(p.success_rate for p in recent_performances) / len(recent_performances),
                "avg_page_load_time": sum(p.avg_page_load_time for p in recent_performances) / len(recent_performances),
                "avg_extraction_time": sum(p.avg_extraction_time for p in recent_performances) / len(recent_performances),
                "total_tasks": len(recent_performances)
            }
        
        # 最近的警报
        recent_alerts = [
            m for m in self.metrics_history 
            if m.category == "alert" and time.time() - m.timestamp < 300  # 最近5分钟
        ]
        current_performance["alerts"] = [
            {"type": m.details.get("alert_type"), "message": m.details.get("message"), "time": m.timestamp}
            for m in recent_alerts
        ]
        
        return current_performance
    
    def _calculate_performance_score(self) -> float:
        """计算综合性能评分 (0-100)"""
        score = 100.0
        
        # 系统资源使用扣分
        if self.system_snapshots:
            latest = self.system_snapshots[-1]
            
            if latest.cpu_percent > 80:
                score -= 20
            elif latest.cpu_percent > 60:
                score -= 10
            
            if latest.memory_percent > 85:
                score -= 20
            elif latest.memory_percent > 70:
                score -= 10
        
        # 爬虫性能扣分
        if self.crawler_performances:
            recent_performances = list(self.crawler_performances)[-5:]
            
            avg_success_rate = sum(p.success_rate for p in recent_performances) / len(recent_performances)
            if avg_success_rate < 0.5:
                score -= 30
            elif avg_success_rate < 0.7:
                score -= 15
            
            avg_load_time = sum(p.avg_page_load_time for p in recent_performances) / len(recent_performances)
            if avg_load_time > 20:
                score -= 15
            elif avg_load_time > 10:
                score -= 8
        
        # 警报扣分
        recent_alert_count = len([
            m for m in self.metrics_history 
            if m.category == "alert" and time.time() - m.timestamp < 600  # 最近10分钟
        ])
        score -= min(20, recent_alert_count * 2)
        
        return max(0.0, score)
    
    def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """生成性能报告"""
        cutoff_time = time.time() - hours * 3600
        
        # 筛选时间范围内的数据
        relevant_snapshots = [s for s in self.system_snapshots if s.timestamp > cutoff_time]
        relevant_performances = [p for p in self.crawler_performances if p.start_time > cutoff_time]
        relevant_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        
        report = {
            "report_period": f"最近{hours}小时",
            "generated_at": time.time(),
            "summary": {
                "total_tasks": len(relevant_performances),
                "avg_success_rate": 0.0,
                "avg_response_time": 0.0,
                "peak_cpu": 0.0,
                "peak_memory": 0.0,
                "total_alerts": len([m for m in relevant_metrics if m.category == "alert"])
            },
            "trends": {},
            "bottlenecks": [],
            "recommendations": []
        }
        
        if relevant_performances:
            report["summary"]["avg_success_rate"] = sum(p.success_rate for p in relevant_performances) / len(relevant_performances)
            report["summary"]["avg_response_time"] = sum(p.avg_page_load_time for p in relevant_performances) / len(relevant_performances)
        
        if relevant_snapshots:
            report["summary"]["peak_cpu"] = max(s.cpu_percent for s in relevant_snapshots)
            report["summary"]["peak_memory"] = max(s.memory_percent for s in relevant_snapshots)
        
        # 生成优化建议
        report["recommendations"] = self._generate_recommendations(report["summary"])
        
        return report
    
    def _generate_recommendations(self, summary: Dict[str, Any]) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # CPU优化建议
        if summary.get("peak_cpu", 0) > 80:
            recommendations.append("CPU使用率过高，建议减少并发任务数量或优化爬虫逻辑")
        
        # 内存优化建议
        if summary.get("peak_memory", 0) > 85:
            recommendations.append("内存使用率过高，建议增加内存清理逻辑或减少缓存大小")
        
        # 成功率优化建议
        if summary.get("avg_success_rate", 1.0) < 0.7:
            recommendations.append("任务成功率较低，建议检查网络连接、选择器配置或增加重试机制")
        
        # 响应时间优化建议
        if summary.get("avg_response_time", 0) > 15:
            recommendations.append("页面加载时间过长，建议优化网络配置或增加超时设置")
        
        # 警报建议
        if summary.get("total_alerts", 0) > 10:
            recommendations.append("警报数量较多，建议检查系统配置和爬虫稳定性")
        
        if not recommendations:
            recommendations.append("系统运行良好，无需特殊优化")
        
        return recommendations
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """获取详细统计信息"""
        return {
            "monitor_stats": self.stats.copy(),
            "system_snapshots_count": len(self.system_snapshots),
            "crawler_performances_count": len(self.crawler_performances),
            "metrics_history_count": len(self.metrics_history),
            "current_performance_score": self._calculate_performance_score(),
            "monitoring_active": self.is_monitoring
        }


class BottleneckDetector:
    """瓶颈检测器"""
    
    async def analyze_crawler_performance(self, performance: CrawlerPerformance) -> List[str]:
        """分析爬虫性能瓶颈"""
        bottlenecks = []
        
        # 页面加载瓶颈
        if performance.avg_page_load_time > 15:
            bottlenecks.append("页面加载缓慢")
        
        # 数据提取瓶颈
        if performance.avg_extraction_time > 10:
            bottlenecks.append("数据提取耗时")
        
        # 重试过多
        if performance.retry_count > 5:
            bottlenecks.append("重试次数过多")
        
        # 成功率低
        if performance.success_rate < 0.7:
            bottlenecks.append("成功率低")
        
        # 缓存命中率低
        if performance.cache_hit_rate < 0.3:
            bottlenecks.append("缓存效率低")
        
        return bottlenecks


class TrendAnalyzer:
    """趋势分析器"""
    
    def analyze_trend(self, values: List[float]) -> str:
        """分析趋势：increasing, decreasing, stable"""
        if len(values) < 3:
            return "stable"
        
        # 简单线性趋势分析
        diff_sum = sum(values[i+1] - values[i] for i in range(len(values)-1))
        
        if diff_sum > len(values) * 0.5:
            return "increasing"
        elif diff_sum < -len(values) * 0.5:
            return "decreasing"
        else:
            return "stable"