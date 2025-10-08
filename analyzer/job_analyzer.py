from .ai_client_factory import AIClientFactory
from .prompts.job_analysis_prompts import JobAnalysisPrompts
from .job_requirement_summarizer import JobRequirementSummarizer, JobRequirementSummary
import os
import json
import asyncio
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class JobAnalyzer:
    def __init__(self, ai_provider=None, model_name=None):
        self.ai_provider = ai_provider or os.getenv('AI_PROVIDER', 'claude')
        self.model_name = model_name
        
        # 如果提供了模型名称，从中推导出provider
        if model_name:
            if 'deepseek' in model_name.lower():
                self.ai_provider = 'deepseek'
            elif 'claude' in model_name.lower():
                self.ai_provider = 'claude'
            elif 'gemini' in model_name.lower():
                self.ai_provider = 'gemini'
        
        # 直接创建AI客户端，跳过AIService包装层
        self.ai_client = self._create_ai_client(self.ai_provider, model_name)
        self.user_requirements = self.get_default_requirements()

        # 初始化市场分析器（替代原有的单岗位总结器）
        from analyzer.market_analyzer import MarketAnalyzer
        self.market_analyzer = MarketAnalyzer(ai_provider=self.ai_provider)
        
        print(f"🤖 使用AI服务: {self.ai_provider.upper()}")
        if model_name:
            print(f"🎯 指定模型: {model_name}")
        print(f"📊 启用市场整体分析引擎")

    def get_default_requirements(self):
        """获取用户要求（从配置文件读取默认偏好）"""
        try:
            from config.config_manager import ConfigManager
            config_manager = ConfigManager()

            # 获取搜索关键词作为求职意向
            keyword = config_manager.get_user_preference('search.keyword', '市场风险管理')
            cities = config_manager.get_user_preference('search.selected_cities', ['shanghai'])

            requirements = f"""
求职意向：
- {keyword}相关岗位

目标城市：
- {', '.join(cities)}

说明：将使用原始简历文本进行岗位匹配分析
"""
            return requirements

        except Exception as e:
            # 如果配置读取失败，返回基础默认值
            import logging
            logging.error(f"获取用户要求失败: {e}")
            return """
求职意向：
- 待设定

说明：请检查配置文件或上传简历
"""

    def _create_ai_client(self, provider: str, model_name: str = None):
        """直接创建AI客户端，跳过AIService包装层"""
        if provider == "deepseek":
            from .clients.deepseek_client import DeepSeekClient
            return DeepSeekClient(model_name)
        elif provider == "claude":
            from .clients.claude_client import ClaudeClient
            return ClaudeClient(model_name)
        elif provider == "gemini":
            from .clients.gemini_client import GeminiClient
            return GeminiClient(model_name)
        elif provider in ["gpt", "openai"]:
            from .clients.gpt_client import GPTClient
            return GPTClient(model_name)
        elif provider == "glm":
            from .clients.glm_client import GLMClient
            return GLMClient(model_name)
        else:
            raise ValueError(f"不支持的AI提供商: {provider}")
    
    def analyze_job_match(self, job_info: Dict[str, Any], resume_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        岗位匹配分析 - 使用专业8维度分析（从AIService移过来的方法）
        
        Args:
            job_info: 岗位信息字典
            resume_analysis: 简历分析结果字典
            
        Returns:
            岗位匹配分析结果字典
        """
        try:
            # 获取统一的提示词模板
            system_prompt = JobAnalysisPrompts.get_hr_system_prompt()
            user_prompt = JobAnalysisPrompts.get_job_match_analysis_prompt(job_info, resume_analysis)
            
            # 直接调用AI客户端API
            response = self.ai_client.call_api(system_prompt, user_prompt)
            
            # 解析结果
            return self._parse_job_analysis_result(response)
            
        except Exception as e:
            logger.error(f"岗位匹配分析失败 [{self.ai_provider}]: {e}")
            # 直接抛出异常，让上层处理
            raise e
    
    def analyze_job_match_simple(self, job_info: Dict[str, Any], user_requirements: str) -> Dict[str, Any]:
        """
        简单岗位匹配分析 - 兼容旧版本接口（从AIService移过来的方法）
        
        Args:
            job_info: 岗位信息字典
            user_requirements: 用户要求字符串
            
        Returns:
            简单岗位匹配分析结果字典
        """
        try:
            # 获取简单提示词模板
            prompt = JobAnalysisPrompts.get_simple_job_match_prompt(job_info, user_requirements)
            
            # 直接调用AI客户端API
            response = self.ai_client.call_api_simple(prompt)
            
            # 解析结果
            return self._parse_simple_job_analysis_result(response)
            
        except Exception as e:
            logger.error(f"简单岗位匹配分析失败 [{self.ai_provider}]: {e}")
            # 直接抛出异常，让上层处理
            raise e

    def analyze_jobs(self, jobs_list):
        """批量分析岗位（基于简历智能匹配）"""
        analyzed_jobs = []
        
        print(f"🤖 开始AI分析 {len(jobs_list)} 个岗位...")
        
        # 第一步：生成市场整体分析（新功能）
        print(f"📊 步骤1: 生成市场整体分析...")
        try:
            # 使用新的市场分析方法
            if self.generate_market_analysis(jobs_list):
                print(f"✅ 市场分析完成，分析了 {self.market_analysis.total_jobs_analyzed} 个岗位")
                
                # 显示分析摘要
                if hasattr(self.market_analysis, 'hard_skills_top5') and self.market_analysis.hard_skills_top5:
                    top_skills = [skill['name'] for skill in self.market_analysis.hard_skills_top5[:3]]
                    print(f"🔝 最常见技能: {', '.join(top_skills)}")
                elif hasattr(self.market_analysis, 'common_skills') and self.market_analysis.common_skills:
                    print(f"🔝 最常见技能: {', '.join(self.market_analysis.common_skills[:3])}")
            else:
                print(f"⚠️ 市场分析生成失败")
                self.market_analysis = None
            
        except Exception as e:
            print(f"⚠️ 市场分析失败: {e}")
            self.market_analysis = None
        
        # 第二步：进行匹配度分析
        print(f"🤖 步骤2: 进行智能匹配分析...")
        
        # 检查是否有简历分析结果
        if self.resume_analysis:
            print(f"🔍 使用简历智能匹配模式")
            return self._analyze_jobs_with_resume_match(jobs_list)
        else:
            print(f"⚠️ 未上传简历，使用默认匹配模式")
            return self._analyze_jobs_default_mode(jobs_list)
    
    def _analyze_jobs_with_resume_match(self, jobs_list):
        """基于简历的智能岗位匹配分析"""
        analyzed_jobs = []
        
        for i, job in enumerate(jobs_list, 1):
            print(f"分析第 {i}/{len(jobs_list)} 个岗位: {job.get('title', '未知')}")
            
            try:
                # 使用新的智能匹配分析
                analysis_result = self._analyze_single_job_match(job)
                
                # 将分析结果添加到岗位信息中
                job['analysis'] = analysis_result
                analyzed_jobs.append(job)
                
                overall_score = analysis_result.get('overall_score', 0)
                print(f"✅ 智能匹配完成 - 综合评分: {overall_score}/10")
                
            except Exception as e:
                print(f"❌ 分析失败: {e}")
                job['analysis'] = {
                    'score': -1,
                    'overall_score': -1,
                    'recommendation': '分析失败',
                    'reason': f'分析失败: {e}',
                    'error': True,
                    'error_message': str(e)
                }
                analyzed_jobs.append(job)
        
        return analyzed_jobs
    
    def _analyze_jobs_default_mode(self, jobs_list):
        """默认模式的岗位分析（兼容原有功能）"""
        analyzed_jobs = []
        
        for i, job in enumerate(jobs_list, 1):
            print(f"分析第 {i}/{len(jobs_list)} 个岗位: {job.get('title', '未知')}")
            
            try:
                # 使用重构后的简单岗位匹配分析方法
                analysis_result = self.analyze_job_match_simple(
                    job, 
                    self.user_requirements
                )
                
                # 将分析结果添加到岗位信息中
                job['analysis'] = analysis_result
                analyzed_jobs.append(job)
                
                print(f"✅ 分析完成 - 评分: {analysis_result['score']}/10")
                
            except Exception as e:
                print(f"❌ 分析失败: {e}")
                job['analysis'] = {
                    'score': -1,
                    'overall_score': -1,
                    'recommendation': '分析失败',
                    'reason': f'分析失败: {e}',
                    'error': True,
                    'error_message': str(e)
                }
                analyzed_jobs.append(job)
        
        return analyzed_jobs
    
    def filter_and_sort_jobs(self, analyzed_jobs, min_score=6):
        """过滤和排序岗位"""
        def get_score(job):
            analysis = job.get('analysis', {})
            # 优先使用overall_score，其次使用score
            return analysis.get('overall_score', analysis.get('score', 0))
        
        # 过滤掉低分岗位
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
        
        print(f"🎯 过滤结果: {len(sorted_jobs)}/{len(analyzed_jobs)} 个岗位达到最低评分标准({min_score}分)")
        
        return sorted_jobs
    
    def get_resume_based_analysis_summary(self):
        """获取基于简历的分析概要"""
        if not self.resume_analysis:
            return None
        
        return {
            'competitiveness_score': self.resume_analysis.get('competitiveness_score', 0),
            'recommended_jobs': self.resume_analysis.get('recommended_jobs', []),
            'strengths': self.resume_analysis.get('strengths', []),
            'improvement_suggestions': self.resume_analysis.get('improvement_suggestions', [])
        }
    
    def get_market_analysis(self):
        """获取市场分析结果"""
        if hasattr(self, 'market_analysis') and self.market_analysis:
            # 返回兼容新格式的数据
            return {
                'common_skills': self.market_analysis.common_skills,
                'keyword_cloud': self.market_analysis.keyword_cloud,
                'differentiation_analysis': self.market_analysis.differentiation_analysis,
                'total_jobs_analyzed': self.market_analysis.total_jobs_analyzed,
                # 新增可视化所需字段
                'hard_skills_top5': self.market_analysis.hard_skills_top5 if hasattr(self.market_analysis, 'hard_skills_top5') else [],
                'education_distribution': self.market_analysis.education_distribution if hasattr(self.market_analysis, 'education_distribution') else {},
                'experience_distribution': self.market_analysis.experience_distribution if hasattr(self.market_analysis, 'experience_distribution') else {},
                'key_insights': self.market_analysis.key_insights if hasattr(self.market_analysis, 'key_insights') else []
            }
        return None
    
    def generate_market_analysis(self, jobs_list):
        """从岗位列表生成市场分析数据 - 使用AI分析器"""
        if not jobs_list:
            return None

        try:
            # 使用AI市场分析器进行深度分析
            logger.info(f"🤖 调用MarketAnalyzer进行AI市场分析，岗位数: {len(jobs_list)}")

            # 调用异步方法
            import asyncio
            ai_result = asyncio.run(self.market_analyzer.analyze_market_trends(jobs_list))

            # 补充统计学历和经验分布（AI可能不包含）
            education_counter = {}
            experience_counter = {}

            for job in jobs_list:
                job_desc = job.get('job_description', '') + ' ' + job.get('job_requirements', '')

                # 统计学历要求
                if '博士' in job_desc:
                    education_counter['博士'] = education_counter.get('博士', 0) + 1
                elif '硕士' in job_desc or '研究生' in job_desc:
                    education_counter['硕士'] = education_counter.get('硕士', 0) + 1
                elif '本科' in job_desc:
                    education_counter['本科'] = education_counter.get('本科', 0) + 1
                else:
                    education_counter['不限'] = education_counter.get('不限', 0) + 1

                # 统计经验要求
                import re
                experience_matches = re.findall(r'(\d+)[年\-]', job_desc)
                if experience_matches:
                    exp_years = max([int(x) for x in experience_matches])
                    if exp_years == 0:
                        experience_counter['应届'] = experience_counter.get('应届', 0) + 1
                    elif exp_years <= 3:
                        experience_counter['1-3年'] = experience_counter.get('1-3年', 0) + 1
                    elif exp_years <= 5:
                        experience_counter['3-5年'] = experience_counter.get('3-5年', 0) + 1
                    else:
                        experience_counter['5年+'] = experience_counter.get('5年+', 0) + 1
                else:
                    experience_counter['不限'] = experience_counter.get('不限', 0) + 1

            # 转换学历分布为百分比
            education_distribution = {}
            edu_total = sum(education_counter.values()) or 1
            for edu, count in education_counter.items():
                education_distribution[edu] = int((count / edu_total) * 100)

            # 转换经验分布为百分比
            experience_distribution = {}
            exp_total = sum(experience_counter.values()) or 1
            for exp, count in experience_counter.items():
                experience_distribution[exp] = int((count / exp_total) * 100)

            # 从AI结果提取技能数据
            hard_skills_top5 = []
            if ai_result.common_skills:
                for skill_dict in ai_result.common_skills[:5]:
                    hard_skills_top5.append({
                        'name': skill_dict.get('name', ''),
                        'frequency': skill_dict.get('percentage', 0),
                        'count': skill_dict.get('percentage', 0)  # 使用percentage作为count的近似
                    })

            # 生成关键洞察（完全由AI生成，不使用固定模板）
            key_insights = []

            # 从AI的差异化分析中提取洞察
            if ai_result.differentiation_analysis.get('analysis'):
                diff_text = ai_result.differentiation_analysis['analysis']
                # 提取所有句子作为关键洞察（不限制数量）
                sentences = [s.strip() + '。' for s in diff_text.split('。') if s.strip()]
                key_insights.extend(sentences)

            # 如果AI没有生成洞察，记录警告但不使用硬编码模板
            if not key_insights:
                logger.warning("⚠️ AI未生成关键洞察，保持为空以确保数据真实性")

            # 创建增强的market_analysis对象
            class EnhancedMarketAnalysis:
                def __init__(self, ai_result, edu_dist, exp_dist, skills, insights):
                    # AI分析结果
                    self.common_skills = ai_result.common_skills
                    self.keyword_cloud = ai_result.keyword_cloud
                    self.differentiation_analysis = ai_result.differentiation_analysis
                    self.total_jobs_analyzed = ai_result.total_jobs_analyzed

                    # 补充统计数据
                    self.education_distribution = edu_dist
                    self.experience_distribution = exp_dist
                    self.hard_skills_top5 = skills
                    self.key_insights = insights

            self.market_analysis = EnhancedMarketAnalysis(
                ai_result,
                education_distribution,
                experience_distribution,
                hard_skills_top5,
                key_insights
            )

            logger.info(f"✅ AI市场分析完成，提取到 {len(hard_skills_top5)} 个核心技能")
            return True

        except Exception as e:
            logger.error(f"❌ AI市场分析失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    
    def _parse_match_analysis_result(self, analysis_result):
        """解析匹配分析结果"""
        try:
            # 如果是字符串，说明是旧版本的raw response，需要解析
            if isinstance(analysis_result, str):
                response_text = analysis_result.strip()
                
                if "```json" in response_text:
                    start = response_text.find("```json") + 7
                    end = response_text.find("```", start)
                    json_text = response_text[start:end].strip()
                elif "{" in response_text and "}" in response_text:
                    start = response_text.find("{")
                    end = response_text.rfind("}") + 1
                    json_text = response_text[start:end]
                else:
                    json_text = response_text
                
                result = json.loads(json_text)
                result['full_output'] = response_text
            
            # 如果是字典，说明是新版本AI服务返回的结构化数据
            elif isinstance(analysis_result, dict):
                result = analysis_result.copy()
            else:
                # 其他类型，转换为字符串处理
                return self._extract_match_info_from_text(str(analysis_result))
            
            # 验证和填充必要字段
            required_fields = [
                'overall_score', 'recommendation', 'dimension_scores',
                'match_highlights', 'potential_concerns', 'interview_suggestions',
                'negotiation_points', 'detailed_analysis', 'action_recommendation'
            ]
            
            for field in required_fields:
                if field not in result:
                    result[field] = self._get_default_match_value(field)
            
            # 确保分数在合理范围内
            if 'overall_score' in result:
                result['overall_score'] = max(1, min(10, float(result['overall_score'])))
            
            # 兼容原有字段格式
            result['score'] = result.get('overall_score', result.get('score', 5))
            result['reason'] = result.get('detailed_analysis', result.get('reason', ''))
            result['summary'] = result.get('action_recommendation', result.get('summary', ''))
            
            return result
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"结果解析失败: {e}")
            return self._extract_match_info_from_text(str(analysis_result))
    
    def _get_default_match_value(self, field):
        """获取匹配分析字段默认值"""
        defaults = {
            'overall_score': 5.0,
            'recommendation': '一般推荐',
            'dimension_scores': {
                'job_match': 5,
                'skill_match': 5,
                'experience_match': 5,
                'skill_coverage': 5
            },
            'match_highlights': ['待分析'],
            'potential_concerns': ['待分析'],
            'interview_suggestions': ['待分析'],
            'negotiation_points': ['待分析'],
            'detailed_analysis': '分析中...',
            'action_recommendation': '待提供建议'
        }
        return defaults.get(field, '待完善')
    
    def _extract_match_info_from_text(self, text):
        """从纯文本中提取匹配信息（fallback方法）"""
        # 简单的文本分析逻辑
        score = 5
        recommendation = '一般推荐'
        
        # 尝试提取评分
        import re
        score_match = re.search(r'评分[:：]\s*(\d+)', text)
        if score_match:
            score = min(10, max(1, int(score_match.group(1))))
        
        # 判断推荐级别
        if '强烈推荐' in text:
            recommendation = '强烈推荐'
        elif '不推荐' in text:
            recommendation = '不推荐'
        elif '推荐' in text:
            recommendation = '推荐'
        
        return {
            'overall_score': score,
            'score': score,  # 兼容字段
            'recommendation': recommendation,
            'dimension_scores': self._get_default_match_value('dimension_scores'),
            'match_highlights': ['文本解析中'],
            'potential_concerns': ['需要重新分析'],
            'interview_suggestions': ['建议重新分析'],
            'negotiation_points': ['建议重新分析'],
            'detailed_analysis': text[:200] + '...' if len(text) > 200 else text,
            'reason': text[:200] + '...' if len(text) > 200 else text,  # 兼容字段
            'action_recommendation': '建议重新上传简历进行分析',
            'summary': '建议重新分析',  # 兼容字段
            'full_output': text
        }
    
    def _get_fallback_analysis(self, error_msg):
        """分析失败时的返回结果"""
        return {
            'overall_score': -1,  # 使用-1表示失败
            'score': -1,
            'recommendation': '分析失败',
            'dimension_scores': {},
            'match_highlights': [],
            'potential_concerns': [],
            'interview_suggestions': [],
            'negotiation_points': [],
            'detailed_analysis': f'分析失败: {error_msg}',
            'reason': f'分析失败: {error_msg}',
            'action_recommendation': '',
            'summary': f'分析失败: {error_msg}',
            'full_output': f'AI分析失败: {error_msg}',
            'error': True,
            'error_message': error_msg
        }
    
    def set_user_requirements(self, requirements):
        """设置用户要求（后续版本使用）"""
        self.user_requirements = requirements
    
    # ==== 从AIService移过来的解析方法 ====
    
    def _parse_job_analysis_result(self, response_text: str) -> Dict[str, Any]:
        """
        解析专业岗位分析结果（从AIService移过来）
        
        Args:
            response_text: AI响应文本
            
        Returns:
            解析后的分析结果字典
        """
        try:
            # 尝试提取JSON部分
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                # 验证必要字段
                required_fields = ['overall_score', 'recommendation', 'dimension_scores']
                if all(field in result for field in required_fields):
                    return result
            
            # 如果JSON解析失败，尝试文本解析
            return self._parse_text_job_analysis(response_text)
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
            return self._parse_text_job_analysis(response_text)
        except Exception as e:
            logger.error(f"解析岗位分析结果失败: {e}")
            return self._get_fallback_job_analysis(f"解析失败: {e}")
    
    def _parse_simple_job_analysis_result(self, response_text: str) -> Dict[str, Any]:
        """
        解析简单岗位分析结果（从AIService移过来）
        
        Args:
            response_text: AI响应文本
            
        Returns:
            解析后的简单分析结果字典
        """
        try:
            # 尝试提取JSON部分
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                # 如果有推荐级别但没有分数，根据推荐级别推断分数
                if 'recommendation' in result and 'score' not in result:
                    recommendation = result['recommendation']
                    if "强烈推荐" in recommendation:
                        result['score'] = 8
                    elif "推荐" in recommendation:
                        result['score'] = 7
                    elif "可以考虑" in recommendation:
                        result['score'] = 6
                    elif "不推荐" in recommendation:
                        result['score'] = 3
                    else:
                        result['score'] = 5
                    logger.info(f"根据推荐级别'{recommendation}'推断分数为{result['score']}")
                
                # 确保分数是数字类型
                if 'score' in result:
                    try:
                        result['score'] = float(result['score'])
                    except (ValueError, TypeError):
                        result['score'] = 5
                
                # 验证必要字段，缺失的用默认值填充
                defaults = {
                    'score': 5,
                    'recommendation': '需要进一步评估',
                    'reason': result.get('reason', '分析完成'),
                    'summary': result.get('summary', '请查看详细分析')
                }
                
                for field, default_value in defaults.items():
                    if field not in result:
                        result[field] = default_value
                
                return result
            
            # JSON解析失败的降级处理
            return {
                "score": 5,
                "recommendation": "需要进一步评估",
                "reason": "AI响应格式异常，无法完成详细分析",
                "summary": "分析结果解析失败"
            }
            
        except Exception as e:
            logger.error(f"解析简单岗位分析结果失败: {e}, 响应内容前100字符: {response_text[:100]}")
            return self._get_fallback_simple_analysis(f"解析失败: {e}")
    
    def _parse_text_job_analysis(self, text: str) -> Dict[str, Any]:
        """从文本中解析岗位分析结果（从AIService移过来）"""
        # 尝试从文本中提取评分
        score_match = re.search(r'(?:总分|综合|评分|score).*?(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        score = float(score_match.group(1)) if score_match else 5.0
        
        # 判断推荐等级
        if score >= 8:
            recommendation = "强烈推荐"
        elif score >= 6:
            recommendation = "推荐"
        elif score >= 4:
            recommendation = "一般推荐"
        else:
            recommendation = "不推荐"
        
        return {
            "overall_score": score,
            "recommendation": recommendation,
            "dimension_scores": {
                "job_match": score,
                "skill_match": score,
                "experience_match": score,
                "skill_coverage": score
            },
            "match_highlights": ["AI分析处理中"],
            "potential_issues": ["AI响应格式异常，建议重新分析"],
            "detailed_analysis": text[:200] + "..." if len(text) > 200 else text,
            "action_recommendation": f"基于{score}分的评估，{recommendation}。"
        }
    
    def _get_fallback_job_analysis(self, error_msg: str) -> Dict[str, Any]:
        """分析失败时的返回结果"""
        return {
            "overall_score": -1,
            "recommendation": "分析失败",
            "dimension_scores": {},
            "match_highlights": [],
            "potential_concerns": [],
            "interview_suggestions": [],
            "negotiation_points": [],
            "detailed_analysis": f"分析失败: {error_msg}",
            "action_recommendation": "",
            "error": True,
            "error_message": error_msg
        }
    
    def _get_fallback_simple_analysis(self, error_msg: str) -> Dict[str, Any]:
        """分析失败时的返回结果"""
        return {
            "score": -1,
            "recommendation": "分析失败",
            "reason": f"分析失败: {error_msg}",
            "summary": f"分析失败: {error_msg}",
            "error": True,
            "error_message": error_msg
        }