#!/usr/bin/env python3
"""
增强版岗位分析器
实现三阶段分析流程：
1. 信息提取（GLM-4.5）
2. 市场认知分析（DeepSeek等）
3. 个人匹配分析（DeepSeek等）
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
    """增强版岗位分析器 - 支持三阶段混合模型分析"""
    
    def __init__(self, extraction_provider: str = "glm", 
                 analysis_provider: Optional[str] = None, 
                 model_name: Optional[str] = None,
                 screening_mode: bool = True,
                 extraction_model_name: Optional[str] = "glm-4.5"):
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
        self.market_cognition_report = None
        self.screening_mode = screening_mode
        
        logger.debug(f"🚀 增强版分析器初始化完成")
        logger.debug(f"🎯 筛选模式: {'启用' if screening_mode else '禁用'}")
        logger.debug(f"📋 筛选引擎: {self.extraction_provider.upper()}")
        logger.debug(f"🧠 分析引擎: {self.job_analyzer.ai_provider.upper()}")

    def _is_ai_quota_error(self, error: Exception) -> bool:
        """判断是否为各家AI配额/余额不足错误（GLM/Gemini等）"""
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
    
    async def analyze_jobs_three_stages(self, jobs_list: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        三阶段岗位分析
        
        Args:
            jobs_list: 岗位列表
            
        Returns:
            (市场认知报告, 分析后的岗位列表)
        """
        logger.debug(f"\n🎯 开始三阶段智能分析，共{len(jobs_list)}个岗位...")
        
        # 存储当前处理的岗位列表，用于默认报告
        self._current_job_list = jobs_list
        
        if self.screening_mode:
            # 新流程：快速筛选模式
            # 阶段1：快速筛选相关岗位
            logger.debug(f"\n🔍 阶段1/3: 快速筛选相关岗位（使用{self.extraction_provider.upper()}）...")
            relevant_jobs = await self._stage1_quick_screening(jobs_list)
            
            if not relevant_jobs:
                logger.debug("⚠️ 没有找到相关岗位，返回空结果")
                return self._get_default_market_report(), []
            
            logger.debug(f"✅ 筛选出 {len(relevant_jobs)}/{len(jobs_list)} 个相关岗位")
            
            # 阶段2：信息提取（只对相关岗位）
            logger.debug(f"\n📊 阶段2/3: 提取相关岗位信息（使用{self.extraction_provider.upper()}）...")
            extracted_jobs = await self._stage1_extract_job_info(relevant_jobs)
            
            # 阶段3：市场认知分析
            logger.debug(f"\n🧠 阶段3/3: 市场认知分析（使用{self.job_analyzer.ai_provider.upper()}）...")
            market_report = await self._stage2_market_cognition_analysis(extracted_jobs)
            self.market_cognition_report = market_report
            
            # 阶段4：个人匹配分析（只对相关岗位）
            logger.debug(f"\n🎯 阶段4/4: 个人匹配分析（使用{self.job_analyzer.ai_provider.upper()}）...")
            analyzed_jobs = await self._stage3_personal_match_analysis(relevant_jobs, extracted_jobs)
            
            # 标记不相关的岗位
            all_analyzed_jobs = self._merge_with_irrelevant_jobs(jobs_list, analyzed_jobs, relevant_jobs)
            
            return market_report, all_analyzed_jobs
        else:
            # 原流程：全量分析
            # 阶段1：信息提取
            logger.debug(f"\n📊 阶段1/3: 岗位信息提取（使用{self.extraction_provider.upper()}）...")
            extracted_jobs = await self._stage1_extract_job_info(jobs_list)
            
            # 阶段2：市场认知分析
            logger.debug(f"\n🧠 阶段2/3: 市场认知分析（使用{self.job_analyzer.ai_provider.upper()}）...")
            market_report = await self._stage2_market_cognition_analysis(extracted_jobs)
            self.market_cognition_report = market_report
            
            # 阶段3：个人匹配分析
            logger.debug(f"\n🎯 阶段3/3: 个人匹配分析（使用{self.job_analyzer.ai_provider.upper()}）...")
            analyzed_jobs = await self._stage3_personal_match_analysis(jobs_list, extracted_jobs)
            
            return market_report, analyzed_jobs
    
    async def _stage1_extract_job_info(self, jobs_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        阶段1：信息提取
        使用低成本模型（GLM-4.5）提取关键信息
        """
        extracted_jobs = []
        
        for i, job in enumerate(jobs_list, 1):
            if i % 10 == 0:
                logger.debug(f"   提取进度: {i}/{len(jobs_list)}")
            
            try:
                # 获取提取提示词
                prompt = ExtractionPrompts.get_job_info_extraction_prompt(job)
                
                # 调试：显示完整的输入输出
                if i <= 2:
                    logger.debug(f"\n{'='*60}")
                    logger.debug(f"🔍 GLM调试信息 - 岗位{i}")
                    logger.debug(f"{'='*60}")
                    logger.debug(f"【输入提示词】")
                    logger.debug(prompt[:500] + "..." if len(prompt) > 500 else prompt)
                    logger.debug(f"\n【岗位标题】{job.get('title', '')}")
                    logger.debug(f"【岗位描述长度】{len(job.get('job_description', ''))}字符")
                
                # 调用GLM-4.5进行信息提取，设置较小的max_tokens避免深度思考模式，依赖reasoning_content提取
                response = self.extraction_service.call_api_simple(prompt, max_tokens=800)
                
                # 调试：显示响应
                if i <= 2:
                    logger.debug(f"\n【GLM响应】")
                    logger.debug(f"响应长度: {len(response)}字符")
                    if len(response) == 0:
                        logger.debug("⚠️ 警告: GLM返回了空响应！")
                    else:
                        logger.debug(f"响应内容: {response[:500]}..." if len(response) > 500 else f"响应内容: {response}")
                    logger.debug(f"{'='*60}\n")
                
                # 检查空响应
                if not response or len(response.strip()) == 0:
                    logger.warning(f"岗位{i}的GLM响应为空")
                    raise Exception("GLM返回空响应")
                
                # 解析JSON响应
                extracted_info = self._parse_extraction_result(response)
                
                # 保存原始岗位信息和提取结果
                job_with_extraction = job.copy()
                job_with_extraction['extracted_info'] = extracted_info
                extracted_jobs.append(job_with_extraction)
                
            except Exception as e:
                logger.error(f"提取岗位{i}信息失败: {e}")
                
                # 如果是GLM网络错误，尝试降级到DeepSeek
                if "GLM API网络请求失败" in str(e) or "Read timed out" in str(e):
                    logger.debug(f"⚠️ GLM网络异常，尝试降级到DeepSeek进行岗位{i}的信息提取...")
                    try:
                        # 使用DeepSeek进行提取
                        fallback_response = self.job_analyzer.ai_client.call_api_simple(prompt, max_tokens=3000)
                        extracted_info = self._parse_extraction_result(fallback_response)
                        
                        job_with_extraction = job.copy()
                        job_with_extraction['extracted_info'] = extracted_info
                        extracted_jobs.append(job_with_extraction)
                        logger.debug(f"✅ DeepSeek降级提取成功")
                        continue
                        
                    except Exception as fallback_error:
                        logger.error(f"DeepSeek降级提取也失败: {fallback_error}")
                
                # 提取失败，标记错误
                job_with_extraction = job.copy()
                job_with_extraction['extracted_info'] = {
                    "error": True,
                    "error_message": str(e),
                    "responsibilities": [],
                    "hard_skills": {"required": [], "preferred": [], "bonus": []},
                    "soft_skills": [],
                    "experience_required": "提取失败",
                    "education_required": "提取失败"
                }
                extracted_jobs.append(job_with_extraction)
        
        logger.debug(f"✅ 信息提取完成，成功提取{len(extracted_jobs)}个岗位")
        return extracted_jobs
    
    async def _stage2_market_cognition_analysis(self, extracted_jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        # 已停用：市场认知分析已从核心流程中移除（见 design.md 超出范围章节）
        return self._get_default_market_report()
    
    async def _stage3_personal_match_analysis(self, 
                                            original_jobs: List[Dict[str, Any]], 
                                            extracted_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        阶段3：个人匹配分析
        基于简历对每个岗位进行匹配度分析
        """
        analyzed_jobs = []
        
        for i, (job, extracted_job) in enumerate(zip(original_jobs, extracted_jobs), 1):
            if i % 10 == 0:
                logger.debug(f"   分析进度: {i}/{len(original_jobs)}")
            
            try:
                # 使用简历进行智能匹配（此时必定有简历，因为上层已检查）
                if not self.resume_analysis:
                    raise Exception("简历数据缺失，无法进行岗位匹配分析")
                
                analysis_result = self.job_analyzer.analyze_job_match(
                    job, self.resume_analysis
                )
                
                # 合并分析结果
                job['analysis'] = analysis_result
                job['extracted_info'] = extracted_job.get('extracted_info', {})
                analyzed_jobs.append(job)
                
            except Exception as e:
                logger.error(f"分析岗位{i}失败: {e}")
                # 直接显示失败，不使用fallback
                job['analysis'] = {
                    'score': -1,
                    'overall_score': -1,
                    'recommendation': '分析失败',
                    'reason': f'AI分析失败: {e}',
                    'summary': f'分析失败: {e}',
                    'error': True,
                    'error_message': str(e)
                }
                job['extracted_info'] = extracted_job.get('extracted_info', {})
                analyzed_jobs.append(job)
        
        logger.debug(f"✅ 个人匹配分析完成，共分析 {len(analyzed_jobs)} 个岗位")
        
        # 调试：显示前3个岗位的分析结果摘要
        for i, job in enumerate(analyzed_jobs[:3], 1):
            if 'analysis' in job:
                score = job['analysis'].get('score', 0)
                recommendation = job['analysis'].get('recommendation', '未知')
                logger.debug(f"   岗位{i}: {job.get('title', '未知')} - 评分: {score}/10 - 推荐: {recommendation}")
        
        return analyzed_jobs
    
    def _parse_extraction_result(self, response_text: str) -> Dict[str, Any]:
        """解析信息提取结果"""
        try:
            # 处理可能包含markdown代码块的响应
            import re
            
            # 先尝试提取```json代码块中的内容
            json_code_block = re.search(r'```json\s*\n?(.*?)\n?```', response_text, re.DOTALL)
            if json_code_block:
                try:
                    result = json.loads(json_code_block.group(1).strip())
                    logger.info(f"成功从markdown代码块解析JSON，包含键: {list(result.keys())}")
                    return result
                except json.JSONDecodeError as e:
                    logger.warning(f"markdown代码块中的JSON解析失败: {e}")
            
            # 尝试直接解析整个响应
            try:
                result = json.loads(response_text.strip())
                logger.info(f"成功直接解析JSON，包含键: {list(result.keys())}")
                return result
            except json.JSONDecodeError:
                pass
            
            # 方法3: 查找以{开始，以}结束的完整JSON
            json_start = response_text.find('{')
            if json_start != -1:
                # 找到匹配的闭合括号
                brace_count = 0
                json_end = json_start
                for i in range(json_start, len(response_text)):
                    if response_text[i] == '{':
                        brace_count += 1
                    elif response_text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                if json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    try:
                        result = json.loads(json_str)
                        logger.info(f"成功通过括号匹配解析JSON，包含键: {list(result.keys())}")
                        return result
                    except json.JSONDecodeError as e:
                        logger.warning(f"括号匹配的JSON解析失败: {e}")
                        logger.debug(f"尝试解析的JSON: {json_str[:200]}...")
            
            # 方法4: 使用正则表达式（作为后备）
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    logger.info(f"成功通过正则表达式解析JSON")
                    return result
                except json.JSONDecodeError:
                    pass
            
            logger.warning(f"无法从响应中提取有效的JSON，响应开头: {response_text[:100]}...")
            return self._get_default_extraction()
            
        except Exception as e:
            logger.error(f"解析提取结果失败: {e}")
            logger.debug(f"原始响应: {response_text[:200]}...")
            return self._get_default_extraction()
    
    def _parse_market_cognition_result(self, response_text: str) -> Dict[str, Any]:
        """解析市场认知分析结果"""
        try:
            import re
            logger = logging.getLogger(__name__)
            
            # 1. 尝试从markdown代码块中提取JSON
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                # 清理JSON中的注释
                json_str = re.sub(r'//.*?\n', '\n', json_str)  # 删除单行注释
                return json.loads(json_str)
            
            # 2. 直接查找JSON对象（支持多行和嵌套）
            json_match = re.search(r'\{(?:[^{}]|{[^{}]*})*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                # 清理JSON中的注释
                json_str = re.sub(r'//.*?\n', '\n', json_str)  # 删除单行注释
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as parse_error:
                    logger.warning(f"JSON解析失败，尝试修复: {parse_error}")
                    # 尝试修复常见的JSON问题
                    json_str = json_str.replace(',}', '}').replace(',]', ']')  # 移除多余逗号
                    try:
                        return json.loads(json_str)
                    except:
                        pass
            
            logger.warning(f"无法从响应中提取有效JSON，响应开头: {response_text[:200]}...")
            return self._get_default_market_report()
            
        except Exception as e:
            logger.warning(f"解析市场分析结果失败: {e}")
            return self._get_default_market_report()
    
    def _get_default_extraction(self) -> Dict[str, Any]:
        """获取默认的信息提取结果"""
        return {
            "responsibilities": ["待提取"],
            "hard_skills": {
                "required": [],
                "preferred": [],
                "bonus": []
            },
            "soft_skills": [],
            "experience_required": "未知",
            "education_required": "未知"
        }
    
    def _get_default_market_report(self) -> Dict[str, Any]:
        """获取默认的市场分析报告"""
        return {
            "market_overview": {
                "total_jobs_analyzed": len(getattr(self, '_current_job_list', [])),
                "analysis_date": datetime.now().strftime("%Y-%m-%d")
            },
            "skill_requirements": {
                "hard_skills": {
                    "core_required": [],
                    "important_preferred": [],
                    "special_scenarios": []
                },
                "soft_skills": {
                    "core_required": [],
                    "important_preferred": [],
                    "special_scenarios": []
                }
            },
            "core_responsibilities": ["分析失败"],
            "market_insights": {},
            "key_findings": ["市场分析暂时不可用"]
        }
    
    def _get_fallback_analysis(self, error_msg: str) -> Dict[str, Any]:
        """分析失败时的返回结果"""
        return {
            "overall_score": -1,  # 使用-1表示失败
            "score": -1,
            "recommendation": "分析失败",
            "reason": f"分析失败: {error_msg}",
            "summary": f"分析失败: {error_msg}",
            "dimension_scores": {},
            "match_highlights": [],
            "potential_concerns": [],
            "error": True,
            "error_message": error_msg
        }
    
    
    def get_market_analysis(self) -> Optional[Dict[str, Any]]:
        """获取市场分析结果（兼容原JobAnalyzer接口）"""
        if hasattr(self, 'market_report') and self.market_report:
            # 转换新格式到旧格式以保持前端兼容
            market_report = self.market_report
            logger.info(f"EnhancedJobAnalyzer - 原始market_report包含: {list(market_report.keys())}")
            
            # 合并硬技能和软技能为统一格式
            all_skills = []
            if 'skill_requirements' in market_report:
                skill_req = market_report['skill_requirements']
                
                # 硬技能
                if 'hard_skills' in skill_req:
                    for category in ['core_required', 'important_preferred', 'special_scenarios']:
                        if category in skill_req['hard_skills']:
                            all_skills.extend(skill_req['hard_skills'][category])
                
                # 软技能  
                if 'soft_skills' in skill_req:
                    for category in ['core_required', 'important_preferred', 'special_scenarios']:
                        if category in skill_req['soft_skills']:
                            all_skills.extend(skill_req['soft_skills'][category])
            
            # 转换为旧版本兼容格式
            return {
                'common_skills': all_skills[:20],  # 前20个技能
                'keyword_cloud': all_skills[:30],  # 关键词云
                'differentiation_analysis': {
                    'analysis': market_report.get('core_responsibilities', [])
                },
                'total_jobs_analyzed': market_report.get('market_overview', {}).get('total_jobs_analyzed', 0),
                'market_overview': market_report.get('market_overview', {}),  # 添加完整的市场概览
                'skill_requirements': market_report.get('skill_requirements', {}),  # 添加技能要求详情
                'market_insights': market_report.get('market_insights', {}),
                'key_findings': market_report.get('key_findings', [])
            }
        return None
    
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
    
    async def _stage1_quick_screening(self, jobs_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        阶段1：快速筛选相关岗位
        使用GLM判断岗位是否与求职意向相关
        """
        relevant_jobs = []
        
        for i, job in enumerate(jobs_list, 1):
            if i % 10 == 0:
                logger.debug(f"   筛选进度: {i}/{len(jobs_list)}")
            
            try:
                # 获取筛选提示词
                prompt = ExtractionPrompts.get_job_relevance_screening_prompt(job, self.user_intentions)
                
                # 调用GLM进行快速判断，设置temperature=0保证稳定输出
                response = self.extraction_service.call_api_simple(prompt, max_tokens=200, temperature=0.1)
                
                # 调试：显示GLM响应
                if i == 1:
                    logger.info(f"GLM筛选响应: {response[:200]}")
                
                # 解析结果
                result = self._parse_screening_result(response)
                
                if result.get('relevant', False):
                    job['screening_reason'] = result.get('reason', '')
                    relevant_jobs.append(job)
                    if len(relevant_jobs) <= 3:
                        logger.debug(f"   ✅ 相关岗位: {job.get('title', '')} - {result.get('reason', '')}")
                
            except Exception as e:
                logger.error(f"筛选岗位{i}失败: {e}")
                # 筛选失败的默认不包含
        
        return relevant_jobs
    
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
    
    def _merge_with_irrelevant_jobs(self, all_jobs: List[Dict[str, Any]], 
                                   analyzed_jobs: List[Dict[str, Any]], 
                                   relevant_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        合并分析结果，标记不相关的岗位
        """
        # 创建相关岗位的ID集合
        relevant_ids = {job.get('link', job.get('title', '')) for job in relevant_jobs}
        analyzed_ids = {job.get('link', job.get('title', '')) for job in analyzed_jobs}
        
        result = []
        
        for job in all_jobs:
            job_id = job.get('link', job.get('title', ''))
            
            if job_id in analyzed_ids:
                # 已分析的岗位，从analyzed_jobs中找到对应结果
                for analyzed_job in analyzed_jobs:
                    if analyzed_job.get('link', analyzed_job.get('title', '')) == job_id:
                        result.append(analyzed_job)
                        break
            else:
                # 不相关的岗位，标记为0分
                job['analysis'] = {
                    'score': 0,
                    'overall_score': 0,
                    'recommendation': 'D',
                    'reason': '岗位与求职意向不相关',
                    'summary': '经快速筛选，该岗位与您的求职意向不匹配'
                }
                result.append(job)
        
        return result
