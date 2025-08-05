# 三阶段AI分析工作流程说明

## 总体架构
Enhanced Job Analyzer实现了一个三阶段的分析流程，通过不同AI模型的组合实现成本优化和分析深度的平衡。

## 阶段1：信息提取（GLM-4.5）
**目标**：从原始岗位描述中提取结构化信息
**成本**：低（GLM-4.5是低成本模型）
**输出内容**：
```json
{
    "responsibilities": ["岗位职责1", "岗位职责2", "..."],
    "hard_skills": {
        "required": ["必备技能1", "必备技能2"],
        "preferred": ["加分技能1", "加分技能2"]
    },
    "soft_skills": ["沟通能力", "团队协作"],
    "experience_required": "3-5年",
    "education_required": "本科"
}
```

## 阶段2：市场认知分析（DeepSeek）
**目标**：基于所有岗位的提取信息生成市场洞察
**成本**：中等
**输入**：所有岗位的extracted_info
**输出内容**：
```json
{
    "market_overview": {
        "total_jobs_analyzed": 10,
        "analysis_date": "2024-XX-XX",
        "job_title_category": "AI工程师类"
    },
    "skill_requirements": {
        "hard_skills": {
            "core_required": [{"name": "Python", "frequency": "90%", "importance": "核心必备"}],
            "important_preferred": [...],
            "special_scenarios": [...]
        },
        "soft_skills": {...}
    },
    "core_responsibilities": ["核心职责总结1", "核心职责总结2"],
    "market_insights": {
        "tech_stack_trends": ["趋势1", "趋势2"],
        "emerging_skills": ["新兴技能1"],
        "experience_distribution": {"0-3年": "30%", "3-5年": "50%"},
        "education_requirements": {"本科": "60%", "硕士": "35%"}
    },
    "key_findings": [
        "Python是最核心的技能，90%的岗位要求",
        "大模型相关技能需求激增",
        "..."
    ]
}
```

## 阶段3：个人匹配分析（DeepSeek）
**目标**：基于用户简历/偏好对每个岗位进行评分
**成本**：高（需要对每个岗位进行深度分析）
**输入**：原始岗位信息 + 用户简历/偏好
**输出内容**：
```json
{
    "overall_score": 8,
    "score": 8,  // 1-10分的评分
    "recommendation": "A",  // A/B/C/D推荐等级
    "summary": "整体匹配度较高，技能符合度85%...",
    "dimension_scores": {
        "job_match": 8,      // 岗位匹配度
        "skill_match": 7,    // 技能匹配度
        "experience_match": 9, // 经验匹配度
        "salary_match": 8,   // 薪资合理性
        "company_match": 7,  // 公司适配度
        "development": 8,    // 发展潜力
        "location_time": 9,  // 地理位置
        "stability": 7       // 稳定性预期
    },
    "match_highlights": ["亮点1", "亮点2"],
    "potential_concerns": ["潜在问题1", "潜在问题2"],
    "suggestions": ["建议1", "建议2"]
}
```

## 页面展示位置
1. **市场分析报告**：显示在岗位列表顶部，包含技能统计、关键发现等
2. **岗位评分**：每个岗位卡片右上角显示 `X/10` 的评分
3. **智能匹配分析**：每个岗位卡片底部展开区域，显示各维度评分
4. **合格岗位筛选**：根据配置的min_score（现在是6分）过滤岗位

## 成本优化说明
- GLM-4.5负责简单的信息提取，成本极低
- DeepSeek只在需要深度理解和分析时使用
- 市场分析只调用一次，不是每个岗位都调用
- 通过这种分工，100个岗位的分析成本从¥58降低到约¥28.6