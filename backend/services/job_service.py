"""
岗位搜索和分析服务
"""

import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable

from crawler.boss_spider import BossSpider
from analyzer.job_analyzer import JobAnalyzer
from config.config_manager import ConfigManager


logger = logging.getLogger(__name__)


class JobSearchService:
    """岗位搜索服务"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.current_task: Optional[Dict] = None
        self.current_spider: Optional[BossSpider] = None
        self.progress_callback: Optional[Callable] = None
    
    def set_progress_callback(self, callback: Callable):
        """设置进度回调函数"""
        self.progress_callback = callback
    
    def emit_progress(self, message: str, progress: Optional[int] = None, data: Optional[Dict] = None):
        """发送进度更新"""
        if self.progress_callback:
            self.progress_callback(message, progress, data)
        logger.info(f"Progress: {message}")
    
    def start_search_task(self, params: Dict = None) -> Dict:
        """启动搜索任务"""
        if self.current_task and self.current_task.get('status') == 'running':
            raise Exception('已有任务正在运行中')
        
        # 初始化任务状态
        self.current_task = {
            'status': 'starting',
            'start_time': datetime.now(),
            'params': params or {}
        }
        
        # 在新线程中执行搜索任务
        thread = threading.Thread(target=self._run_search_task, args=(params or {},))
        thread.daemon = True
        thread.start()
        
        return {
            'message': '任务已启动',
            'task_id': 'default'
        }
    
    def _run_search_task(self, params: Dict):
        """执行搜索任务的主逻辑"""
        try:
            self.current_task['status'] = 'running'
            self.emit_progress("🚀 开始初始化爬虫...", 5)
            
            # 1. 初始化爬虫
            self.current_spider = BossSpider()
            if not self.current_spider.start():
                raise Exception("爬虫启动失败")
            
            self.emit_progress("🔐 等待用户登录...", 10)
            
            # 2. 登录处理
            if not self.current_spider.login_with_manual_help():
                raise Exception("登录失败")
            
            self.emit_progress("✅ 登录成功，开始搜索岗位...", 20)
            
            # 3. 获取配置
            search_config = self.config_manager.get_search_config()
            ai_config = self.config_manager.get_ai_config()
            
            # 获取城市代码
            city_code = self._get_city_code(search_config)
            
            self.emit_progress(f"🔍 搜索岗位: {search_config['keyword']}", 30)
            
            # 4. 搜索岗位
            jobs = self.current_spider.search_jobs(
                search_config['keyword'], 
                city_code, 
                search_config['max_jobs'],
                search_config['fetch_details']
            )
            
            if not jobs:
                raise Exception("未找到任何岗位")
            
            self.emit_progress(f"📊 找到 {len(jobs)} 个岗位，开始AI分析...", 50)
            
            # 5. AI分析
            analyzed_jobs = self._analyze_jobs(jobs, search_config, ai_config)
            
            # 6. 过滤和排序
            self.emit_progress("🎯 过滤和排序结果...", 85)
            filtered_jobs = self._filter_and_sort_jobs(analyzed_jobs, ai_config)
            
            # 7. 保存结果
            self.emit_progress("💾 保存结果...", 95)
            self._save_results(filtered_jobs)
            
            # 8. 完成
            self._complete_task(jobs, analyzed_jobs, filtered_jobs)
            
        except Exception as e:
            self._handle_task_error(e)
        finally:
            self._cleanup_resources()
    
    def _get_city_code(self, search_config: Dict) -> str:
        """获取城市代码"""
        selected_cities = search_config['cities']
        city_codes = search_config['city_codes']
        
        if not selected_cities:
            raise Exception("未选择任何城市")
        
        first_city = selected_cities[0]
        return city_codes.get(first_city, {}).get('code', '101210100')
    
    def _analyze_jobs(self, jobs: List[Dict], search_config: Dict, ai_config: Dict) -> List[Dict]:
        """分析岗位"""
        analyzer = JobAnalyzer(ai_config['provider'])
        jobs_to_analyze = jobs[:search_config['max_analyze_jobs']]
        analyzed_jobs = []
        
        for i, job in enumerate(jobs_to_analyze):
            progress = 50 + (i / len(jobs_to_analyze)) * 30
            self.emit_progress(f"🤖 分析第 {i+1}/{len(jobs_to_analyze)} 个岗位...", progress)
            
            try:
                analysis_result = analyzer.ai_client.analyze_job_match(
                    job, analyzer.user_requirements
                )
                job['analysis'] = analysis_result
                analyzed_jobs.append(job)
            except Exception as e:
                logger.error(f"分析岗位失败: {e}")
                job['analysis'] = {
                    "score": 0,
                    "recommendation": "分析失败",
                    "reason": f"分析过程中出错: {e}",
                    "summary": "无法分析此岗位"
                }
                analyzed_jobs.append(job)
        
        return analyzed_jobs
    
    def _filter_and_sort_jobs(self, analyzed_jobs: List[Dict], ai_config: Dict) -> List[Dict]:
        """过滤和排序岗位"""
        analyzer = JobAnalyzer(ai_config['provider'])
        return analyzer.filter_and_sort_jobs(analyzed_jobs, ai_config['min_score'])
    
    def _save_results(self, filtered_jobs: List[Dict]):
        """保存结果"""
        try:
            # 这里可以调用保存函数
            # save_results_to_json(filtered_jobs)
            pass
        except Exception as e:
            logger.error(f"保存结果失败: {e}")
    
    def _complete_task(self, jobs: List[Dict], analyzed_jobs: List[Dict], filtered_jobs: List[Dict]):
        """完成任务"""
        self.current_task.update({
            'status': 'completed',
            'end_time': datetime.now(),
            'results': filtered_jobs,
            'total_jobs': len(jobs),
            'analyzed_jobs': len(analyzed_jobs),
            'qualified_jobs': len(filtered_jobs)
        })
        
        self.emit_progress(f"✅ 任务完成! 找到 {len(filtered_jobs)} 个合适岗位", 100, {
            'results': filtered_jobs,
            'stats': {
                'total': len(jobs),
                'analyzed': len(analyzed_jobs),
                'qualified': len(filtered_jobs)
            }
        })
    
    def _handle_task_error(self, error: Exception):
        """处理任务错误"""
        logger.error(f"搜索任务失败: {error}")
        self.current_task.update({
            'status': 'failed',
            'error': str(error),
            'end_time': datetime.now()
        })
        self.emit_progress(f"❌ 任务失败: {str(error)}", None)
    
    def _cleanup_resources(self):
        """清理资源"""
        if self.current_spider:
            try:
                self.current_spider.close()
            except Exception as e:
                logger.error(f"清理爬虫资源失败: {e}")
            self.current_spider = None
    
    def get_task_status(self) -> Dict:
        """获取任务状态"""
        if not self.current_task:
            return {'status': 'idle'}
        
        return {
            'status': self.current_task.get('status', 'idle'),
            'start_time': self.current_task.get('start_time'),
            'end_time': self.current_task.get('end_time'),
            'error': self.current_task.get('error')
        }
    
    def get_task_results(self) -> Dict:
        """获取任务结果"""
        if not self.current_task:
            raise Exception('没有可用的搜索结果')
        
        return {
            'status': self.current_task.get('status'),
            'results': self.current_task.get('results', []),
            'stats': {
                'total_jobs': self.current_task.get('total_jobs', 0),
                'analyzed_jobs': self.current_task.get('analyzed_jobs', 0),
                'qualified_jobs': self.current_task.get('qualified_jobs', 0)
            },
            'start_time': self.current_task.get('start_time'),
            'end_time': self.current_task.get('end_time')
        }
    
    def stop_task(self):
        """停止当前任务"""
        if self.current_task and self.current_task.get('status') == 'running':
            self.current_task['status'] = 'stopping'
            self._cleanup_resources()
            self.current_task.update({
                'status': 'stopped',
                'end_time': datetime.now()
            })
            self.emit_progress("⏹️ 任务已停止", None)