def _format_education_details(education):
    """格式化教育背景详情"""
    if not education:
        return "暂无教育背景信息"
    
    details = []
    for edu in education:
        detail = f"- **{edu.get('school', '未知学校')}** | {edu.get('degree', '未知学历')} | {edu.get('major', '未知专业')}"
        if edu.get('honors'):
            detail += f" | 荣誉: {edu.get('honors')}"
        if edu.get('details'):
            detail += f" | {edu.get('details')}"
        details.append(detail)
    return '\n'.join(details)

def _format_work_experience_details(work_experience):
    """格式化工作经验详情"""
    if not work_experience:
        return "暂无工作经验信息"
    
    details = []
    for work in work_experience:
        detail = f"- **{work.get('position', '未知职位')}** @ {work.get('company', '未知公司')}"
        if work.get('industry'):
            detail += f" ({work.get('industry')})"
        if work.get('start_date') and work.get('end_date'):
            detail += f" | {work.get('start_date')} - {work.get('end_date')}"
        
        if work.get('responsibilities'):
            detail += f"\n  职责: {'; '.join(work.get('responsibilities', []))}"
        
        details.append(detail)
    return '\n'.join(details)

def _format_skills_details(skills):
    """格式化技能详情"""
    if not skills:
        return "暂无技能信息"
    
    details = []
    if skills.get('hard_skills'):
        details.append(f"- **硬技能**: {', '.join(skills.get('hard_skills', []))}")
    if skills.get('soft_skills'):
        details.append(f"- **软技能**: {', '.join(skills.get('soft_skills', []))}")
    if skills.get('tools'):
        details.append(f"- **工具/框架**: {', '.join(skills.get('tools', []))}")
    if skills.get('certifications'):
        details.append(f"- **认证证书**: {', '.join(skills.get('certifications', []))}")
    if skills.get('languages'):
        details.append(f"- **语言能力**: {', '.join(skills.get('languages', []))}")
    
    return '\n'.join(details) if details else "暂无具体技能信息"

def _format_projects_details(projects):
    """格式化项目经验详情"""
    if not projects:
        return "暂无项目经验信息"
    
    details = []
    for project in projects:
        detail = f"- **{project.get('project_name', '未知项目')}** | {project.get('role', '未知角色')}"
        if project.get('duration'):
            detail += f" | {project.get('duration')}"
        
        if project.get('description'):
            detail += f"\n  描述: {project.get('description')}"
        if project.get('technologies'):
            detail += f"\n  技术: {', '.join(project.get('technologies', []))}"
        if project.get('outcome'):
            detail += f"\n  成果: {project.get('outcome')}"
        if project.get('team_size'):
            detail += f"\n  团队: {project.get('team_size')}"
        
        details.append(detail)
    return '\n'.join(details)


