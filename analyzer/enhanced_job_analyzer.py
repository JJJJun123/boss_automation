#!/usr/bin/env python3
"""
增强版岗位分析器：两阶段同步流水线
1. 类型筛选（GLM-4.7-Flash 等廉价模型）：过滤明显不相关的岗位
2. 简历匹配（Claude/GPT 等主力模型）：1–10 分评分 + 亮点/差距/总结
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .ai_client_factory import AIClientFactory
from .job_analyzer import JobAnalyzer
from .prompts.extraction_prompts import ExtractionPrompts
from .prompts.job_analysis_prompts import JobAnalysisPrompts, RESUME_MATCH_PROMPT

logger = logging.getLogger(__name__)


class EnhancedJobAnalyzer:
    """增强版岗位分析器 - 两阶段混合模型分析（廉价筛选 + 主力匹配）"""
    
    def __init__(self, extraction_provider: str = "glm", 
                 analysis_provider: Optional[str] = None, 
                 model_name: Optional[str] = None,
                 screening_mode: bool = True,
                 extraction_model_name: Optional[str] = "glm-4.7-flash"):
        """
        初始化增强版分析器
        
        Args:
            extraction_provider: 信息提取阶段的AI提供商（默认GLM）
            analysis_provider: 分析阶段的AI提供商（默认从配置读取）
            model_name: 分析阶段的具体模型名称
            screening_mode: 是否启用快速筛选模式（默认True）
            extraction_model_name: 信息提取阶段的具体模型名称
        """
        # 创建AI服务实例
        self.extraction_service = AIClientFactory.create_client(extraction_provider, extraction_model_name)
        self.extraction_provider = extraction_provider  # 保存provider信息以便显示
        self.job_analyzer = JobAnalyzer(ai_provider=analysis_provider, model_name=model_name)
        self._screening_fallback_active = False
        self._screening_rule_fallback_active = False
        
        # 获取用户配置
        self.user_requirements = self._get_user_requirements()
        self.user_intentions = self._get_user_intentions()
        self.resume_analysis = None
        self.screening_mode = screening_mode
        
        logger.debug(f"🚀 增强版分析器初始化完成")
        logger.debug(f"🎯 筛选模式: {'启用' if screening_mode else '禁用'}")
        logger.debug(f"📋 筛选引擎: {self.extraction_provider.upper()}")
        logger.debug(f"🧠 分析引擎: {self.job_analyzer.ai_provider.upper()}")

    def _is_ai_quota_error(self, error: Exception) -> bool:
        """判断是否为各家 AI 配额/余额不足错误（GLM/Claude/GPT/DeepSeek 等）"""
        message = str(error).lower()
        patterns = [
            "429",
            "quota exceeded",
            "resource_exhausted",
            "余额不足",
            "无可用资源包",
            "code': '1113'",
            'code": "1113"',
            "limit: 0",
        ]
        return any(p in message for p in patterns)

    def _build_rule_screening_result(self, job: Dict[str, Any], keyword: str) -> str:
        """AI不可用时的规则筛选结果（不调用任何模型）"""
        title = (job.get("title") or "").lower()
        company = (job.get("company") or "").lower()
        desc = (job.get("job_description") or "").lower()
        text = f"{title} {company} {desc}"

        kw = (keyword or "").strip().lower()
        if not kw:
            return json.dumps({"relevant": True, "reason": "未提供关键词，规则筛选默认放行"}, ensure_ascii=False)

        tokens = [t for t in kw.replace("，", " ").replace(",", " ").replace("/", " ").split() if t]
        matched = kw in text or any(t in text for t in tokens)
        if not matched and len(kw) >= 4:
            matched = any(kw[i:i + 2] in text for i in range(len(kw) - 1))

        reason = "规则筛选命中关键词" if matched else "规则筛选未命中关键词"
        return json.dumps({"relevant": matched, "reason": reason}, ensure_ascii=False)

    def _build_no_ai_match_result(self) -> Dict[str, Any]:
        """AI不可用时返回透明占位结果（不伪造匹配）"""
        return {
            "score": 0,
            "match_highlights": [],
            "gaps": ["AI服务不可用（配额或余额不足），未完成匹配分析"],
            "summary": "AI匹配阶段未执行，请补充额度后重试",
        }
        
    def _get_user_requirements(self):
        """获取用户要求配置"""
        try:
            from config.config_manager import ConfigManager
            config_manager = ConfigManager()
            profile = config_manager.get_user_preference('personal_profile', {})
            
            job_intentions = profile.get('job_intentions', [])
            skills = profile.get('skills', [])
            salary_range = profile.get('salary_range', {})
            excluded_types = profile.get('excluded_job_types', [])
            experience_years = profile.get('experience_years', 0)
            
            requirements = f"""
