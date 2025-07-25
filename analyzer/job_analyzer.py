from .ai_client_factory import AIClientFactory
from .prompts import JobMatchPrompts
import os
import json


class JobAnalyzer:
    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider or os.getenv('AI_PROVIDER', 'deepseek')
        self.ai_client = AIClientFactory.create_client(self.ai_provider)
        self.user_requirements = self.get_default_requirements()
        self.resume_analysis = None  # 存储简历分析结果
        print(f"🤖 使用AI服务: {self.ai_provider.upper()}")
    
    def get_default_requirements(self):
        """获取默认的用户要求（从配置文件读取，若无则使用硬编码）"""
        try:
            from config.config_manager import ConfigManager
            config_manager = ConfigManager()
            profile = config_manager.get_user_preference('personal_profile', {})
            
            # 从配置构建用户要求文本
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
- 希望在大中型公司发展

薪资期望：
- {salary_range.get('min', 15)}K-{salary_range.get('max', 35)}K/月（可接受范围）

不接受的岗位类型：
{chr(10).join(f'- {excluded}' for excluded in excluded_types)}
"""
            return requirements
            
        except Exception:
            # 如果配置读取失败，使用硬编码默认值
            return """
求职意向：
- 市场风险管理相关岗位
- 咨询相关岗位（战略咨询、管理咨询、行业分析）
- AI/人工智能相关岗位
- 金融相关岗位（银行、证券、基金、保险）

背景要求：
- 有金融行业经验优先
- 熟悉风险管理、数据分析
- 对AI/机器学习有一定了解
- 希望在大中型公司发展

薪资期望：
- 15K-35K/月（可接受范围）

地理位置：
- 深圳优先，其他一线城市可考虑

不接受的岗位类型：
- 纯销售岗位
- 客服岗位
- 纯技术开发（除非AI相关）
- 初级行政岗位
"""
    
    def set_resume_analysis(self, resume_analysis):
        """设置简历分析结果用于智能匹配"""
        self.resume_analysis = resume_analysis
        print(f"📝 简历分析结果已加载，竞争力评分: {resume_analysis.get('competitiveness_score', 0)}/10")
    
    def analyze_jobs(self, jobs_list):
        """批量分析岗位（基于简历智能匹配）"""
        analyzed_jobs = []
        
        print(f"🤖 开始AI分析 {len(jobs_list)} 个岗位...")
        
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
                job['analysis'] = self._get_fallback_analysis(str(e))
                analyzed_jobs.append(job)
        
        return analyzed_jobs
    
    def _analyze_jobs_default_mode(self, jobs_list):
        """默认模式的岗位分析（兼容原有功能）"""
        analyzed_jobs = []
        
        for i, job in enumerate(jobs_list, 1):
            print(f"分析第 {i}/{len(jobs_list)} 个岗位: {job.get('title', '未知')}")
            
            try:
                analysis_result = self.ai_client.analyze_job_match(
                    job, 
                    self.user_requirements
                )
                
                # 将分析结果添加到岗位信息中
                job['analysis'] = analysis_result
                analyzed_jobs.append(job)
                
                print(f"✅ 分析完成 - 评分: {analysis_result['score']}/10")
                
            except Exception as e:
                print(f"❌ 分析失败: {e}")
                job['analysis'] = self._get_fallback_analysis(str(e))
                analyzed_jobs.append(job)
        
        return analyzed_jobs
    
    def filter_and_sort_jobs(self, analyzed_jobs, min_score=6):
        """过滤和排序岗位"""
        # 过滤掉低分岗位
        filtered_jobs = [
            job for job in analyzed_jobs 
            if job.get('analysis', {}).get('score', 0) >= min_score
        ]
        
        # 按分数排序
        sorted_jobs = sorted(
            filtered_jobs, 
            key=lambda x: x.get('analysis', {}).get('score', 0), 
            reverse=True
        )
        
        print(f"🎯 过滤结果: {len(filtered_jobs)}/{len(analyzed_jobs)} 个岗位达到最低评分标准({min_score}分)")
        
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
    
    def _analyze_single_job_match(self, job):
        """分析单个岗位与简历的匹配度"""
        try:
            # 构建专业匹配分析prompt
            system_prompt = JobMatchPrompts.get_hr_system_prompt()
            user_prompt = JobMatchPrompts.get_job_match_analysis_prompt(
                job, self.resume_analysis
            )
            
            # 调用AI分析
            response = self.ai_client.call_api_with_system(
                system_prompt, user_prompt
            )
            
            # 解析结果
            return self._parse_match_analysis_result(response)
            
        except Exception as e:
            print(f"单个岗位匹配分析失败: {e}")
            return self._get_fallback_analysis(str(e))
    
    def _parse_match_analysis_result(self, response_text):
        """解析匹配分析结果"""
        try:
            # 提取JSON部分
            response_text = response_text.strip()
            
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
            result['score'] = result['overall_score']
            result['reason'] = result['detailed_analysis']
            result['summary'] = result['action_recommendation']
            
            # 添加完整输出
            result['full_output'] = response_text
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            return self._extract_match_info_from_text(response_text)
    
    def _get_default_match_value(self, field):
        """获取匹配分析字段默认值"""
        defaults = {
            'overall_score': 5.0,
            'recommendation': '一般推荐',
            'dimension_scores': {
                'job_match': 5,
                'skill_match': 5,
                'experience_match': 5,
                'salary_reasonableness': 5,
                'company_fit': 5,
                'development_prospects': 5,
                'location_convenience': 5,
                'risk_assessment': 5
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
        """获取fallback分析结果"""
        return {
            'overall_score': 0,
            'score': 0,  # 兼容字段
            'recommendation': '分析失败',
            'dimension_scores': self._get_default_match_value('dimension_scores'),
            'match_highlights': ['分析失败'],
            'potential_concerns': ['无法分析'],
            'interview_suggestions': ['请重新分析'],
            'negotiation_points': ['请重新分析'],
            'detailed_analysis': f'分析过程中出错: {error_msg}',
            'reason': f'分析过程中出错: {error_msg}',  # 兼容字段
            'action_recommendation': '请检查网络连接和API配置后重试',
            'summary': '无法分析此岗位',  # 兼容字段
            'full_output': f'AI分析服务异常: {error_msg}'
        }
    
    def set_user_requirements(self, requirements):
        """设置用户要求（后续版本使用）"""
        self.user_requirements = requirements