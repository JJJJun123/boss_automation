"""
改进的简历AI分析器，使用DeepSeek进行结构化分析
"""
import json
import logging
from datetime import datetime
from ..deepseek_client import DeepSeekClient


class ResumeAnalyzerV2:
    """改进的简历AI分析器"""
    
    def __init__(self, ai_provider='deepseek'):
        self.logger = logging.getLogger(__name__)
        self.ai_client = DeepSeekClient()
    
    def analyze_resume(self, resume_text):
        """分析简历内容，返回结构化的分析结果"""
        
        if not resume_text or len(resume_text.strip()) < 100:
            self.logger.warning("简历内容太短或为空")
            return self._get_empty_analysis()
        
        # 构建分析prompt
        system_prompt = self._build_hr_system_prompt()
        user_prompt = self._build_analysis_prompt(resume_text)
        
        try:
            self.logger.info("开始调用DeepSeek API分析简历...")
            
            # 调用AI分析
            response = self.ai_client.call_api_with_system(
                system_prompt, 
                user_prompt,
                model="deepseek-reasoner"
            )
            
            self.logger.info(f"AI响应长度: {len(response)} 字符")
            
            # 解析分析结果
            analysis_result = self._parse_analysis_response(response)
            
            # 保存原始输出
            analysis_result['full_output'] = response
            analysis_result['analysis_time'] = datetime.now().isoformat()
            
            self.logger.info(f"简历分析完成，竞争力评分: {analysis_result.get('competitiveness_score')}/10")
            
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"简历分析失败: {e}")
            return self._get_error_analysis(str(e))
    
    def _build_hr_system_prompt(self):
        """构建HR系统提示词"""
        return """你是一位拥有15年经验的资深HR总监，专门负责中高端人才的简历分析和职业发展评估。

你的专业能力包括：
1. 准确识别候选人的核心竞争力和潜在价值
2. 深入理解各行业的岗位要求和发展趋势
3. 客观评估候选人与市场需求的匹配度
4. 提供专业的职业发展建议和改进方案

分析要求：
- 基于简历内容进行客观、专业的分析
- 评分必须合理，避免过高或过低
- 建议必须具体、可执行
- 输出必须是标准的JSON格式"""

    def _build_analysis_prompt(self, resume_text):
        """构建用户分析提示词"""
        
        return f"""请对以下简历进行专业分析：

简历内容：
---
{resume_text}
---

请进行6个维度的专业评估，并严格按照以下JSON格式输出：

{{
    "competitiveness_score": ,  // 总体竞争力评分(1-10分，保留1位小数)
    "competitiveness_desc": "您具有...",  // 50-100字的总体评价
    
    "dimension_scores": {{  // 6个维度的评分，每项1-10分
        "professional_skills": ,      // 专业技能
        "work_experience": ,          // 工作经验
        "education_background": ,      // 教育背景
        "development_potential": ,     // 发展潜力
        "salary_negotiation": ,        // 薪资议价力
        "resume_expression": ,         // 简历表达
    }},
    
    "strengths": [  // 3-5个核心优势
        如：
        "具有5年以上Python开发经验",
        "熟悉金融风控领域",
        "项目管理能力突出"
    ],
    
    "weaknesses": [  // 2-3个待改进点
        如：
        "简历缺少量化的项目成果",
        "缺少大型团队管理经验"
    ],
    
    "recommended_jobs": [  // 3-5个推荐岗位
        如：
        "高级风险管理经理",
        "量化分析师",
        "金融科技产品经理"
    ],
    
    "improvement_suggestions": [  // 3-4个具体建议
        如：
        "建议补充项目的量化成果指标",
        "可以考虑获取FRM或CFA认证",
        "增加对新兴技术的学习和应用"
    ],
    
    "career_advice": "基于您的背景，建议向XXXX领域发展...",  // 100-200字的职业建议
    
    "market_position": "在XXXX领域属于...",  // 市场定位评估
    
    "expected_salary_range": "xx-xx K/月"  // 预期薪资范围
}}

注意：
1. 必须输出完整的JSON格式，不要有额外的说明文字
2. 评分要客观合理
3. 建议要具体且可执行
4. 所有文本使用中文"""

    def _parse_analysis_response(self, response_text):
        """解析AI响应"""
        try:
            # 清理响应文本
            response_text = response_text.strip()
            
            # 提取JSON内容
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
            elif response_text.startswith('{') and response_text.endswith('}'):
                json_text = response_text
            else:
                # 尝试找到JSON开始和结束
                start = response_text.find('{')
                end = response_text.rfind('}')
                if start != -1 and end != -1:
                    json_text = response_text[start:end+1]
                else:
                    raise ValueError("响应中没有找到有效的JSON内容")
            
            # 解析JSON
            result = json.loads(json_text)
            
            # 验证必要字段
            required_fields = [
                'competitiveness_score', 'competitiveness_desc', 
                'dimension_scores', 'strengths', 'weaknesses',
                'recommended_jobs', 'improvement_suggestions'
            ]
            
            for field in required_fields:
                if field not in result:
                    self.logger.warning(f"缺少必要字段: {field}")
                    result[field] = self._get_default_value(field)
            
            # 确保评分在合理范围
            score = result.get('competitiveness_score', 5)
            result['competitiveness_score'] = max(1, min(10, float(score)))
            
            return result
            
        except Exception as e:
            self.logger.error(f"解析AI响应失败: {e}")
            self.logger.error(f"原始响应: {response_text[:500]}...")
            return self._get_error_analysis(f"响应解析失败: {str(e)}")
    
    def _get_default_value(self, field):
        """获取字段默认值 - 明确标识分析失败状态"""
        defaults = {
            'competitiveness_score': 0,
            'competitiveness_desc': '分析未成功',
            'dimension_scores': {
                'professional_skills': 0,
                'work_experience': 0,
                'education_background': 0,
                'development_potential': 0,
                'salary_negotiation': 0,
                'resume_expression': 0,
                'personal_branding': 0,
                'job_match': 0
            },
            'strengths': ['分析未成功'],
            'weaknesses': ['分析未成功'],
            'recommended_jobs': ['分析未成功'],
            'improvement_suggestions': ['请重新上传简历再试'],
            'career_advice': '由于分析失败，无法提供职业建议',
            'market_position': '分析未成功',
            'expected_salary_range': '分析未成功'
        }
        return defaults.get(field, '分析未成功')
    
    def _get_empty_analysis(self):
        """获取空简历的分析结果"""
        return {
            'competitiveness_score': 0,
            'competitiveness_desc': '简历内容为空或过短，无法进行分析',
            'dimension_scores': self._get_default_value('dimension_scores'),
            'strengths': ['简历内容不足，无法分析'],
            'weaknesses': ['请上传包含完整信息的简历'],
            'recommended_jobs': ['无法推荐，请先上传完整简历'],
            'improvement_suggestions': [
                '请上传包含工作经历的完整简历', 
                '确保简历内容不少于100字',
                '检查文件是否正确上传'
            ],
            'career_advice': '无法提供职业建议。请上传包含教育背景、工作经历、技能等完整信息的简历文件。',
            'market_position': '无法评估市场竞争力',
            'expected_salary_range': '无法评估薪资范围',
            'full_output': '简历内容为空或过短，无法调用AI进行分析',
            'analysis_time': datetime.now().isoformat()
        }
    
    def _get_error_analysis(self, error_msg):
        """获取错误情况的分析结果"""
        # 将技术错误转换为用户友好的消息
        user_friendly_msg = self._get_user_friendly_error_msg(error_msg)
        
        return {
            'competitiveness_score': 0,
            'competitiveness_desc': f'分析失败: {user_friendly_msg}',
            'dimension_scores': self._get_default_value('dimension_scores'),
            'strengths': ['AI分析服务暂时不可用'],
            'weaknesses': ['请稍后重试或联系技术支持'],
            'recommended_jobs': ['分析失败，无法提供推荐'],
            'improvement_suggestions': [
                '请稍后重新上传简历',
                '检查网络连接是否正常', 
                '如果问题持续，请联系技术支持'
            ],
            'career_advice': f'由于技术原因分析失败（{user_friendly_msg}），请稍后重试。如果问题持续存在，建议联系技术支持。',
            'market_position': 'AI服务暂时不可用',
            'expected_salary_range': '分析失败，无法评估',
            'full_output': f'AI分析失败: {error_msg}',
            'analysis_time': datetime.now().isoformat()
        }
    
    def _get_user_friendly_error_msg(self, error_msg):
        """将技术错误消息转换为用户友好的描述"""
        error_lower = error_msg.lower()
        
        if 'api key' in error_lower or 'unauthorized' in error_lower:
            return "AI服务配置问题"
        elif 'timeout' in error_lower or 'connection' in error_lower:
            return "网络连接超时"
        elif 'rate limit' in error_lower or 'quota' in error_lower:
            return "服务使用达到限制"
        elif 'json' in error_lower or '解析失败' in error_msg:
            return "AI返回格式异常"
        elif 'server error' in error_lower or '500' in error_msg:
            return "AI服务暂时不可用"
        else:
            return "未知技术问题"