求职意向：
{chr(10).join(f'- {intention}' for intention in job_intentions)}

背景要求：
- 工作经验: {experience_years}年
- 技能专长: {', '.join(skills)}

薪资期望：
- {salary_range.get('min', 15)}K-{salary_range.get('max', 35)}K/月

不接受的岗位类型：
{chr(10).join(f'- {excluded}' for excluded in excluded_types)}
"""
            return requirements
            
        except Exception:
            # 默认配置
            return """
求职意向：
- 市场风险管理相关岗位
- AI/人工智能相关岗位

背景要求：
- 有金融行业经验优先
- 熟悉风险管理、数据分析

薪资期望：
- 15K-35K/月
"""
    
    def _get_user_intentions(self):
        """获取用户求职意向（用于快速筛选）"""
        try:
            from config.config_manager import ConfigManager
            config_manager = ConfigManager()
            profile = config_manager.get_user_preference('personal_profile', {})
            
            job_intentions = profile.get('job_intentions', [])
            excluded_types = profile.get('excluded_job_types', [])
            
            intentions = "求职意向：\n"
            intentions += "\n".join(f"- {intention}" for intention in job_intentions)
            
            if excluded_types:
                intentions += "\n\n不接受的岗位：\n"
                intentions += "\n".join(f"- {excluded}" for excluded in excluded_types)
            
            return intentions
            
        except Exception:
            return "求职意向：\n- 市场风险管理相关岗位\n- AI/人工智能相关岗位\n- 金融科技相关岗位"
    
    def set_resume_analysis(self, resume_analysis: Dict[str, Any]):
        """设置简历分析结果"""
        self.resume_analysis = resume_analysis
        logger.debug(f"📝 简历分析结果已加载")
    
    def analyze_jobs(self, jobs_list: List[Dict[str, Any]], resume_text: str = "", keyword: str = "") -> List[Dict[str, Any]]:
        """
        两阶段流水线：GLM 类型筛选 → 主力模型简历匹配，按分数降序返回。

        Args:
            jobs_list: 岗位列表
            resume_text: 简历全文（直接传入，不做额外结构化）
            keyword: 搜索关键词（用于类型筛选）
        """
        self._search_keyword = keyword

        # 阶段1：GLM 类型过滤（判断岗位类型是否与搜索关键词相关，不比对简历）
        screened = []
        for i, job in enumerate(jobs_list, 1):
            if i % 10 == 0:
                logger.debug(f"   筛选进度: {i}/{len(jobs_list)}")
            response = self._call_ai_for_screening(job)
            result = self._parse_screening_result(response)
            if result.get("relevant", False):
                screened.append(job)

        logger.debug(f"✅ 筛选出 {len(screened)}/{len(jobs_list)} 个相关岗位")

        # 阶段2：主力模型简历匹配
        results = []
        for i, job in enumerate(screened, 1):
            if i % 10 == 0:
                logger.debug(f"   匹配进度: {i}/{len(screened)}")
            response = self._call_ai_for_matching(job, resume_text)
            match = self._parse_match_result(response)
            try:
                score = float(match.get("score", 0))
                match["score"] = int(score) if score.is_integer() else score
            except (TypeError, ValueError):
                match["score"] = 0
            results.append({**job, **match})

        return sorted(results, key=lambda x: x.get("score", 0), reverse=True)

    def _call_ai_for_screening(self, job: Dict[str, Any]) -> str:
        """调用 GLM 判断岗位类型与搜索关键词的相关性。可被测试 mock 替换。"""
        keyword = getattr(self, '_search_keyword', '')
        prompt = ExtractionPrompts.get_job_relevance_screening_prompt(job, keyword)
        
        if self._screening_rule_fallback_active:
            return self._build_rule_screening_result(job, keyword)

        if self._screening_fallback_active:
            try:
                return self.job_analyzer.ai_client.call_api_simple(prompt, max_tokens=200, temperature=0.1)
            except Exception as e:
                if self._is_ai_quota_error(e):
                    logger.warning(f"筛选阶段备用AI也不可用，切换规则筛选: {e}")
                    self._screening_rule_fallback_active = True
                    return self._build_rule_screening_result(job, keyword)
                raise

        try:
            return self.extraction_service.call_api_simple(prompt, max_tokens=200, temperature=0.1)
        except Exception as e:
            if self._is_ai_quota_error(e):
                logger.warning(f"筛选阶段主AI不可用，尝试备用AI: {e}")
                self._screening_fallback_active = True
                try:
                    return self.job_analyzer.ai_client.call_api_simple(prompt, max_tokens=200, temperature=0.1)
                except Exception as fallback_e:
                    if self._is_ai_quota_error(fallback_e):
                        logger.warning(f"筛选阶段主/备AI均不可用，切换规则筛选: {fallback_e}")
                        self._screening_rule_fallback_active = True
                        return self._build_rule_screening_result(job, keyword)
                    raise
            raise

    def _call_ai_for_matching(self, job: Dict[str, Any], resume_text: str) -> str:
        """调用主力模型进行简历×JD深度匹配。可被测试 mock 替换。"""
        requirements_text = job.get('job_requirements') or ''
        if not requirements_text.strip():
            requirements_text = job.get('job_description', '')
        prompt = RESUME_MATCH_PROMPT.format(
            resume_text=resume_text[:2000] if resume_text else "（未提供简历）",
            job_title=job.get('title', ''),
            company=job.get('company', ''),
            salary=job.get('salary', '未提供'),
            description=job.get('job_description', '')[:800],
            requirements=requirements_text[:800],
        )
        try:
            return self.job_analyzer.ai_client.call_api_simple(prompt)
        except Exception as e:
            if self._is_ai_quota_error(e):
                logger.warning(f"匹配阶段AI不可用（配额/余额），返回未分析结果: {e}")
                return json.dumps(self._build_no_ai_match_result(), ensure_ascii=False)
            raise

    def _parse_match_result(self, response_text: str) -> Dict[str, Any]:
        """解析主力模型返回的匹配结果 JSON。"""
        import re
        try:
            m = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if m:
                return json.loads(m.group(1))
            m = re.search(r'\{.*\}', response_text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            logger.error(f"解析匹配结果失败: {e}")
        return {"score": 0, "match_highlights": [], "gaps": [], "summary": "解析失败"}
    
    def filter_and_sort_jobs(self, analyzed_jobs: List[Dict[str, Any]], min_score: int = 6) -> List[Dict[str, Any]]:
        """过滤和排序岗位"""
        def get_score(job):
            analysis = job.get('analysis', {})
            # 优先使用overall_score，其次使用score
            return analysis.get('overall_score', analysis.get('score', 0))
        
        # 过滤低分岗位
        filtered_jobs = [
            job for job in analyzed_jobs 
            if get_score(job) >= min_score
        ]
        
        # 按分数排序
        sorted_jobs = sorted(
            filtered_jobs, 
            key=get_score, 
            reverse=True
        )
        
        logger.debug(f"🎯 筛选结果: {len(sorted_jobs)}/{len(analyzed_jobs)} 个岗位达到标准({min_score}分)")
        return sorted_jobs
    
    def _parse_screening_result(self, response_text: str) -> Dict[str, Any]:
        """解析筛选结果"""
        try:
            import re
            
            # 尝试提取JSON
            json_match = re.search(r'\{.*?\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            # 如果解析失败，默认为不相关
            return {"relevant": False, "reason": "解析失败"}
            
        except Exception as e:
            logger.error(f"解析筛选结果失败: {e}")
            return {"relevant": False, "reason": "解析异常"}
