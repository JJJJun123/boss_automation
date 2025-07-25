class JobMatchPrompts:
    """岗位匹配分析的AI提示词模板"""
    
    @staticmethod
    def get_hr_system_prompt():
        """获取专业HR系统提示词"""
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
    def get_job_match_analysis_prompt(job_info, resume_analysis):
        """获取岗位匹配分析提示词"""
        
        # 提取简历分析的关键信息
        resume_strengths = resume_analysis.get('strengths', [])
        resume_skills = resume_analysis.get('dimension_scores', {})
        competitiveness_score = resume_analysis.get('competitiveness_score', 0)
        career_advice = resume_analysis.get('career_advice', '')
        
        return f"""请基于候选人简历分析结果，对以下岗位进行精准匹配分析：

【候选人简历分析摘要】
- 综合竞争力评分：{competitiveness_score}/10
- 核心优势：{', '.join(resume_strengths)}
- 专业技能水平：{resume_skills.get('professional_skills', 0)}/10
- 工作经验价值：{resume_skills.get('work_experience', 0)}/10
- 发展潜力：{resume_skills.get('development_potential', 0)}/10
- 职业发展建议：{career_advice}

【目标岗位信息】
- 岗位标题：{job_info.get('title', '未知')}
- 公司名称：{job_info.get('company', '未知')}
- 薪资范围：{job_info.get('salary', '未提供')}
- 工作地点：{job_info.get('location', '未提供')}
- 岗位标签：{', '.join(job_info.get('tags', []))}
- 公司信息：{job_info.get('company_info', '未提供')}
- 岗位描述：{job_info.get('job_description', '未提供')[:500]}...

请从以下8个维度进行深度匹配分析，每个维度给出1-10分评分：

1. 【岗位匹配度】
   - 岗位职责与候选人经验的吻合程度
   - 行业背景和工作内容的匹配性

2. 【技能匹配度】
   - 必备技能的覆盖程度
   - 技术栈和工具的熟练度匹配

3. 【经验匹配度】
   - 工作年限与岗位要求的适配性
   - 相关项目经验的深度和广度

4. 【薪资合理性】
   - 薪资水平与候选人能力的匹配
   - 市场薪资水平的合理性评估

5. 【公司适配度】
   - 公司规模、文化与候选人期望的匹配
   - 行业发展前景与个人发展规划的一致性

6. 【发展前景】
   - 该岗位对候选人职业发展的价值
   - 学习成长和晋升机会

7. 【地理位置】
   - 工作地点的便利性和合理性
   - 生活成本与薪资的平衡

8. 【综合风险评估】
   - 工作稳定性和公司发展风险
   - 候选人适应新环境的挑战

请按以下JSON格式返回分析结果：
{{
    "overall_score": 综合匹配度评分(1-10),
    "recommendation": "强烈推荐/推荐/一般推荐/不推荐",
    "dimension_scores": {{
        "job_match": 岗位匹配度分数,
        "skill_match": 技能匹配度分数,
        "experience_match": 经验匹配度分数,
        "salary_reasonableness": 薪资合理性分数,
        "company_fit": 公司适配度分数,
        "development_prospects": 发展前景分数,
        "location_convenience": 地理位置分数,
        "risk_assessment": 风险评估分数(越高风险越低)
    }},
    "match_highlights": ["匹配亮点1", "匹配亮点2", "匹配亮点3"],
    "potential_concerns": ["潜在问题1", "潜在问题2"],
    "interview_suggestions": ["面试建议1", "面试建议2"],
    "negotiation_points": ["薪资谈判要点1", "谈判要点2"],
    "detailed_analysis": "详细分析报告(200-300字)",
    "action_recommendation": "具体行动建议"
}}"""

    @staticmethod
    def get_batch_match_analysis_prompt(jobs_list, resume_analysis):
        """获取批量岗位匹配分析提示词"""
        
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