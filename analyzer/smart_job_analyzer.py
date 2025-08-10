#!/usr/bin/env python3
"""
智能分层岗位分析器
实现批量处理和智能分层策略：
1. GLM批量提取（便宜）
2. DeepSeek批量打分（中等）
3. Claude深度分析TOP岗位（贵但精准）
"""

import os
import json
import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from .ai_client_factory import AIClientFactory

logger = logging.getLogger(__name__)


class SmartJobAnalyzer:
    """智能分层岗位分析器 - 成本优化版"""
    
    def __init__(self):
        """初始化智能分析器"""
        # 初始化不同层级的AI客户端
        try:
            self.glm_client = AIClientFactory.create_client("glm", "glm-4.5")
        except Exception as e:
            print(f"⚠️ GLM客户端初始化失败，使用DeepSeek作为后备: {e}")
            self.glm_client = AIClientFactory.create_client("deepseek", "deepseek-chat")
        
        self.deepseek_client = AIClientFactory.create_client("deepseek", "deepseek-chat")
        
        # Claude客户端（仅在需要时初始化）
        self._claude_client = None
        
        # 批处理配置
        self.batch_size = 10  # 每批处理10个岗位
        
        # 缓存管理
        self.cache_dir = Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 统计信息
        self.stats = {
            "total_jobs": 0,
            "extracted": 0,
            "scored": 0,
            "deep_analyzed": 0,
            "cache_hits": 0,
            "api_calls": 0,
            "estimated_cost": 0.0
        }
        
        print("🚀 智能分层分析器初始化完成")
        print("📊 批处理大小: 10个岗位/批")
        print("💰 预期成本: $0.65/100个岗位")
    
    @property
    def claude_client(self):
        """延迟初始化Claude客户端"""
        if self._claude_client is None:
            try:
                self._claude_client = AIClientFactory.create_client("claude", "claude-3-5-sonnet-20241022")
            except Exception as e:
                print(f"⚠️ Claude客户端初始化失败，使用DeepSeek作为后备: {e}")
                self._claude_client = self.deepseek_client  # 使用DeepSeek作为后备
        return self._claude_client
    
    def analyze_jobs_smart(self, jobs: List[Dict[str, Any]], resume: Optional[Dict] = None) -> Dict[str, Any]:
        """
        智能分析岗位列表
        
        Args:
            jobs: 岗位列表
            resume: 用户简历（可选）
            
        Returns:
            分析结果，包含所有岗位评分和TOP岗位深度分析
        """
        print(f"\n🎯 开始智能分析 {len(jobs)} 个岗位...")
        self.stats["total_jobs"] = len(jobs)
        
        # Step 1: 批量提取结构化信息
        print("\n📊 第一步：批量提取岗位信息（GLM）...")
        extracted_jobs = self._batch_extract(jobs)
        
        # Step 2: 批量打分筛选
        print("\n🔍 第二步：批量评分筛选（DeepSeek）...")
        scored_jobs = self._batch_score(extracted_jobs, resume)
        
        # Step 3: 选择TOP岗位
        print("\n🎯 第三步：选择TOP岗位...")
        top_jobs = self._select_top_jobs(scored_jobs, n=10)
        
        # Step 4: 深度分析TOP岗位
        print(f"\n💎 第四步：深度分析TOP {len(top_jobs)} 个岗位（Claude）...")
        detailed_analysis = self._deep_analyze(top_jobs, resume)
        
        # 生成分析报告
        report = self._generate_report(scored_jobs, detailed_analysis)
        
        # 打印统计信息
        self._print_stats()
        
        return report
    
    def _batch_extract(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量提取岗位信息"""
        extracted_jobs = []
        
        # 分批处理
        for i in range(0, len(jobs), self.batch_size):
            batch = jobs[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(jobs) + self.batch_size - 1) // self.batch_size
            
            print(f"  处理批次 {batch_num}/{total_batches}...")
            
            # 检查缓存
            batch_results = []
            jobs_to_process = []
            cache_indices = []
            
            for idx, job in enumerate(batch):
                job_id = self._generate_job_id(job)
                cached = self._get_cached_extraction(job_id)
                
                if cached:
                    batch_results.append(cached)
                    self.stats["cache_hits"] += 1
                else:
                    jobs_to_process.append(job)
                    cache_indices.append(idx)
            
            # 处理未缓存的岗位
            if jobs_to_process:
                try:
                    # 构建批量提取提示词
                    prompt = self._build_batch_extract_prompt(jobs_to_process)
                    
                    # 调用GLM批量提取
                    response = self.glm_client.call_api_simple(prompt, max_tokens=2000)
                    self.stats["api_calls"] += 1
                    self.stats["estimated_cost"] += 0.0005 * len(jobs_to_process)
                    
                    # 解析结果
                    extracted_batch = self._parse_batch_extraction(response, jobs_to_process)
                    
                    # 合并结果并缓存
                    result_idx = 0
                    for idx in range(len(batch)):
                        if idx in cache_indices:
                            job = batch[idx]
                            extracted = extracted_batch[result_idx] if result_idx < len(extracted_batch) else {}
                            job_id = self._generate_job_id(job)
                            
                            # 缓存提取结果
                            self._cache_extraction(job_id, extracted)
                            batch_results.insert(idx, extracted)
                            result_idx += 1
                            self.stats["extracted"] += 1
                    
                except Exception as e:
                    logger.error(f"批量提取失败: {e}")
                    # 降级到单个处理
                    for job in jobs_to_process:
                        extracted = self._extract_single(job)
                        batch_results.append(extracted)
            
            # 合并原始岗位信息和提取结果
            for job, extracted in zip(batch, batch_results):
                job_with_extraction = {**job, "extracted_info": extracted}
                extracted_jobs.append(job_with_extraction)
        
        return extracted_jobs
    
    def _batch_score(self, jobs: List[Dict[str, Any]], resume: Optional[Dict]) -> List[Dict[str, Any]]:
        """批量评分岗位"""
        scored_jobs = []
        
        # 准备简历摘要
        resume_summary = self._prepare_resume_summary(resume) if resume else None
        
        # 分批评分
        for i in range(0, len(jobs), self.batch_size):
            batch = jobs[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(jobs) + self.batch_size - 1) // self.batch_size
            
            print(f"  评分批次 {batch_num}/{total_batches}...")
            
            try:
                # 构建批量评分提示词
                prompt = self._build_batch_score_prompt(batch, resume_summary)
                
                # 调用DeepSeek批量评分
                response = self.deepseek_client.call_api_simple(prompt, max_tokens=1000)
                self.stats["api_calls"] += 1
                self.stats["estimated_cost"] += 0.001 * len(batch)
                
                # 解析评分结果
                scores = self._parse_batch_scores(response, batch)
                
                # 合并评分到岗位信息
                for job, score_info in zip(batch, scores):
                    job_with_score = {
                        **job,
                        "score": score_info.get("score", 0),
                        "match_reason": score_info.get("reason", ""),
                        "match_details": score_info
                    }
                    scored_jobs.append(job_with_score)
                    self.stats["scored"] += 1
                    
            except Exception as e:
                logger.error(f"批量评分失败: {e}")
                # 降级处理：给默认分数
                for job in batch:
                    job_with_score = {
                        **job,
                        "score": 5.0,
                        "match_reason": "评分服务暂时不可用",
                        "match_details": {}
                    }
                    scored_jobs.append(job_with_score)
        
        return scored_jobs
    
    def _select_top_jobs(self, jobs: List[Dict[str, Any]], n: int = 10) -> List[Dict[str, Any]]:
        """选择TOP N个岗位"""
        # 按评分排序
        sorted_jobs = sorted(jobs, key=lambda x: x.get("score", 0), reverse=True)
        
        # 选择TOP N
        top_jobs = sorted_jobs[:n]
        
        print(f"✅ 选出TOP {len(top_jobs)}个岗位")
        for i, job in enumerate(top_jobs[:5], 1):
            print(f"  {i}. {job['title'][:30]}... - {job.get('score', 0):.1f}分")
        
        if len(top_jobs) > 5:
            print(f"  ... 还有{len(top_jobs) - 5}个岗位")
        
        return top_jobs
    
    def _deep_analyze(self, jobs: List[Dict[str, Any]], resume: Optional[Dict]) -> List[Dict[str, Any]]:
        """深度分析TOP岗位"""
        detailed_results = []
        
        for i, job in enumerate(jobs, 1):
            print(f"  深度分析 {i}/{len(jobs)}: {job['title'][:30]}...")
            
            try:
                # 构建深度分析提示词
                prompt = self._build_deep_analysis_prompt(job, resume)
                
                # 调用Claude深度分析
                response = self.claude_client.call_api_simple(prompt, max_tokens=2000)
                self.stats["api_calls"] += 1
                self.stats["estimated_cost"] += 0.05
                self.stats["deep_analyzed"] += 1
                
                # 解析深度分析结果
                analysis = self._parse_deep_analysis(response)
                
                # 合并到岗位信息
                job_with_analysis = {
                    **job,
                    "deep_analysis": analysis
                }
                detailed_results.append(job_with_analysis)
                
            except Exception as e:
                logger.error(f"深度分析失败: {e}")
                # 使用基础分析作为降级方案
                job_with_analysis = {
                    **job,
                    "deep_analysis": {
                        "summary": "深度分析暂时不可用",
                        "match_score": job.get("score", 0),
                        "recommendations": []
                    }
                }
                detailed_results.append(job_with_analysis)
        
        return detailed_results
    
    # ========== 辅助方法 ==========
    
    def _generate_job_id(self, job: Dict[str, Any]) -> str:
        """生成岗位唯一ID"""
        if job.get('link'):
            return hashlib.md5(job['link'].encode()).hexdigest()[:16]
        
        key_content = f"{job.get('company','')}|{job.get('title','')}|{job.get('salary','')}"
        return hashlib.md5(key_content.encode()).hexdigest()[:16]
    
    def _get_cached_extraction(self, job_id: str) -> Optional[Dict]:
        """获取缓存的提取结果"""
        cache_file = self.cache_dir / "extracted" / f"{job_id}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 检查缓存有效期（30天）
                    if self._is_cache_valid(data, days=30):
                        return data.get("extracted_info", {})
            except Exception:
                pass
        
        return None
    
    def _cache_extraction(self, job_id: str, extracted: Dict):
        """缓存提取结果"""
        cache_file = self.cache_dir / "extracted" / f"{job_id}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            data = {
                "extracted_info": extracted,
                "timestamp": datetime.now().isoformat()
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"缓存失败: {e}")
    
    def _is_cache_valid(self, data: Dict, days: int) -> bool:
        """检查缓存是否有效"""
        if not data or 'timestamp' not in data:
            return False
        
        try:
            cache_time = datetime.fromisoformat(data['timestamp'])
            age = (datetime.now() - cache_time).days
            return age < days
        except Exception:
            return False
    
    def _build_batch_extract_prompt(self, jobs: List[Dict]) -> str:
        """构建批量提取提示词"""
        jobs_text = ""
        for i, job in enumerate(jobs, 1):
            jobs_text += f"\n岗位{i}:\n"
            jobs_text += f"标题: {job.get('title', '')}\n"
            jobs_text += f"公司: {job.get('company', '')}\n"
            jobs_text += f"薪资: {job.get('salary', '')}\n"
            jobs_text += f"描述: {job.get('job_description', '')[:500]}...\n"
            jobs_text += "-" * 40
        
        prompt = f"""
批量提取以下{len(jobs)}个岗位的关键信息。

对每个岗位，提取：
1. skills_required: 必需技能列表
2. experience_years: 经验要求（数字）
3. education: 学历要求
4. job_type: 岗位类型（技术/管理/运营/销售等）

岗位列表：
{jobs_text}

输出JSON数组格式：
[
  {{
    "job_index": 1,
    "skills_required": ["Python", "SQL"],
    "experience_years": 3,
    "education": "本科",
    "job_type": "技术"
  }},
  ...
]
"""
        return prompt
    
    def _build_batch_score_prompt(self, jobs: List[Dict], resume_summary: Optional[str]) -> str:
        """构建批量评分提示词"""
        jobs_text = ""
        for i, job in enumerate(jobs, 1):
            extracted = job.get("extracted_info", {})
            jobs_text += f"\n岗位{i}:\n"
            jobs_text += f"标题: {job.get('title', '')}\n"
            jobs_text += f"公司: {job.get('company', '')}\n"
            jobs_text += f"技能要求: {extracted.get('skills_required', [])}\n"
            jobs_text += f"经验要求: {extracted.get('experience_years', '')}年\n"
            jobs_text += "-" * 40
        
        if resume_summary:
            resume_text = f"\n用户简历摘要：\n{resume_summary}\n"
        else:
            resume_text = "\n用户背景：通用求职者（无特定简历）\n"
        
        prompt = f"""
评估以下岗位的匹配度（0-10分）。
{resume_text}

评分标准：
- 0-3分：基本不匹配
- 4-6分：部分匹配
- 7-10分：高度匹配

岗位列表：
{jobs_text}

输出JSON数组：
[
  {{"job_index": 1, "score": 8.5, "reason": "技能高度匹配，经验符合要求"}},
  {{"job_index": 2, "score": 5.0, "reason": "技能部分匹配，经验略有不足"}},
  ...
]
"""
        return prompt
    
    def _build_deep_analysis_prompt(self, job: Dict, resume: Optional[Dict]) -> str:
        """构建深度分析提示词"""
        job_info = f"""
岗位信息：
- 标题：{job.get('title', '')}
- 公司：{job.get('company', '')}
- 薪资：{job.get('salary', '')}
- 描述：{job.get('job_description', '')}
- 初步评分：{job.get('score', 0):.1f}分
- 评分理由：{job.get('match_reason', '')}
"""
        
        if resume:
            resume_info = f"\n用户简历：\n{json.dumps(resume, ensure_ascii=False, indent=2)}\n"
        else:
            resume_info = ""
        
        prompt = f"""
请对以下岗位进行深度分析：

{job_info}
{resume_info}

请提供：
1. 整体匹配度评估（详细说明）
2. 优势亮点（3-5个）
3. 潜在挑战（2-3个）
4. 面试准备建议（3-5条）
5. 薪资谈判策略
6. 是否推荐投递（强烈推荐/推荐/谨慎考虑/不推荐）

输出JSON格式。
"""
        return prompt
    
    def _parse_batch_extraction(self, response: str, jobs: List[Dict]) -> List[Dict]:
        """解析批量提取结果"""
        try:
            # 尝试解析JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            else:
                json_str = response
            
            results = json.loads(json_str)
            
            # 确保返回正确数量的结果
            extracted_list = []
            for i in range(len(jobs)):
                # 查找对应的结果
                found = False
                for result in results:
                    if result.get("job_index") == i + 1:
                        extracted_list.append(result)
                        found = True
                        break
                
                if not found:
                    # 结果缺失，抛出异常
                    raise ValueError(f"岗位{i+1}的提取结果缺失")
            
            return extracted_list
            
        except Exception as e:
            logger.error(f"解析批量提取结果失败: {e}")
            # 提取失败，抛出异常
            raise e
    
    def _parse_batch_scores(self, response: str, jobs: List[Dict]) -> List[Dict]:
        """解析批量评分结果"""
        try:
            # 尝试解析JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            else:
                json_str = response
            
            results = json.loads(json_str)
            
            # 确保返回正确数量的结果
            scores_list = []
            for i in range(len(jobs)):
                # 查找对应的结果
                found = False
                for result in results:
                    if result.get("job_index") == i + 1:
                        scores_list.append(result)
                        found = True
                        break
                
                if not found:
                    # 结果缺失，抛出异常
                    raise ValueError(f"岗位{i+1}的评分结果缺失")
            
            return scores_list
            
        except Exception as e:
            logger.error(f"解析批量评分结果失败: {e}")
            # 评分失败，抛出异常
            raise e
    
    def _parse_deep_analysis(self, response: str) -> Dict:
        """解析深度分析结果"""
        try:
            # 尝试解析JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            else:
                json_str = response
            
            return json.loads(json_str)
            
        except Exception as e:
            # 解析失败，抛出异常
            logger.error(f"深度分析结果解析失败: {e}")
            raise e
    
    def _get_default_extraction(self) -> Dict:
        """这个函数不应该被使用"""
        raise NotImplementedError("默认提取机制已被移除")
    
    def _extract_single(self, job: Dict) -> Dict:
        """单个岗位提取（降级方案）"""
        try:
            prompt = f"""
提取岗位关键信息：
标题：{job.get('title', '')}
描述：{job.get('job_description', '')[:500]}

输出JSON：
{{"skills_required": [], "experience_years": 0, "education": "", "job_type": ""}}
"""
            response = self.glm_client.call_api_simple(prompt, max_tokens=500)
            return json.loads(response)
        except Exception:
            return {"skills_required": [], "experience_years": 0}
    
    def _prepare_resume_summary(self, resume: Optional[Dict]) -> str:
        """准备简历摘要"""
        if not resume:
            return "通用求职者"
        
        summary = f"""
技能：{resume.get('skills', [])}
经验：{resume.get('experience_years', 0)}年
教育：{resume.get('education', '本科')}
期望薪资：{resume.get('expected_salary', '面议')}
"""
        return summary
    
    def _generate_report(self, scored_jobs: List[Dict], detailed_jobs: List[Dict]) -> Dict:
        """生成分析报告"""
        report = {
            "total_jobs": len(scored_jobs),
            "analysis_time": datetime.now().isoformat(),
            "all_jobs_with_scores": scored_jobs,
            "top_jobs_detailed": detailed_jobs,
            "statistics": {
                "average_score": sum(j.get("score", 0) for j in scored_jobs) / len(scored_jobs) if scored_jobs else 0,
                "high_match_count": sum(1 for j in scored_jobs if j.get("score", 0) >= 7),
                "medium_match_count": sum(1 for j in scored_jobs if 4 <= j.get("score", 0) < 7),
                "low_match_count": sum(1 for j in scored_jobs if j.get("score", 0) < 4),
            },
            "cost_analysis": {
                "total_api_calls": self.stats["api_calls"],
                "cache_hits": self.stats["cache_hits"],
                "estimated_cost": f"${self.stats['estimated_cost']:.2f}"
            }
        }
        
        return report
    
    def _print_stats(self):
        """打印统计信息"""
        print("\n" + "=" * 50)
        print("📊 分析统计")
        print("=" * 50)
        print(f"总岗位数: {self.stats['total_jobs']}")
        print(f"信息提取: {self.stats['extracted']}个")
        print(f"评分完成: {self.stats['scored']}个")
        print(f"深度分析: {self.stats['deep_analyzed']}个")
        print(f"缓存命中: {self.stats['cache_hits']}次")
        print(f"API调用: {self.stats['api_calls']}次")
        print(f"预估成本: ${self.stats['estimated_cost']:.2f}")
        print("=" * 50)