import json
import os
from datetime import datetime
from ..ai_client_factory import AIClientFactory


class ResumeAnalyzer:
    """简历AI分析器，使用专业HR角色分析简历"""
    
    def __init__(self, ai_provider=None):
        # 从配置读取默认AI提供商
        if not ai_provider:
            try:
                from config.config_manager import ConfigManager
                config_manager = ConfigManager()
                ai_provider = config_manager.get_app_config('ai.default_provider', 'deepseek')
            except Exception:
                ai_provider = 'deepseek'
        
        self.ai_provider = ai_provider
        self.ai_client = AIClientFactory.create_client(ai_provider)
        self.analysis_history = []
        
        print(f"📝 简历分析器初始化完成，使用AI: {self.ai_provider.upper()}")
    
    def analyze_resume(self, resume_text, basic_info=None):
        """分析简历内容，返回完整的AI分析结果"""
        
        # 构建专业HR分析prompt
        system_prompt = self._build_hr_system_prompt()
        user_prompt = self._build_user_analysis_prompt(resume_text, basic_info)
        
        try:
            # 调用AI分析
            analysis_response = self.ai_client.call_api(
                system_prompt, user_prompt
            )
            
            # 解析分析结果
            analysis_result = self._parse_analysis_response(analysis_response)
            
            # 记录分析历史
            self._save_analysis_history(resume_text, analysis_result)
            
            return analysis_result
            
        except Exception as e:
            print(f"简历分析失败: {e}")
            raise e
    
    def _build_hr_system_prompt(self):
        """构建专业HR系统prompt"""
        return """你是一位拥有15年丰富经验的资深HR总监，专精于人才评估和职业发展规划。

重要评估原则：
1. 【严格客观】不要过度乐观，要基于实际经验和技能进行评估
2. 【实事求是】基于简历内容评分，不要凭空想象或过度推测
3. 【市场对标】参考当前市场上同级别人才的平均水平
4. 【合理建议】推荐的岗位要符合候选人的实际水平

评分标准：
- 9-10分：行业顶尖人才，有突出成就和影响力
- 7-8分：优秀人才，在某些领域有明显优势
- 5-6分：合格人才，能胜任对应级别工作
- 3-4分：基础人才，需要进一步提升
- 1-2分：入门级别，经验和技能较弱

请以严格、客观的态度进行评估，避免给出过高的评分。"""
    
    def _build_user_analysis_prompt(self, resume_text, basic_info):
        """构建用户分析prompt"""
        
        basic_info_text = ""
        if basic_info:
            basic_info_text = f"""
已提取的基本信息：
- 姓名：{basic_info.get('name', '未知')}
- 联系方式：{basic_info.get('phone', '未提供')}
- 邮箱：{basic_info.get('email', '未提供')}
- 工作年限：{basic_info.get('experience_years', 0)}年
- 教育背景：{basic_info.get('education', '未知')}
- 技能关键词：{', '.join(basic_info.get('skills', []))}
"""
        
        return f"""请对以下简历进行全面分析：

{basic_info_text}

简历原文：
{resume_text}

请从以下8个维度进行专业分析，并给出详细评估：

重要提醒：
- 根据工作年限合理评估（如3年经验不应推荐总监岗位）
- 基于实际技能水平评分，不要过度乐观
- 推荐岗位要与当前水平匹配

1. 【竞争力评估】(1-10分)
   - 整体竞争力水平（基于工作年限和实际成就）
   - 在同等经验人群中的位置
   - 与市场平均水平的对比

2. 【专业技能匹配度】(1-10分)
   - 技能深度与广度
   - 技能与市场需求的匹配程度
   - 技术栈的前瞻性

3. 【工作经验价值】(1-10分)
   - 工作经历的含金量
   - 项目经验的复杂度
   - 成长轨迹的连贯性

4. 【教育背景适配性】(1-10分)
   - 学历层次适合度
   - 专业与职业方向的匹配
   - 持续学习能力

5. 【职业发展潜力】(1-10分)
   - 未来发展空间
   - 学习能力和适应性
   - 领导力和创新能力

6. 【薪资谈判能力】(1-10分)
   - 基于经验和技能的薪资议价空间
   - 市场稀缺度
   - 可替代性分析

7. 【简历表达能力】(1-10分)
   - 简历逻辑性和条理性
   - 重点突出程度
   - 专业性体现

8. 【个人品牌建设】(1-10分)
   - 个人特色和亮点
   - 行业影响力
   - 职业形象塑造

请按以下JSON格式返回分析结果：
{{
    "competitiveness_score": 总体竞争力评分(1-10),
    "competitiveness_desc": "竞争力描述",
    "dimension_scores": {{
        "professional_skills": 专业技能分数,
        "work_experience": 工作经验分数,
        "education_background": 教育背景分数,
        "development_potential": 发展潜力分数,
        "salary_negotiation": 薪资谈判分数,
        "resume_expression": 简历表达分数,
        "personal_branding": 个人品牌分数
    }},
    "strengths": ["真实的优势1", "优势2", "优势3"],
    "weaknesses": ["客观的不足1", "不足2", "不足3"],
    "recommended_jobs": ["与经验匹配的岗位1(如:中级工程师)", "岗位2", "岗位3"],
    "improvement_suggestions": ["实际可行的建议1", "建议2", "建议3"],
    "career_advice": "职业发展建议",
    "full_analysis": "完整分析报告"
}}"""
    
    def _parse_analysis_response(self, response_text):
        """解析AI分析响应"""
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
                'competitiveness_score', 'competitiveness_desc', 'dimension_scores',
                'strengths', 'weaknesses', 'recommended_jobs', 'improvement_suggestions',
                'career_advice', 'full_analysis'
            ]
            
            for field in required_fields:
                if field not in result:
                    result[field] = self._get_default_value(field)
            
            # 确保分数在合理范围内
            if 'competitiveness_score' in result:
                result['competitiveness_score'] = max(1, min(10, float(result['competitiveness_score'])))
            
            # 添加时间戳和原始输出
            result['analysis_time'] = datetime.now().isoformat()
            result['full_output'] = response_text
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            return self._extract_info_from_text(response_text)
    
    def _get_default_value(self, field):
        """获取字段默认值"""
        defaults = {
            'competitiveness_score': 5.0,
            'competitiveness_desc': '分析中...',
            'dimension_scores': {
                'professional_skills': 5,
                'work_experience': 5,
                'education_background': 5,
                'development_potential': 5,
                'salary_negotiation': 5,
                'resume_expression': 5,
                'personal_branding': 5
            },
            'strengths': ['待分析'],
            'weaknesses': ['待分析'],
            'recommended_jobs': ['待推荐'],
            'improvement_suggestions': ['待建议'],
            'career_advice': '待提供职业建议',
            'full_analysis': '分析中...'
        }
        return defaults.get(field, '待完善')
    
    def _extract_info_from_text(self, text):
        """这个函数不应该被使用"""
        raise NotImplementedError("fallback文本解析已被移除")
        # 以下代码不会执行
        return {
            'competitiveness_score': 5.0,
            'competitiveness_desc': '分析结果解析失败，请重新分析',
            'dimension_scores': {
                'professional_skills': 5,
                'work_experience': 5,
                'education_background': 5,
                'development_potential': 5,
                'salary_negotiation': 5,
                'resume_expression': 5,
                'personal_branding': 5
            },
            'strengths': ['待重新分析'],
            'weaknesses': ['待重新分析'],
            'recommended_jobs': ['待重新推荐'],
            'improvement_suggestions': ['请重新上传简历进行分析'],
            'career_advice': '建议重新进行分析',
            'full_analysis': text[:500] + '...' if len(text) > 500 else text,
            'analysis_time': datetime.now().isoformat(),
            'full_output': text
        }
    
    def _get_fallback_analysis(self, basic_info):
        """这个函数不应该被使用"""
        raise NotImplementedError("fallback机制已被移除")
        # 以下代码不会执行
        experience_years = basic_info.get('experience_years', 0) if basic_info else 0
        skills = basic_info.get('skills', []) if basic_info else []
        
        # 基于基本信息给出简单评估
        base_score = min(10, max(1, 5 + experience_years * 0.5))
        
        return {
            'competitiveness_score': base_score,
            'competitiveness_desc': f'基于{experience_years}年工作经验的初步评估',
            'dimension_scores': {
                'professional_skills': base_score,
                'work_experience': min(10, experience_years * 1.5),
                'education_background': 6,
                'development_potential': base_score,
                'salary_negotiation': base_score,
                'resume_expression': 5,
                'personal_branding': 5
            },
            'strengths': skills[:3] if skills else ['具有一定工作经验'],
            'weaknesses': ['需要更详细的简历分析'],
            'recommended_jobs': ['基于技能的相关岗位'],
            'improvement_suggestions': ['建议重新上传简历进行详细分析'],
            'career_advice': '建议完善简历信息后重新分析',
            'full_analysis': 'AI分析服务暂时不可用，已提供基础评估',
            'analysis_time': datetime.now().isoformat(),
            'full_output': 'AI分析服务异常'
        }
    
    def _save_analysis_history(self, resume_text, analysis_result):
        """保存分析历史"""
        history_item = {
            'timestamp': datetime.now().isoformat(),
            'resume_length': len(resume_text),
            'analysis_result': analysis_result
        }
        
        self.analysis_history.append(history_item)
        
        # 保存到文件（可选）
        try:
            history_file = 'data/resume_analysis_history.json'
            os.makedirs(os.path.dirname(history_file), exist_ok=True)
            
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
            else:
                history_data = []
            
            history_data.append(history_item)
            
            # 只保留最近50条记录
            if len(history_data) > 50:
                history_data = history_data[-50:]
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"保存分析历史失败: {e}")
    
    def get_analysis_history(self):
        """获取分析历史"""
        return self.analysis_history