#!/usr/bin/env python3
"""
AI岗位要求总结引擎
基于设计文档中的AI成本控制策略，提供智能岗位要求分析和总结
"""

import logging
import time
import hashlib
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from .ai_client_factory import AIClientFactory

logger = logging.getLogger(__name__)


@dataclass
class JobRequirementSummary:
    """岗位要求总结数据结构"""
    core_responsibilities: List[str]  # 核心职责
    key_requirements: List[str]       # 关键要求
    technical_skills: List[str]       # 技术技能
    soft_skills: List[str]           # 软技能
    experience_level: str            # 经验要求
    education_requirement: str       # 学历要求
    industry_background: str         # 行业背景
    compensation_range: str          # 薪资范围
    company_stage: str              # 公司阶段
    growth_potential: str           # 成长潜力
    match_keywords: List[str]       # 匹配关键词
    summary_confidence: float       # 总结置信度 (0-1)


class JobRequirementSummarizer:
    """AI岗位要求总结引擎"""
    
    def __init__(self, ai_provider: str = "deepseek"):
        self.ai_provider = ai_provider
        self.ai_client = AIClientFactory.create_client(ai_provider)
        
        # 智能缓存系统（实现AI成本控制）
        self.cache_file = Path("data/job_requirements_cache.json")
        self.cache_data = self._load_cache()
        
        # 批量处理配置
        self.batch_size = 5  # 每批处理的岗位数量
        self.cache_hit_threshold = 0.85  # 缓存相似度阈值
        
        # 性能统计
        self.stats = {
            "total_processed": 0,
            "cache_hits": 0,
            "ai_calls": 0,
            "batch_calls": 0,
            "cost_savings": 0.0,
            "processing_time": 0.0
        }
    
    def _load_cache(self) -> Dict:
        """加载缓存数据"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    logger.info(f"📚 加载岗位要求缓存: {len(cache_data)} 条记录")
                    return cache_data
        except Exception as e:
            logger.warning(f"加载缓存失败: {e}")
        
        return {}
    
    def _save_cache(self) -> None:
        """保存缓存数据"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"💾 缓存已保存: {len(self.cache_data)} 条记录")
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
    
    def _generate_job_hash(self, job_description: str, job_requirements: str) -> str:
        """生成岗位内容哈希值"""
        content = f"{job_description}\n{job_requirements}".strip()
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _check_cache(self, job_hash: str) -> Optional[JobRequirementSummary]:
        """检查缓存中是否有相似的岗位要求总结"""
        if job_hash in self.cache_data:
            cached = self.cache_data[job_hash]
            self.stats["cache_hits"] += 1
            logger.debug(f"🎯 缓存命中: {job_hash[:8]}")
            
            # 更新缓存统计
            cached["cache_hits"] = cached.get("cache_hits", 0) + 1
            cached["last_accessed"] = time.time()
            
            return self._dict_to_summary(cached["summary"])
        
        return None
    
    def _dict_to_summary(self, data: Dict) -> JobRequirementSummary:
        """将字典转换为JobRequirementSummary对象"""
        return JobRequirementSummary(**data)
    
    def _summary_to_dict(self, summary: JobRequirementSummary) -> Dict:
        """将JobRequirementSummary对象转换为字典"""
        return {
            "core_responsibilities": summary.core_responsibilities,
            "key_requirements": summary.key_requirements,
            "technical_skills": summary.technical_skills,
            "soft_skills": summary.soft_skills,
            "experience_level": summary.experience_level,
            "education_requirement": summary.education_requirement,
            "industry_background": summary.industry_background,
            "compensation_range": summary.compensation_range,
            "company_stage": summary.company_stage,
            "growth_potential": summary.growth_potential,
            "match_keywords": summary.match_keywords,
            "summary_confidence": summary.summary_confidence
        }
    
    async def summarize_single_job(self, job_data: Dict) -> JobRequirementSummary:
        """总结单个岗位要求"""
        start_time = time.time()
        
        # 提取岗位描述和要求
        job_description = job_data.get('job_description', '')
        job_requirements = job_data.get('job_requirements', '')
        
        if not job_description and not job_requirements:
            # 使用标题和公司信息作为fallback
            job_description = f"职位: {job_data.get('title', '')}\n公司: {job_data.get('company', '')}"
        
        # 检查缓存
        job_hash = self._generate_job_hash(job_description, job_requirements)
        cached_summary = self._check_cache(job_hash)
        
        if cached_summary:
            processing_time = time.time() - start_time
            self.stats["processing_time"] += processing_time
            return cached_summary
        
        # AI分析岗位要求
        summary = await self._ai_analyze_job_requirements(
            job_data.get('title', ''),
            job_data.get('company', ''),
            job_description,
            job_requirements,
            job_data.get('salary', ''),
            job_data.get('work_location', '')
        )
        
        # 保存到缓存
        self._cache_summary(job_hash, summary)
        
        processing_time = time.time() - start_time
        self.stats["processing_time"] += processing_time
        self.stats["total_processed"] += 1
        self.stats["ai_calls"] += 1
        
        return summary
    
    async def summarize_batch_jobs(self, jobs: List[Dict]) -> List[JobRequirementSummary]:
        """批量总结岗位要求（AI成本优化）"""
        logger.info(f"🔄 开始批量分析 {len(jobs)} 个岗位要求...")
        
        summaries = []
        uncached_jobs = []
        cached_results = {}
        
        # 第一步：检查缓存，分离已缓存和未缓存的岗位
        for i, job in enumerate(jobs):
            job_description = job.get('job_description', '')
            job_requirements = job.get('job_requirements', '')
            job_hash = self._generate_job_hash(job_description, job_requirements)
            
            cached_summary = self._check_cache(job_hash)
            if cached_summary:
                cached_results[i] = cached_summary
            else:
                uncached_jobs.append((i, job))
        
        logger.info(f"📚 缓存命中: {len(cached_results)}/{len(jobs)} 个岗位")
        
        # 第二步：批量处理未缓存的岗位
        if uncached_jobs:
            logger.info(f"🧠 需要AI分析: {len(uncached_jobs)} 个岗位")
            
            # 分批处理以优化API调用
            for batch_start in range(0, len(uncached_jobs), self.batch_size):
                batch = uncached_jobs[batch_start:batch_start + self.batch_size]
                batch_summaries = await self._ai_batch_analyze_jobs(batch)
                
                for (original_index, job), summary in zip(batch, batch_summaries):
                    # 保存到缓存
                    job_description = job.get('job_description', '')
                    job_requirements = job.get('job_requirements', '')
                    job_hash = self._generate_job_hash(job_description, job_requirements)
                    self._cache_summary(job_hash, summary)
                    
                    cached_results[original_index] = summary
                
                self.stats["batch_calls"] += 1
                self.stats["ai_calls"] += len(batch)
        
        # 第三步：按原始顺序组装结果
        for i in range(len(jobs)):
            summaries.append(cached_results[i])
        
        self.stats["total_processed"] += len(jobs)
        
        # 计算成本节省
        cache_hit_rate = len(cached_results) / len(jobs) if jobs else 0
        self.stats["cost_savings"] = cache_hit_rate * 0.8  # 假设缓存节省80%成本
        
        logger.info(f"✅ 批量分析完成，缓存命中率: {cache_hit_rate:.1%}")
        
        return summaries
    
    async def _ai_analyze_job_requirements(self, title: str, company: str, 
                                          description: str, requirements: str,
                                          salary: str, location: str) -> JobRequirementSummary:
        """AI分析单个岗位要求"""
        
        prompt = f"""
请分析以下岗位的核心要求并生成结构化总结：

岗位信息：
- 职位：{title}
- 公司：{company}
- 薪资：{salary}
- 地点：{location}

职位描述：
{description}

任职要求：
{requirements}

请按以下JSON格式输出分析结果：
{{
    "core_responsibilities": ["核心职责1", "核心职责2", "..."],
    "key_requirements": ["关键要求1", "关键要求2", "..."],
    "technical_skills": ["技术技能1", "技术技能2", "..."],
    "soft_skills": ["软技能1", "软技能2", "..."],
    "experience_level": "工作经验要求（如：3-5年）",
    "education_requirement": "学历要求（如：本科以上）",
    "industry_background": "行业背景要求",
    "compensation_range": "薪资范围分析",
    "company_stage": "公司发展阶段",
    "growth_potential": "成长潜力评估",
    "match_keywords": ["匹配关键词1", "匹配关键词2", "..."],
    "summary_confidence": 0.85
}}

注意：
1. 提取最重要的3-5个核心职责
2. 识别硬性要求vs加分项
3. 区分技术技能和软技能
4. 评估岗位的成长潜力
5. summary_confidence表示分析的置信度(0-1)
"""
        
        try:
            response = await self.ai_client.analyze_async(prompt)
            
            # 解析JSON响应
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result_data = json.loads(json_str)
                return JobRequirementSummary(**result_data)
            else:
                raise ValueError("AI响应格式不正确，无法解析JSON")
                
        except Exception as e:
            logger.error(f"AI分析失败: {e}")
            raise e
    
    async def _ai_batch_analyze_jobs(self, job_batch: List[Tuple[int, Dict]]) -> List[JobRequirementSummary]:
        """AI批量分析岗位（成本优化策略）"""
        
        # 构建批量分析提示词
        job_texts = []
        for i, (_, job) in enumerate(job_batch):
            job_text = f"""
岗位 {i+1}:
- 职位：{job.get('title', '')}
- 公司：{job.get('company', '')}
- 描述：{job.get('job_description', '')[:500]}...
- 要求：{job.get('job_requirements', '')[:500]}...
"""
            job_texts.append(job_text)
        
        batch_prompt = f"""
请批量分析以下 {len(job_batch)} 个岗位的核心要求：

{chr(10).join(job_texts)}

请为每个岗位输出以下JSON格式的分析结果，用数组包含：
[
    {{
        "core_responsibilities": ["职责1", "职责2"],
        "key_requirements": ["要求1", "要求2"],
        "technical_skills": ["技能1", "技能2"],
        "soft_skills": ["软技能1", "软技能2"],
        "experience_level": "经验要求",
        "education_requirement": "学历要求",
        "industry_background": "行业背景",
        "compensation_range": "薪资分析",
        "company_stage": "公司阶段",
        "growth_potential": "成长潜力",
        "match_keywords": ["关键词1", "关键词2"],
        "summary_confidence": 0.8
    }},
    ...
]

注意：数组长度必须等于岗位数量({len(job_batch)})
"""
        
        try:
            response = await self.ai_client.analyze_async(batch_prompt)
            
            # 解析批量JSON响应
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                results_data = json.loads(json_str)
                
                summaries = []
                for i, result_data in enumerate(results_data):
                    if i < len(job_batch):
                        summaries.append(JobRequirementSummary(**result_data))
                
                # 如果结果数量不足，抛出异常
                if len(summaries) < len(job_batch):
                    raise ValueError(f"AI返回的结果数量不足: 期望{len(job_batch)}个，实际{len(summaries)}个")
                
                return summaries
            else:
                logger.warning("批量AI响应格式不正确，使用单独分析")
                # 降级到单独分析
                summaries = []
                for _, job in job_batch:
                    summary = await self._ai_analyze_job_requirements(
                        job.get('title', ''),
                        job.get('company', ''),
                        job.get('job_description', ''),
                        job.get('job_requirements', ''),
                        job.get('salary', ''),
                        job.get('work_location', '')
                    )
                    summaries.append(summary)
                return summaries
                
        except Exception as e:
            logger.error(f"批量AI分析失败: {e}")
            raise e
    
    def _create_fallback_summary(self, title: str, description: str, requirements: str) -> JobRequirementSummary:
        """这个函数不应该被使用，保留仅为向后兼容"""
        raise NotImplementedError("fallback机制已被移除，分析失败应直接报错")
    
    def _cache_summary(self, job_hash: str, summary: JobRequirementSummary) -> None:
        """缓存岗位要求总结"""
        self.cache_data[job_hash] = {
            "summary": self._summary_to_dict(summary),
            "created_time": time.time(),
            "cache_hits": 0,
            "last_accessed": time.time()
        }
        
        # 定期保存缓存
        if len(self.cache_data) % 10 == 0:
            self._save_cache()
    
    def get_cost_savings_report(self) -> Dict:
        """获取成本节省报告"""
        total_jobs = self.stats["total_processed"]
        cache_hits = self.stats["cache_hits"]
        ai_calls = self.stats["ai_calls"]
        
        if total_jobs > 0:
            cache_hit_rate = cache_hits / total_jobs
            estimated_cost_without_cache = total_jobs * 0.01  # 假设每次分析成本0.01元
            estimated_cost_with_cache = ai_calls * 0.01
            cost_savings = estimated_cost_without_cache - estimated_cost_with_cache
            
            return {
                "cache_statistics": {
                    "total_processed": total_jobs,
                    "cache_hits": cache_hits,
                    "cache_hit_rate": f"{cache_hit_rate:.1%}",
                    "ai_calls_made": ai_calls,
                    "ai_calls_saved": cache_hits
                },
                "cost_analysis": {
                    "estimated_cost_without_cache": f"¥{estimated_cost_without_cache:.2f}",
                    "actual_cost_with_cache": f"¥{estimated_cost_with_cache:.2f}",
                    "total_savings": f"¥{cost_savings:.2f}",
                    "savings_rate": f"{(cost_savings/estimated_cost_without_cache)*100:.1f}%" if estimated_cost_without_cache > 0 else "0%"
                },
                "performance_metrics": {
                    "batch_calls": self.stats["batch_calls"],
                    "avg_processing_time": f"{self.stats['processing_time']/total_jobs:.2f}s" if total_jobs > 0 else "0s",
                    "cache_size": len(self.cache_data)
                }
            }
        
        return {"message": "没有足够的数据生成报告"}
    
    def cleanup_old_cache(self, max_age_days: int = 30) -> int:
        """清理过期缓存"""
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 3600
        
        old_keys = []
        for key, data in self.cache_data.items():
            if current_time - data.get("last_accessed", 0) > max_age_seconds:
                old_keys.append(key)
        
        for key in old_keys:
            del self.cache_data[key]
        
        if old_keys:
            self._save_cache()
            logger.info(f"🧹 清理过期缓存: {len(old_keys)} 条记录")
        
        return len(old_keys)
    
    def __del__(self):
        """析构时保存缓存"""
        try:
            self._save_cache()
        except:
            pass