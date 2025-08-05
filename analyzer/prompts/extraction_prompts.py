#!/usr/bin/env python3
"""
信息提取相关的提示词模板
专门用于第一阶段的岗位信息提取，优化为低成本模型（如GLM-4.5）使用
"""

from typing import Dict, Any


class ExtractionPrompts:
    """信息提取提示词模板类"""
    
    @staticmethod
    def get_job_info_extraction_prompt(job_data: Dict[str, Any]) -> str:
        """
        获取岗位信息提取提示词
        
        Args:
            job_data: 原始岗位数据
            
        Returns:
            信息提取提示词
        """
        job_description = job_data.get('job_description', '')
        job_title = job_data.get('title', '')
        company = job_data.get('company', '')
        
        # 限制描述长度，避免过长提示词
        description = job_description[:300] if len(job_description) > 300 else job_description
        
        return f"""分析以下岗位信息，提取关键要素：

岗位名称：{job_title}
公司：{company}
岗位描述：
{description}

请从上述岗位描述中提取以下信息：
1. 岗位职责（responsibilities）：主要工作内容
2. 硬技能要求（hard_skills）：技术、工具、专业能力等
   - required：必须掌握的技能
   - preferred：加分项技能
3. 软技能要求（soft_skills）：沟通、团队协作等
4. 经验要求（experience_required）：工作年限要求
5. 学历要求（education_required）：最低学历要求

输出格式要求：
- 必须是标准JSON格式
- 不要输出任何其他文字
- 如果某项信息未提及，使用"未提及"或空数组

示例输出格式（请根据实际岗位信息填充）：
{{
    "responsibilities": ["实际职责1", "实际职责2", "实际职责3"],
    "hard_skills": {{
        "required": ["必备技能1", "必备技能2"],
        "preferred": ["加分技能1", "加分技能2"]
    }},
    "soft_skills": ["软技能1", "软技能2"],
    "experience_required": "3-5年",
    "education_required": "本科"
}}"""

    @staticmethod
    def get_batch_extraction_prompt(jobs_list: list) -> str:
        """
        获取批量信息提取提示词（备用方案）
        
        Args:
            jobs_list: 岗位列表
            
        Returns:
            批量提取提示词
        """
        job_summaries = []
        for i, job in enumerate(jobs_list[:10], 1):  # 限制10个以控制token
            job_summaries.append(f"""
岗位{i}：
标题：{job.get('title', '')}
公司：{job.get('company', '')}
描述摘要：{job.get('job_description', '')[:200]}...
""")
        
        return f"""请批量提取以下岗位的关键信息：

{''.join(job_summaries)}

对每个岗位，提取：
1. 核心技能要求（区分硬技能和软技能）
2. 经验和学历要求
3. 主要职责（最多3条）

请以JSON数组格式返回，每个岗位一个对象。"""

    @staticmethod
    def get_job_relevance_screening_prompt(job_data: Dict[str, Any], user_intentions: str) -> str:
        """
        获取岗位相关性快速筛选提示词
        用于判断岗位是否与用户求职意向相关
        
        Args:
            job_data: 原始岗位数据
            user_intentions: 用户求职意向
            
        Returns:
            相关性筛选提示词
        """
        job_title = job_data.get('title', '')
        company = job_data.get('company', '')
        job_description = job_data.get('job_description', '')
        
        # 限制描述长度
        description = job_description[:500] if len(job_description) > 500 else job_description
        
        return f"""请判断以下岗位是否与求职意向相关：

求职意向：
{user_intentions}

岗位信息：
职位：{job_title}
公司：{company}
描述：{description}

判断标准：
1. 岗位类型是否匹配求职意向
2. 核心工作内容是否相关
3. 技能要求是否对口

输出要求：
- 只输出一个JSON对象
- 格式：{{"relevant": true/false, "reason": "简短说明原因"}}
- relevant为true表示相关，false表示不相关

示例输出：
{{"relevant": true, "reason": "岗位为AI工程师，符合人工智能求职意向"}}"""