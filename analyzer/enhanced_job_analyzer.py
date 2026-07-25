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
from .machine_summary import normalize_machine_summary
from .prompts.extraction_prompts import ExtractionPrompts
from .prompts.job_analysis_prompts import JobAnalysisPrompts, RESUME_MATCH_PROMPT

logger = logging.getLogger(__name__)


class EnhancedJobAnalyzer:
    """增强版岗位分析器 - 两阶段混合模型分析（廉价筛选 + 主力匹配）"""
    
    def __init__(self, extraction_provider: str = "deepseek",
                 analysis_provider: Optional[str] = None,
                 model_name: Optional[str] = None,
                 screening_mode: bool = True,
                 extraction_model_name: Optional[str] = "deepseek-v4-flash",
                 api_key: Optional[str] = None):
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
        self.extraction_service = AIClientFactory.create_client(
            extraction_provider, extraction_model_name, api_key=api_key
        )
        self.extraction_provider = extraction_provider  # 保存provider信息以便显示
        self.job_analyzer = JobAnalyzer(
            ai_provider=analysis_provider, model_name=model_name, api_key=api_key
        )
        self._screening_fallback_active = False
        self._screening_rule_fallback_active = False
        self.discarded_jobs: List[Dict[str, str]] = []
        
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
    
    def analyze_jobs(self, jobs_list: List[Dict[str, Any]], resume_text: str = "",
                     keyword: str = "",
                     hard_filters: Optional[Dict[str, Any]] = None,
                     career_profile: Optional[Dict[str, Any]] = None
                     ) -> List[Dict[str, Any]]:
        """
        流水线：Hard filter（省 API 成本）→ AI 类型筛选 → 主力模型简历匹配，按分数降序返回。

        Args:
            jobs_list: 岗位列表
            resume_text: 简历全文（直接传入，不做额外结构化）
            keyword: 搜索关键词（用于类型筛选）
            hard_filters: F2 硬性过滤（薪资/年限/学历/排除标签），在 AI 前过滤省成本
            career_profile: 对话形成的求职画像；不传时完全沿用旧行为
        """
        # 分析器实例可能跨搜索复用；每次调用都只暴露本轮被过滤的岗位。
        self.discarded_jobs = []
        self._career_profile = career_profile if isinstance(
            career_profile, dict
        ) else None
        target_directions = (
            self._career_profile.get("target_directions", [])
            if self._career_profile else []
        )
        target_directions = [
            item.strip() for item in target_directions
            if isinstance(item, str) and item.strip()
        ]
        self._search_keyword = (
            " / ".join(target_directions) if target_directions else keyword
        )

        # 画像硬排除与请求显式 hard_filters 合并，但不修改调用方原字典。
        effective_hard_filters = dict(hard_filters or {})
        if self._career_profile:
            excludes = list(effective_hard_filters.get("exclude_keywords") or [])
            for item in self._career_profile.get("hard_avoids", []) or []:
                if isinstance(item, str) and item.strip() and item.strip() not in excludes:
                    excludes.append(item.strip())
            if excludes:
                effective_hard_filters["exclude_keywords"] = excludes

        # 阶段0：Hard filter（爬虫后、AI 前）——阶段 1.8。
        # 命中用户硬性排除条件的岗位直接剔除，不送昂贵 AI。
        if effective_hard_filters:
            from .hard_filter import apply_hard_filters
            before = len(jobs_list)
            jobs_list, dropped = apply_hard_filters(
                jobs_list, effective_hard_filters
            )
            self.discarded_jobs.extend({
                "title": item.get("title", ""),
                "company": item.get("company", ""),
                "stage": "hard_filter",
                "reason": item.get("reason") or "命中硬性过滤条件",
            } for item in dropped)
            logger.debug(f"🔪 Hard filter: {before} → {len(jobs_list)}（剔除 {len(dropped)} 个）")

        # 阶段1：GLM 类型过滤（判断岗位类型是否与搜索关键词相关，不比对简历）
        screened = []
        if not self.screening_mode:
            screened = list(jobs_list)
        else:
            for i, job in enumerate(jobs_list, 1):
                if i % 10 == 0:
                    logger.debug(f"   筛选进度: {i}/{len(jobs_list)}")
                response = self._call_ai_for_screening(job)
                result = self._parse_screening_result(response)
                if result.get("relevant", False):
                    screened.append(job)
                    continue

                raw_reason = result.get("reason") or "AI 判定岗位类型不相关"
                reason = (raw_reason if self._screening_rule_fallback_active
                          else f"类型不符：{raw_reason}")
                self.discarded_jobs.append({
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "stage": "screening",
                    "reason": reason,
                })

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
            machine_summary = normalize_machine_summary(match, job)
            results.append({**job, **match, **machine_summary})

        return sorted(results, key=lambda x: x.get("score", 0), reverse=True)

    def _call_ai_for_screening(self, job: Dict[str, Any]) -> str:
        """调用 GLM 判断岗位类型与搜索关键词的相关性。可被测试 mock 替换。"""
        keyword = getattr(self, '_search_keyword', '')
        prompt = ExtractionPrompts.get_job_relevance_screening_prompt(job, keyword)
        profile = getattr(self, "_career_profile", None)
        if profile:
            directions = [
                item for item in profile.get("target_directions", [])
                if isinstance(item, str) and item.strip()
            ]
            prompt += (
                "\n\n【求职画像 target_directions】\n- "
                + "\n- ".join(directions)
                + "\n判定标准：岗位与任一目标方向相关即可通过；"
                  "画像方向优先于本次单一搜索词。"
            )
        
        if self._screening_rule_fallback_active:
            return self._build_rule_screening_result(job, keyword)

        # Stage 1 是简单二分类，关闭 thinking 以省 token / 降延迟（DeepSeek 客户端识别该参数；其他 client 忽略）
        if self._screening_fallback_active:
            try:
                return self.job_analyzer.ai_client.call_api_simple(prompt, max_tokens=200, temperature=0.1, thinking=False)
            except Exception as e:
                if self._is_ai_quota_error(e):
                    logger.warning(f"筛选阶段备用AI也不可用，切换规则筛选: {e}")
                    self._screening_rule_fallback_active = True
                    return self._build_rule_screening_result(job, keyword)
                raise

        try:
            return self.extraction_service.call_api_simple(prompt, max_tokens=200, temperature=0.1, thinking=False)
        except Exception as e:
            if self._is_ai_quota_error(e):
                logger.warning(f"筛选阶段主AI不可用，尝试备用AI: {e}")
                self._screening_fallback_active = True
                try:
                    return self.job_analyzer.ai_client.call_api_simple(prompt, max_tokens=200, temperature=0.1, thinking=False)
                except Exception as fallback_e:
                    if self._is_ai_quota_error(fallback_e):
                        logger.warning(f"筛选阶段主/备AI均不可用，切换规则筛选: {fallback_e}")
                        self._screening_rule_fallback_active = True
                        return self._build_rule_screening_result(job, keyword)
                    raise
            raise

    def _analysis_max_tokens(self) -> int:
        """返回阶段二预算；推理模型留足 reasoning 与最终 JSON 空间。"""
        provider = (self.job_analyzer.ai_provider or "").strip().lower()
        if provider in {"claude", "gpt", "openai"}:  # openai 是 gpt 的工厂别名
            return 16000
        return 6000

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
        profile = getattr(self, "_career_profile", None)
        if profile:
            transition = profile.get("transition")
            profile_block = json.dumps(
                profile, ensure_ascii=False, sort_keys=True
            )
            prompt += (
                "\n\n【求职画像——评估标准，简历仅作为能力素材】\n"
                f"{profile_block}\n"
            )
            if (
                isinstance(transition, dict)
                and transition.get("is_transition") is True
                and transition.get("to")
            ):
                prompt += (
                    f"候选人明确希望从 {transition.get('from') or '当前方向'} "
                    f"转型到 {transition['to']}。评分锚必须切换为：这个岗位是否是"
                    f"通往 {transition['to']} 的好跳板，以及现有经历中有哪些技能可迁移；"
                    "不要只按简历与 JD 的静态重合度打分。\n"
                )
            else:
                prompt += (
                    "请以画像中的目标方向、城市、薪资与偏好为评估标准，"
                    "简历用于判断能力证据。\n"
                )
        # Stage 2 需要打分/判断，开启 thinking 让 DeepSeek 先做链式推理再输出 JSON。
        # Claude/GPT 推理模型使用 16000；DeepSeek 维持已调优的 6000，避免超过
        # 其输出上限。各客户端负责把兼容输入名 max_tokens 转成实际 API 参数。
        try:
            return self.job_analyzer.ai_client.call_api_simple(
                prompt,
                thinking=True,
                max_tokens=self._analysis_max_tokens(),
            )
        except Exception as e:
            if self._is_ai_quota_error(e):
                logger.warning(f"匹配阶段AI不可用（配额/余额），返回未分析结果: {e}")
                return json.dumps(self._build_no_ai_match_result(), ensure_ascii=False)
            raise

    def _parse_match_result(self, response_text: str) -> Dict[str, Any]:
        """解析主力模型返回的匹配结果 JSON

        解析路径：① ```json ...``` 代码块 → ② 裸 JSON 对象
        两者都失败时，记录 raw response 前缀到日志便于诊断（典型场景：thinking
        模式 token 截断、模型直接吐 reasoning 文本不给 JSON 等）。
        """
        import re
        try:
            m = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if m:
                return json.loads(m.group(1))
            m = re.search(r'\{.*\}', response_text, re.DOTALL)
            if m:
                return json.loads(m.group())
            # 没匹配到任何 JSON 块——通常是 thinking 截断或模型未按 prompt 输出 JSON
            logger.warning(
                f"匹配阶段未找到 JSON 块（可能 thinking 截断）；"
                f"raw 长度={len(response_text)}, 前200字={response_text[:200]!r}"
            )
        except Exception as e:
            logger.error(
                f"解析匹配结果失败: {e}; "
                f"raw 长度={len(response_text)}, 前200字={response_text[:200]!r}"
            )
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

            # 简单二分类模型常直接返回“是”或“否”；这种合法短答不应被当成
            # JSON 解析失败。若后面附了一句话，也保留下来供用户查看。
            plain = (response_text or "").strip()
            if plain.startswith("是"):
                reason = plain[1:].lstrip("：:，,。 ") or "AI 判定岗位类型相关"
                return {"relevant": True, "reason": reason}
            if plain.startswith("否"):
                reason = plain[1:].lstrip("：:，,。 ") or "AI 判定岗位类型不相关"
                return {"relevant": False, "reason": reason}
            
            # 如果解析失败，默认为不相关
            return {"relevant": False, "reason": "解析失败"}
            
        except Exception as e:
            logger.error(f"解析筛选结果失败: {e}")
            return {"relevant": False, "reason": "解析异常"}
