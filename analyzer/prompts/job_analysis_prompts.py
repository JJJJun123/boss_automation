#!/usr/bin/env python3
"""
岗位分析相关的提示词模板
统一管理所有岗位分析的AI提示词，支持多种AI模型
"""

from typing import Dict, Any, List


class JobAnalysisPrompts:
    """岗位分析提示词模板类"""
    
    @staticmethod
    def get_hr_system_prompt() -> str:
        """
        获取专业HR系统提示词
        
        Returns:
            专业HR系统提示词
        """
        return """你是一位拥有15年丰富经验的资深HR总监，专精于人才与岗位的精准匹配分析。

你具备以下专业能力：
1. 深度理解候选人的核心竞争力和发展潜力
2. 精准评估岗位要求与人才能力的匹配度
3. 多维度分析人岗匹配的各个关键因素
4. 基于市场趋势提供客观的职业发展建议
5. 识别潜在的职业风险和机会点

你的分析必须：
- 客观公正，基于具体事实和数据
- 严格评分，避免评分过高或过于宽松
- 多维度考量，不仅看技能匹配，还要考虑发展潜力
- 前瞻性思考，结合行业发展趋势
- 实用性强，提供可行的建议和改进方案

重要提醒：请保持严格的评分标准，大多数匹配应该在5-7分之间，只有真正优秀的匹配才能达到8分以上。"""

    @staticmethod
    def get_job_match_analysis_prompt(job_info: Dict[str, Any], resume_analysis: Dict[str, Any]) -> str:
        """
        获取岗位匹配分析提示词
        
        Args:
            job_info: 岗位信息字典
            resume_analysis: 简历分析结果字典
            
        Returns:
            完整的岗位匹配分析提示词
        """
        # 提取简历分析的关键信息
        resume_strengths = resume_analysis.get('strengths', [])
        resume_skills = resume_analysis.get('dimension_scores', {})
        competitiveness_score = resume_analysis.get('competitiveness_score', 0)
        career_advice = resume_analysis.get('career_advice', '暂无')
        
        return f"""请基于候选人简历分析结果，对以下岗位进行精准匹配分析：

【候选人简历分析摘要】
- 综合竞争力评分：{competitiveness_score}/10
- 核心优势：{', '.join(resume_strengths) if resume_strengths else '暂无'}
- 专业技能水平：{resume_skills.get('professional_skills', 0)}/10
- 工作经验价值：{resume_skills.get('work_experience', 0)}/10
- 发展潜力：{resume_skills.get('development_potential', 0)}/10
- 职业发展建议：{career_advice}

【目标岗位信息】
- 岗位标题：{job_info.get('title', '未知')}
- 公司名称：{job_info.get('company', '未知')}
- 薪资范围：{job_info.get('salary', '未提供')}
- 工作地点：{job_info.get('work_location', '未提供')}
- 岗位标签：{', '.join(job_info.get('tags', [])) if job_info.get('tags') else '无'}
- 公司信息：{job_info.get('company_info', '未提供')}
- 岗位描述：{job_info.get('job_description', '未提供')[:500]}{'...' if len(str(job_info.get('job_description', ''))) > 500 else ''}

请从以下8个维度进行深度匹配分析，每个维度给出1-10分评分。

【严格的评分标准】：
- 9-10分：完美匹配，候选人能力远超岗位要求，且各方面条件优秀
- 7-8分：良好匹配，满足大部分要求，有少量不足但可接受
- 5-6分：一般匹配，基本满足要求但有明显短板需要提升
- 3-4分：匹配度较低，多项要求不满足，需要大幅提升
- 1-2分：严重不匹配，基本不符合要求

【8个评分维度】：

1. 【岗位匹配度】
   - 岗位职责与候选人经验的吻合程度
   - 行业背景和工作内容的匹配性
   - 必须严格对比岗位要求与候选人背景

2. 【技能匹配度】
   - 必备技能的覆盖程度（缺少关键技能直接扣分）
   - 技术栈和工具的熟练度匹配
   - 注意区分"必须"和"加分"技能

3. 【经验匹配度】
   - 工作年限与岗位要求的适配性
   - 相关项目经验的深度和广度
   - 经验不足或过度都要扣分

4. 【薪资合理性】
   - 薪资水平与候选人当前能力的匹配
   - 考虑行业和地区的薪资水平
   - 期望薪资与岗位薪资的差距

5. 【公司适配度】
   - 公司规模、文化与候选人背景的匹配
   - 行业发展前景与个人发展规划的一致性
   - 公司稳定性和发展阶段

6. 【发展前景】
   - 该岗位对候选人职业发展的价值
   - 是否有明确的学习成长机会
   - 晋升空间和职业路径是否清晰

7. 【地理位置】
   - 工作地点的便利性（通勤时间）
   - 生活成本与薪资的平衡
   - 是否需要搬家或长期出差

8. 【综合风险评估】
   - 转换成本和适应难度
   - 公司稳定性和行业风险
   - 个人发展与岗位的长期匹配度

特别提醒：
1. 必须找出至少2-3个不匹配或需要改进的点
2. 不要给出过于乐观的评分，保持客观严格
3. 即使是推荐的岗位，也要指出潜在的挑战和风险

请按以下JSON格式返回分析结果：
{{
    "overall_score": 综合匹配度评分(1-10，请根据8个维度的平均分计算，不要随意给高分),
    "recommendation": "强烈推荐/推荐/一般推荐/不推荐（8分以上才能强烈推荐）",
    "dimension_scores": {{
        "job_match": 岗位匹配度分数(1-10),
        "skill_match": 技能匹配度分数(1-10),
        "experience_match": 经验匹配度分数(1-10),
        "salary_reasonableness": 薪资合理性分数(1-10),
        "company_fit": 公司适配度分数(1-10),
        "development_prospects": 发展前景分数(1-10),
        "location_convenience": 地理位置分数(1-10),
        "risk_assessment": 风险评估分数(1-10，越高风险越低)
    }},
    "match_highlights": ["最多3个真实的匹配亮点，不要泛泛而谈"],
    "potential_concerns": ["至少2-3个具体的问题或挑战，必须填写"],
    "interview_suggestions": ["2-3个针对性的面试准备建议"],
    "negotiation_points": ["1-2个实际的谈判要点"],
    "detailed_analysis": "详细分析报告(200-300字，必须包含正面和负面分析)",
    "action_recommendation": "具体行动建议（明确说明是否值得投递以及原因）"
}}

评分示例参考：
- 完美匹配的高级岗位：overall_score 8-9分
- 良好匹配的合适岗位：overall_score 6-7分  
- 一般匹配需要努力：overall_score 4-5分
- 不太匹配建议放弃：overall_score 2-3分"""

    @staticmethod
    def get_simple_job_match_prompt(job_info: Dict[str, Any], user_requirements: str) -> str:
        """
        获取简单岗位匹配分析提示词（兼容旧版本）
        
        Args:
            job_info: 岗位信息字典
            user_requirements: 用户要求字符串
            
        Returns:
            简单岗位匹配分析提示词
        """
        job_desc = job_info.get('job_description', '')[:1000]  # 限制长度
        extracted = job_info.get('extracted_info', {})
        
        return f"""你是一个专业的职业匹配分析师。请分析以下岗位信息与求职者要求的匹配度。

岗位信息：
- 标题：{job_info.get('title', '')}
- 公司：{job_info.get('company', '')}
- 薪资：{job_info.get('salary', '')}
- 工作地点：{job_info.get('work_location', '')}

岗位描述摘要：
{job_desc}

关键信息提取结果：
- 核心职责：{', '.join(extracted.get('responsibilities', ['未提取'])[:3])}
- 必备技能：{', '.join(extracted.get('hard_skills', {}).get('required', ['未提取'])[:5])}
- 经验要求：{extracted.get('experience_required', '未知')}
- 学历要求：{extracted.get('education_required', '未知')}

求职者要求：
{user_requirements}

请从以下维度进行深度分析：
1. 岗位类型匹配度：是否符合求职意向（市场风险管理、AI/人工智能等）
2. 技能匹配度：分析必备技能与求职者背景的契合度
3. 经验匹配度：工作年限和行业经验是否符合
4. 薪资合理性：薪资范围是否在期望区间内
5. 发展前景：该岗位对职业发展的价值

注意：
- 请给出具体的匹配和不匹配点，不要泛泛而谈
- 评分要严格，大部分岗位应该在5-7分之间
- 理由要具体，包含至少2-3个支撑点

请以JSON格式回复：
{{
    "score": 评分(1-10),
    "recommendation": "强烈推荐/推荐/一般推荐/不推荐",
    "reason": "详细理由（至少100字，包含具体的匹配点和不足）",
    "summary": "一句话总结（20-30字）",
    "match_points": ["匹配点1", "匹配点2"],
    "mismatch_points": ["不匹配点1", "不匹配点2"]
}}"""

    @staticmethod
    def get_batch_match_analysis_prompt(jobs_list: List[Dict[str, Any]], resume_analysis: Dict[str, Any]) -> str:
        """
        获取批量岗位匹配分析提示词
        
        Args:
            jobs_list: 岗位列表
            resume_analysis: 简历分析结果
            
        Returns:
            批量岗位匹配分析提示词
        """
        competitiveness_score = resume_analysis.get('competitiveness_score', 0)
        resume_strengths = resume_analysis.get('strengths', [])
        recommended_jobs = resume_analysis.get('recommended_jobs', [])
        
        jobs_summary = []
        for i, job in enumerate(jobs_list[:5], 1):  # 限制前5个岗位
            jobs_summary.append(f"""
岗位{i}：
- 标题：{job.get('title', '未知')}
- 公司：{job.get('company', '未知')}
- 薪资：{job.get('salary', '未提供')}
- 标签：{', '.join(job.get('tags', []))}
""")
        
        return f"""作为资深HR总监，请基于候选人简历分析结果，对以下{len(jobs_list)}个岗位进行批量匹配分析。

【候选人简历摘要】
- 综合竞争力：{competitiveness_score}/10
- 核心优势：{', '.join(resume_strengths)}
- 推荐岗位类型：{', '.join(recommended_jobs)}

【待分析岗位列表】
{''.join(jobs_summary)}

请为每个岗位提供：
1. 快速匹配度评分(1-10)
2. 推荐等级(A/B/C/D)
3. 一句话匹配总结
4. 关键匹配点或问题点

同时提供整体分析：
- 最推荐的前3个岗位及理由
- 整体匹配趋势分析
- 求职策略建议

请以JSON格式返回结果。"""

    @staticmethod
    def get_market_cognition_prompt(extracted_jobs_data: list) -> str:
        """
        获取岗位市场认知分析提示词
        
        Args:
            extracted_jobs_data: 已提取的岗位关键信息列表
            
        Returns:
            市场认知分析提示词
        """
        total_jobs = len(extracted_jobs_data)
        
        # 汇总所有技能
        all_hard_skills = []
        all_soft_skills = []
        all_responsibilities = []
        
        for job in extracted_jobs_data:
            if 'hard_skills' in job:
                all_hard_skills.extend(job['hard_skills'].get('required', []))
                all_hard_skills.extend(job['hard_skills'].get('preferred', []))
            if 'soft_skills' in job:
                all_soft_skills.extend(job['soft_skills'])
            if 'responsibilities' in job:
                all_responsibilities.extend(job['responsibilities'])
        
        return f"""基于{total_jobs}个岗位的信息提取结果，请生成岗位市场认知报告。

【分析任务】
1. 技能需求统计与分类
   - 统计每个技能的出现频次
   - 按频次分类：核心必备（70%+）、重要加分（30%-70%）、特殊场景（<30%）
   - 区分硬技能和软技能

2. 核心职责总结
   - 归纳最常见的3-5项核心工作职责
   - 识别不同公司的职责差异

3. 市场洞察
   - 行业技术栈趋势
   - 新兴技能需求
   - 经验和学历要求分布

【已收集的数据样本】
- 硬技能样本（前50个）：{', '.join(all_hard_skills[:50])}
- 软技能样本（前30个）：{', '.join(all_soft_skills[:30])}
- 职责样本（前20个）：{' | '.join(all_responsibilities[:20])}

请按以下JSON格式返回分析结果：
{{
    "market_overview": {{
        "total_jobs_analyzed": {total_jobs},
        "analysis_date": "今天的日期（格式：2024-XX-XX）",
        "job_title_category": "岗位类型"
    }},
    "skill_requirements": {{
        "hard_skills": {{
            "core_required": [
                {{"name": "技能名", "frequency": "85%", "importance": "核心必备"}}
            ],
            "important_preferred": [
                {{"name": "技能名", "frequency": "45%", "importance": "重要加分"}}
            ],
            "special_scenarios": [
                {{"name": "技能名", "frequency": "15%", "importance": "特定场景"}}
            ]
        }},
        "soft_skills": {{
            "core_required": [
                {{"name": "软技能名", "frequency": "80%", "importance": "核心必备"}}
            ],
            "important_preferred": [
                {{"name": "软技能名", "frequency": "50%", "importance": "重要加分"}}
            ],
            "special_scenarios": [
                {{"name": "软技能名", "frequency": "20%", "importance": "特定场景"}}
            ]
        }}
    }},
    "core_responsibilities": [
        "核心职责1：具体描述",
        "核心职责2：具体描述",
        "核心职责3：具体描述"
    ],
    "market_insights": {{
        "tech_stack_trends": ["趋势1", "趋势2"],
        "emerging_skills": ["新兴技能1", "新兴技能2"],
        "experience_distribution": {{
            "0-3年": "X%",
            "3-5年": "Y%",
            "5年以上": "Z%"
        }},
        "education_requirements": {{
            "本科": "X%",
            "硕士": "Y%",
            "不限": "Z%"
        }}
    }},
    "key_findings": [
        "关键发现1：例如Python是最核心的技能，95%的岗位要求",
        "关键发现2：软技能中沟通能力排名第一",
        "关键发现3：行业开始重视AI相关技能"
    ]
}}"""