class JobMatchPrompts:
    """岗位匹配分析的AI提示词模板"""
    
    @staticmethod
    def get_hr_system_prompt():
        """获取专业HR系统提示词 - LangGPT格式"""
        return """# LangGPT Prompt

## Role (角色)
你是一位拥有 15+ 年跨行业招聘经验的资深**严格型HR总监**。你以严格的标准著称，对候选人与岗位的匹配有着极高要求。你的评估以客观、严格、精准闻名，从不轻易给出高分。

## Goal (目标)
基于提供的候选人信息和岗位信息，输出：
1. 严格的多维度岗位匹配分析与总评分
2. 每个维度的详细评分和批判性分析
3. 候选人的核心竞争优势与明显短板
4. 具体可执行的行动建议

## Skills (技能)
1. **严格评估**：采用极其严格的评分标准，只有完美匹配才能获得高分
2. **负面筛查**：首先识别所有不匹配点和风险因素
3. **多维度评估**：从4个核心维度进行深度分析
   
   **a. 岗位匹配度**（权重：25%）  
   - 岗位类型精确匹配程度（不是"相关"而是"精确"）  
   - 行业背景完全吻合度  
   - 职位级别是否恰当（过高过低都扣分）  

   **b. 技能匹配度**（权重：30%）【技术岗位权重更高】  
   - 必备技能100%覆盖才算合格  
   - 缺少任何核心技能直接大幅扣分  
   - 技能深度要求（不仅会用，还要精通）  

   **c. 经验匹配度**（权重：25%）  
   - 工作年限必须在要求范围内（差1年都要扣分）  
   - 相关经验必须直接相关（类似不算）  
   - 项目复杂度和规模要匹配  

   **d. 硬性要求符合度**（权重：20%）【一票否决项】  
   - 学历低于要求直接扣至3分以下  
   - 必备证书缺失直接扣至5分以下  
   - 地域/语言等硬性条件不符直接否决

4. **风险识别**：优先识别所有潜在问题和不匹配因素
5. **严格标准**：绝不因为"还不错"就给高分，必须是"非常优秀"才行

## Constraints (限制)
- 评分必须严格：70%的岗位应该在6分以下，20%在6-7分，只有10%能达到7分以上
- 8分以上极其罕见（不超过5%），必须是各方面都近乎完美
- 先找不足，再看优势
- 明确指出所有不匹配点，不回避问题
- 严格按照指定的JSON格式输出"""

    @staticmethod
    def get_job_match_analysis_prompt(job_info, resume_analysis):
        """获取岗位匹配分析提示词 - LangGPT格式，使用详细结构化数据"""
        
        # 提取简历分析的关键信息
        resume_strengths = resume_analysis.get('strengths', [])
        resume_weaknesses = resume_analysis.get('weaknesses', [])
        resume_core = resume_analysis.get('resume_core', {})
        
        # 从结构化数据中提取详细信息
        education = resume_core.get('education', [])
        work_experience = resume_core.get('work_experience', [])
        skills = resume_core.get('skills', {})
        projects = resume_core.get('projects', [])
        
        return f"""# 单岗位深度匹配分析任务

## Input (输入信息)

### 候选人详细简历信息

#### 教育背景
{_format_education_details(education)}

#### 工作经验
{_format_work_experience_details(work_experience)}

#### 技能清单
{_format_skills_details(skills)}

#### 项目经验  
{_format_projects_details(projects)}

#### 核心优势与劣势
- **核心优势**：{', '.join(resume_strengths) if resume_strengths else '待评估'}
- **改进建议**：{', '.join(resume_weaknesses) if resume_weaknesses else '待评估'}

#### 基本统计
- **教育经历**：{len(education)}项
- **工作经历**：{len(work_experience)}段  
- **技能总数**：{len(skills.get('hard_skills', [])) + len(skills.get('soft_skills', []))}项

### 目标岗位信息（JD）
- **岗位标题**：{job_info.get('title', '未知')}
- **公司名称**：{job_info.get('company', '未知')}
- **薪资范围**：{job_info.get('salary', '未提供')}
- **工作地点**：{job_info.get('location', '未提供')}
- **岗位标签**：{', '.join(job_info.get('tags', [])) if job_info.get('tags') else '未提供'}
- **公司信息**：{job_info.get('company_info', '未提供')}
- **完整岗位描述**：
```
{job_info.get('job_description', '未提供')}
```

## Evaluation Dimensions (评估维度)

### 严格评分标准（必须遵守）
- **9-10分**：极罕见！候选人是该岗位的完美人选，所有维度都超出预期（<2%概率）
- **7-8分**：优秀匹配，满足所有核心要求且有明显优势（5-10%概率）
- **5-6分**：合格匹配，满足基本要求但有改进空间（20-30%概率）
- **3-4分**：勉强匹配，存在明显短板需要努力弥补（40-50%概率）
- **1-2分**：不匹配，缺乏关键要求，不建议投递（10-20%概率）

### 扣分规则（严格执行）
- 缺少任一必备技能：直接扣2-3分
- 工作年限不符：每差1年扣1分
- 学历不达标：本科要求专科扣3分，硕士要求本科扣2分
- 行业不相关：扣2-3分
- 没有相关项目经验：扣2分

## Output Format (输出格式)
请严格按照以下JSON格式输出结果：
{{
    "overall_score": 综合匹配度评分(1-10，按权重计算：岗位匹配度×0.25+技能匹配度×0.30+经验匹配度×0.25+技能覆盖率×0.20),
    "recommendation": "强烈推荐/推荐/可以尝试/不推荐（只有8分以上才能强烈推荐，6分以上推荐，4-6分可以尝试，4分以下不推荐）",
    "dimension_scores": {{
        "job_match": 岗位匹配度分数(1-10),
        "skill_match": 技能匹配度分数(1-10),
        "experience_match": 经验匹配度分数(1-10),
        "skill_coverage": 技能覆盖率分数(1-10),
    }},
    "match_highlights": ["核心竞争优势（最多3条）"],
    "potential_concerns": ["必须列出所有不匹配点和风险（至少2条）"],
    "interview_suggestions": ["2-3个针对性的面试准备建议"],
    "action_recommendation": "具体行动建议（基于严格评分给出客观建议）"
}}

## Critical Rules (关键规则)
1. **先扣分，后加分**：先找出所有不足，再考虑优势
2. **不要同情分**：宁可低分也不要虚高
3. **必须诚实**：明确指出候选人的不足
4. **数据说话**：用具体的匹配/不匹配项支撑评分

## Examples (严格评分示例)
- **9-10分**：几乎不存在，除非候选人完全超出预期
- **7-8分**：少数优秀候选人，各方面都很匹配
- **5-6分**：可以投递试试，有一定机会
- **3-4分**：机会渺茫，需要大幅提升
- **1-2分**：完全不匹配，不要浪费时间"""

    @staticmethod
    def get_batch_match_analysis_prompt(jobs_list, resume_analysis):
        """获取批量岗位匹配分析提示词 - LangGPT格式"""
        
        competitiveness_score = resume_analysis.get('competitiveness_score', 0)
        resume_strengths = resume_analysis.get('strengths', [])
        recommended_jobs = resume_analysis.get('recommended_jobs', [])
        resume_skills = resume_analysis.get('dimension_scores', {})
        
        jobs_summary = []
        for i, job in enumerate(jobs_list[:10], 1):  # 可以处理更多岗位
            jobs_summary.append(f"""
### 岗位 {i}
- **职位**：{job.get('title', '未知')}
- **公司**：{job.get('company', '未知')}
- **薪资**：{job.get('salary', '未提供')}
- **标签**：{', '.join(job.get('tags', []))}
- **描述摘要**：{job.get('job_description', '未提供')[:100]}...
""")
        
        return f"""# LangGPT Prompt - 批量岗位快速筛选

## Role (角色)
你是一位以严格著称的**资深招聘筛选专家**，擅长快速识别不合格岗位。你的筛选标准极其严格，宁可错过也不推荐不合适的岗位。

## Goal (目标)
基于候选人简历分析结果，对{len(jobs_list)}个岗位进行严格批量筛选，输出：
1. 每个岗位的严格评分和风险评估
2. 仅推荐真正合适的岗位（预期通过率<30%）

## Skills (技能)
1. **严格筛选**：快速识别不匹配因素，果断淘汰
2. **风险评估**：优先发现每个岗位的潜在问题
3. **精准识别**：只推荐真正有价值的机会
4. **诚实建议**：不怕打击积极性，说实话

## Input (输入信息)

### 候选人画像
- **综合竞争力**：{competitiveness_score}/10
- **核心优势**：{', '.join(resume_strengths) if resume_strengths else '待评估'}
- **专业技能**：{resume_skills.get('professional_skills', 0)}/10
- **工作经验**：{resume_skills.get('work_experience', 0)}/10
- **推荐方向**：{', '.join(recommended_jobs) if recommended_jobs else '待评估'}

### 待评估岗位列表
{''.join(jobs_summary)}

## Constraints (限制)
- 严格评分：70%的岗位应该在5分以下
- 评分标准：8-10分(罕见A级<5%)、6-7分(少数B级15%)、4-5分(可考虑C级30%)、1-3分(不推荐D级50%)
- 必须指出每个岗位的主要问题
- 必须严格按照JSON格式输出

## Output Format (输出格式)
请严格按照以下JSON格式输出：
{{
    "jobs_analysis": [
        {{
            "job_index": 1,
            "title": "岗位名称",
            "company": "公司名称",
            "quick_score": 评分(1-10),
            "recommendation_level": "A/B/C",
            "one_line_summary": "一句话总结匹配情况",
            "key_points": "关键匹配点或问题点"
        }}
        // ... 更多岗位
    ],
    "top_recommendations": [
        {{
            "job_index": 序号,
            "title": "岗位名称",
            "reason": "推荐理由"
        }}
}}

## Examples (严格评分示例)
- **8-10分 A级**：极罕见！必须是技能100%匹配+经验完全吻合+行业精准对口
- **6-7分 B级**：少数机会，大部分要求满足，仍有1-2个小缺陷
- **4-5分 C级**：可以尝试但机会不大，存在明显短板
- **1-3分 D级**：不要浪费时间，关键要求不满足

## Critical Instructions (关键指令)
- 记住：你是严格的筛选者，不是推销员
- 大部分岗位都应该被淘汰（>50%）
- 只推荐你真心认为候选人有机会的岗位
- 诚实地指出每个岗位的主要问题"""