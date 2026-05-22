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
- 多维度考量，不仅看技能匹配，还要考虑发展潜力
- 前瞻性思考，结合行业发展趋势
- 实用性强，提供可行的建议和改进方案"""

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
        # 直接使用简历原文进行分析
        resume_text = resume_analysis.get('resume_text', '')
        
        return f"""请基于候选人的简历原文，对以下岗位进行精准匹配分析：

【候选人简历原文】
{resume_text[:1000] if resume_text else '简历内容为空'}

【目标岗位信息】
- 岗位标题：{job_info.get('title', '未知')}
- 公司名称：{job_info.get('company', '未知')}
- 薪资范围：{job_info.get('salary', '未提供')}
- 工作地点：{job_info.get('work_location', '未提供')}
- 岗位标签：{', '.join(job_info.get('tags', [])) if job_info.get('tags') else '无'}
- 公司信息：{job_info.get('company_info', '未提供')}
- 岗位描述：{job_info.get('job_description', '未提供')[:500]}{'...' if len(str(job_info.get('job_description', ''))) > 500 else ''}

请从以下8个维度进行深度匹配分析，每个维度给出1-10分评分。

【评分参考标准】：
- 9-10分：完美匹配，各方面都非常契合
- 7-8分：良好匹配，满足大部分要求
- 5-6分：基本匹配，满足核心要求
- 3-4分：匹配度较低，存在明显不足
- 1-2分：不匹配，不建议申请

【核心评估维度】：

1. 【岗位匹配度】
   - 岗位方向是否符合候选人的目标职位
   - 工作内容与候选人经验的相关性
   - 行业背景的匹配程度

2. 【技能匹配度】
   - 必备技能的覆盖程度（明确列出匹配和缺失的技能）
   - 技术栈的重合度
   - 区分"必须掌握"和"优先/加分"技能

3. 【经验匹配度】
   - 工作年限是否满足要求
   - 相关项目经验的匹配度
   - 行业经验的相关性

4. 【技能覆盖率】
   - 岗位要求的技能中，候选人掌握的比例
   - 明确统计：掌握X个/共Y个要求
   - 区分硬性技能和软性技能的覆盖

5. 【关键词匹配度】
   - 简历与JD中的专业术语重合度
   - 核心技术关键词的匹配
   - 业务领域关键词的匹配

6. 【硬性要求符合度】
   - 学历要求是否满足
   - 必须的证书/资质是否具备
   - 其他硬性门槛（如年龄、性别无歧视）

分析要点：
1. 如有不足之处，请具体指出
2. 根据实际情况给出合理评分
3. 既要看到优势，也要识别潜在挑战

请按以下JSON格式返回分析结果：
{{
    "overall_score": 综合匹配度评分(1-10，根据8个维度综合评估),
    "recommendation": "强烈推荐/推荐/可以考虑/不推荐",
    "dimension_scores": {{
        "job_match": 岗位匹配度分数(1-10),
        "skill_match": 技能匹配度分数(1-10),
        "experience_match": 经验匹配度分数(1-10),
        "skill_coverage": 技能覆盖率分数(1-10),
        "keyword_match": 关键词匹配度分数(1-10),
        "hard_requirements": 硬性要求符合度分数(1-10),
        "education_match": 学历匹配度分数(1-10),
        "project_relevance": 项目相关性分数(1-10)
    }},
    "matched_skills": ["列出候选人掌握且岗位需要的技能"],
    "missing_skills": ["列出岗位要求但候选人缺失的技能"],
    "interview_preparation": ["2-3个基于JD分析的面试重点准备方向"],
    "skill_coverage_detail": "技能覆盖情况说明（如：掌握8/10个要求的技能）",
    "priority_level": "投递优先级（高/中/低）",
    "action_recommendation": "明确的行动建议（建议投递/可以尝试/不建议投递，附简要原因）",
    "application_advice": "建议投递/条件投递/不建议投递",
    "resume_optimization": ["针对此岗位的简历优化建议1", "优化建议2", "优化建议3"],
    "decision_reason": "投递决策的具体理由说明",
    "detailed_dimension_scores": {{
        "education": 学历维度评分(1-10),
        "experience": 经验维度评分(1-10),
        "skills": 技能维度评分(1-10)
    }}
}}

评分参考示例：
- 完美匹配：overall_score 9-10分
- 良好匹配：overall_score 7-8分  
- 基本匹配：overall_score 5-6分
- 匹配度低：overall_score 3-4分
- 不匹配：overall_score 1-2分"""

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
- 请给出具体的匹配和不匹配点
- 理由要具体，包含充分的支撑点

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

# 模块级常量：简历匹配 prompt（供 EnhancedJobAnalyzer 两阶段流水线使用）
RESUME_MATCH_PROMPT = """你是一个严格的招聘评估专家。给你一份求职简历和一个招聘JD，请评估匹配程度。

【简历】
{resume_text}

【岗位】
职位：{job_title}
公司：{company}
薪资：{salary}
岗位描述：{description}
任职要求：{requirements}

请严格按以下JSON格式返回（不要包含其他内容）：
{{
  "score": <1-10的整数，10表示完美匹配>,
  "match_highlights": [<最多3条匹配亮点，字符串列表>],
  "gaps": [<最多3条关键差距，字符串列表>],
  "summary": "<一句话综合评价>"
}}

评分标准：
- 9-10: 完全符合，强烈推荐
- 7-8: 大部分符合，值得重点投递
- 5-6: 部分符合，可以投递但需补强
- 3-4: 匹配度低，建议低优先级
- 1-2: 基本不符合"""
