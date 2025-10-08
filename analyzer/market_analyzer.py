"""
市场分析器 - 分析多个岗位的整体市场趋势
用于替代单个岗位的AI总结功能，提供更有价值的市场洞察
"""

import asyncio
from typing import List, Dict
from collections import Counter
import re
import logging
from dataclasses import dataclass
from analyzer.ai_client_factory import AIClientFactory

logger = logging.getLogger(__name__)

@dataclass
class MarketAnalysisResult:
    """市场分析结果"""
    common_skills: List[Dict[str, any]]        # 共同技能要求及频次
    keyword_cloud: List[Dict[str, any]]        # 关键词云数据
    differentiation_analysis: Dict[str, any]   # 差异化分析
    total_jobs_analyzed: int                   # 分析的岗位总数
    
class MarketAnalyzer:
    """市场整体分析器"""
    
    def __init__(self, ai_provider: str = "deepseek"):
        self.ai_provider = ai_provider
        self.ai_client = AIClientFactory.create_client(ai_provider)
        
    async def analyze_market_trends(self, jobs: List[Dict]) -> MarketAnalysisResult:
        """分析市场整体趋势"""
        logger.info(f"📊 开始分析 {len(jobs)} 个岗位的市场趋势...")
        
        if not jobs:
            return self._create_empty_result()
            
        # 预处理：提取所有岗位的关键信息
        processed_jobs = self._preprocess_jobs(jobs)
        
        # AI分析：一次性分析所有岗位
        try:
            analysis = await self._ai_analyze_market(processed_jobs)
            return analysis
        except Exception as e:
            logger.error(f"❌ AI市场分析失败: {e}")
            logger.error(f"❌ 不使用降级方案，返回空结果以保证数据真实性")
            import traceback
            logger.error(traceback.format_exc())
            # 返回空结果，拒绝使用硬编码降级方案
            return self._create_empty_result()
    
    def _preprocess_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """预处理岗位数据，提取关键信息"""
        processed = []
        for job in jobs:
            processed.append({
                'title': job.get('title', ''),
                'company': job.get('company', ''),
                'salary': job.get('salary', ''),
                'location': job.get('work_location', ''),
                'description': job.get('job_description', ''),
                'requirements': job.get('job_requirements', ''),
                'tags': job.get('tags', [])
            })
        return processed
    
    async def _ai_analyze_market(self, jobs: List[Dict]) -> MarketAnalysisResult:
        """使用AI分析市场趋势"""
        # 构建分析提示词
        prompt = self._build_market_analysis_prompt(jobs)
        
        # 调用AI分析（重构后使用纯净客户端的标准接口）
        try:
            system_prompt = "你是专业的市场分析师，擅长分析职位市场趋势和技能需求。"
            response = self.ai_client.call_api(system_prompt, prompt)
        except Exception as e:
            logger.error(f"❌ 市场分析失败: {e}")
            # 尝试使用简单API调用作为降级方案
            try:
                full_prompt = f"你是专业的市场分析师。{prompt}"
                response = self.ai_client.call_api_simple(full_prompt)
            except Exception as e2:
                logger.error(f"❌ 降级方案也失败: {e2}")
                raise e
        
        # 解析AI响应
        return self._parse_ai_response(response, len(jobs))
    
    def _build_market_analysis_prompt(self, jobs: List[Dict]) -> str:
        """构建市场分析提示词"""
        # 提取岗位摘要信息
        job_summaries = []
        for i, job in enumerate(jobs[:20], 1):  # 限制前20个避免token过多
            summary = f"""
岗位{i}: {job['title']} - {job['company']}
薪资: {job['salary']}
要求片段: {job['requirements'][:200] if job['requirements'] else '无'}
"""
            job_summaries.append(summary)
        
        prompt = f"""请分析以下{len(jobs)}个岗位的市场整体趋势。

岗位样本:
{''.join(job_summaries)}

请提供以下分析:

1. 【共同技能要求】
分析所有岗位中频繁出现的技能和要求，按出现频率排序，格式如下:
- 技能名称 (出现率%)
例如:
- Python编程 (85%)
- 数据分析能力 (75%)
- 团队协作 (65%)

2. 【关键词云】
提取最常见的岗位关键词，包括技术栈、工具、方法论等，格式如下:
- 关键词 (相关岗位数)
例如:
- 机器学习 (12个岗位)
- 风险管理 (8个岗位)

3. 【差异化分析】
分析不同类型岗位的差异，例如:
- 高薪岗位(>30K)的特殊要求
- 大公司vs小公司的要求差异
- 不同行业的侧重点

请用简洁的文字描述，避免冗长。"""
        
        return prompt
    
    def _parse_ai_response(self, response: str, total_jobs: int) -> MarketAnalysisResult:
        """解析AI响应"""
        try:
            # 提取各部分内容
            common_skills = self._extract_common_skills(response)
            keyword_cloud = self._extract_keywords(response)
            differentiation = self._extract_differentiation(response)
            
            return MarketAnalysisResult(
                common_skills=common_skills,
                keyword_cloud=keyword_cloud,
                differentiation_analysis=differentiation,
                total_jobs_analyzed=total_jobs
            )
        except Exception as e:
            logger.error(f"解析AI响应失败: {e}")
            return self._create_empty_result()
    
    def _extract_common_skills(self, text: str) -> List[Dict[str, any]]:
        """从文本中提取共同技能"""
        skills = []
        # 查找技能部分
        skill_section = re.search(r'【共同技能要求】(.*?)(?=【|$)', text, re.DOTALL)
        if skill_section:
            # 提取技能和百分比
            skill_patterns = re.findall(r'[-•]\s*(.+?)\s*[\(（](\d+)%[\)）]', skill_section.group(1))
            for skill, percentage in skill_patterns:
                skills.append({
                    'name': skill.strip(),
                    'percentage': int(percentage)
                })
        return skills
    
    def _extract_keywords(self, text: str) -> List[Dict[str, any]]:
        """从文本中提取关键词"""
        keywords = []
        keyword_section = re.search(r'【关键词云】(.*?)(?=【|$)', text, re.DOTALL)
        if keyword_section:
            # 提取关键词和数量
            keyword_patterns = re.findall(r'[-•]\s*(.+?)\s*[\(（](\d+)个?岗位[\)）]', keyword_section.group(1))
            for keyword, count in keyword_patterns:
                keywords.append({
                    'word': keyword.strip(),
                    'count': int(count)
                })
        return keywords
    
    def _extract_differentiation(self, text: str) -> Dict[str, any]:
        """从文本中提取差异化分析"""
        diff_section = re.search(r'【差异化分析】(.*?)(?=$)', text, re.DOTALL)
        if diff_section:
            return {
                'analysis': diff_section.group(1).strip()
            }
        return {'analysis': '暂无差异化分析'}
    
    def _create_empty_result(self) -> MarketAnalysisResult:
        """创建空结果"""
        return MarketAnalysisResult(
            common_skills=[],
            keyword_cloud=[],
            differentiation_analysis={'analysis': '暂无数据'},
            total_jobs_analyzed=0
        )