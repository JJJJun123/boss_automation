#!/usr/bin/env python3
"""
统一AI服务类
提供统一的AI分析服务接口，支持多种AI模型，业务逻辑与AI客户端分离
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List
from .clients.deepseek_client import DeepSeekClient
from .clients.claude_client import ClaudeClient
from .clients.gemini_client import GeminiClient
from .clients.gpt_client import GPTClient
from .clients.glm_client import GLMClient
from .prompts.job_analysis_prompts import JobAnalysisPrompts

logger = logging.getLogger(__name__)


class AIService:
    """统一AI分析服务类 - 包含所有业务逻辑"""
    
    def __init__(self, provider: str = "deepseek", model_name: Optional[str] = None):
        """
        初始化AI服务
        
        Args:
            provider: AI提供商 (deepseek/claude/gemini/gpt)
            model_name: 具体模型名称，如果为None则使用默认模型
        """
        self.provider = provider.lower()
        self.model_name = model_name
        self.client = self._create_client()
        
        logger.info(f"🤖 AI服务初始化完成，使用提供商: {self.provider}")
    
    def _create_client(self):
        """创建AI客户端"""
        try:
            if self.provider == "deepseek":
                return DeepSeekClient(self.model_name)
            elif self.provider == "claude":
                return ClaudeClient(self.model_name)
            elif self.provider == "gemini":
                return GeminiClient(self.model_name)
            elif self.provider in ["gpt", "openai"]:
                return GPTClient(self.model_name)
            elif self.provider == "glm":
                return GLMClient(self.model_name)
            else:
                raise ValueError(f"不支持的AI提供商: {self.provider}")
        except Exception as e:
            logger.error(f"创建AI客户端失败: {e}")
            raise
    
    def analyze_job_match(self, job_info: Dict[str, Any], resume_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        岗位匹配分析 - 使用专业8维度分析
        
        Args:
            job_info: 岗位信息字典
            resume_analysis: 简历分析结果字典
            
        Returns:
            岗位匹配分析结果字典
        """
        try:
            # 获取统一的提示词模板
            system_prompt = JobAnalysisPrompts.get_hr_system_prompt()
            user_prompt = JobAnalysisPrompts.get_job_match_analysis_prompt(job_info, resume_analysis)
            
            # 调用AI API
            response = self.client.call_api(system_prompt, user_prompt)
            
            # 解析结果
            return self._parse_job_analysis_result(response)
            
        except Exception as e:
            logger.error(f"岗位匹配分析失败 [{self.provider}]: {e}")
            return self._get_fallback_job_analysis(str(e))
    
    def analyze_job_match_simple(self, job_info: Dict[str, Any], user_requirements: str) -> Dict[str, Any]:
        """
        简单岗位匹配分析 - 兼容旧版本接口
        
        Args:
            job_info: 岗位信息字典
            user_requirements: 用户要求字符串
            
        Returns:
            简单岗位匹配分析结果字典
        """
        try:
            # 获取简单提示词模板
            prompt = JobAnalysisPrompts.get_simple_job_match_prompt(job_info, user_requirements)
            
            # 调用AI API
            response = self.client.call_api_simple(prompt)
            
            # 解析结果
            return self._parse_simple_job_analysis_result(response)
            
        except Exception as e:
            logger.error(f"简单岗位匹配分析失败 [{self.provider}]: {e}")
            return self._get_fallback_simple_analysis(str(e))
    
    def analyze_batch_jobs(self, jobs_list: List[Dict[str, Any]], resume_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        批量岗位匹配分析
        
        Args:
            jobs_list: 岗位列表
            resume_analysis: 简历分析结果
            
        Returns:
            批量分析结果字典
        """
        try:
            # 获取批量分析提示词
            prompt = JobAnalysisPrompts.get_batch_match_analysis_prompt(jobs_list, resume_analysis)
            
            # 调用AI API
            response = self.client.call_api_simple(prompt)
            
            # 解析结果
            return self._parse_batch_analysis_result(response)
            
        except Exception as e:
            logger.error(f"批量岗位分析失败 [{self.provider}]: {e}")
            return {"error": str(e), "jobs_analysis": []}
    
    def _parse_job_analysis_result(self, response_text: str) -> Dict[str, Any]:
        """
        解析专业岗位分析结果
        
        Args:
            response_text: AI响应文本
            
        Returns:
            解析后的分析结果字典
        """
        try:
            # 尝试提取JSON部分
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                # 验证必要字段
                required_fields = ['overall_score', 'recommendation', 'dimension_scores']
                if all(field in result for field in required_fields):
                    return result
            
            # 如果JSON解析失败，尝试文本解析
            return self._parse_text_job_analysis(response_text)
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
            return self._parse_text_job_analysis(response_text)
        except Exception as e:
            logger.error(f"解析岗位分析结果失败: {e}")
            return self._get_fallback_job_analysis(f"解析失败: {e}")
    
    def _parse_simple_job_analysis_result(self, response_text: str) -> Dict[str, Any]:
        """
        解析简单岗位分析结果
        
        Args:
            response_text: AI响应文本
            
        Returns:
            解析后的简单分析结果字典
        """
        try:
            # 尝试提取JSON部分
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                # 验证必要字段
                required_fields = ['score', 'recommendation', 'reason', 'summary']
                if all(field in result for field in required_fields):
                    return result
            
            # JSON解析失败的降级处理
            return {
                "score": 5,
                "recommendation": "需要进一步评估",
                "reason": "AI响应格式异常，无法完成详细分析",
                "summary": "分析结果解析失败"
            }
            
        except Exception as e:
            logger.error(f"解析简单岗位分析结果失败: {e}")
            return self._get_fallback_simple_analysis(f"解析失败: {e}")
    
    def _parse_text_job_analysis(self, text: str) -> Dict[str, Any]:
        """从文本中解析岗位分析结果"""
        # 尝试从文本中提取评分
        score_match = re.search(r'(?:总分|综合|评分|score).*?(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        score = float(score_match.group(1)) if score_match else 5.0
        
        # 判断推荐等级
        if score >= 8:
            recommendation = "强烈推荐"
        elif score >= 6:
            recommendation = "推荐"
        elif score >= 4:
            recommendation = "一般推荐"
        else:
            recommendation = "不推荐"
        
        return {
            "overall_score": score,
            "recommendation": recommendation,
            "dimension_scores": {
                "job_match": score,
                "skill_match": score,
                "experience_match": score,
                "salary_reasonableness": score,
                "company_fit": score,
                "development_prospects": score,
                "location_convenience": score,
                "risk_assessment": score
            },
            "match_highlights": ["AI分析处理中"],
            "potential_concerns": ["AI响应格式异常，建议重新分析"],
            "detailed_analysis": text[:200] + "..." if len(text) > 200 else text,
            "action_recommendation": f"基于{score}分的评估，{recommendation}。"
        }
    
    def _parse_batch_analysis_result(self, response_text: str) -> Dict[str, Any]:
        """解析批量分析结果"""
        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"error": "无法解析批量分析结果", "jobs_analysis": []}
        except Exception as e:
            return {"error": f"批量分析解析失败: {e}", "jobs_analysis": []}
    
    def _get_fallback_job_analysis(self, error_msg: str) -> Dict[str, Any]:
        """获取岗位分析的降级结果"""
        return {
            "overall_score": 0,
            "recommendation": "分析失败",
            "dimension_scores": {
                "job_match": 0,
                "skill_match": 0,
                "experience_match": 0,
                "salary_reasonableness": 0,
                "company_fit": 0,
                "development_prospects": 0,
                "location_convenience": 0,
                "risk_assessment": 0
            },
            "match_highlights": [],
            "potential_concerns": [f"AI分析失败: {error_msg}"],
            "interview_suggestions": [],
            "negotiation_points": [],
            "detailed_analysis": f"分析过程中出现错误: {error_msg}",
            "action_recommendation": "由于分析失败，建议手动评估该岗位。"
        }
    
    def _get_fallback_simple_analysis(self, error_msg: str) -> Dict[str, Any]:
        """获取简单分析的降级结果"""
        return {
            "score": 0,
            "recommendation": "分析失败",
            "reason": f"AI分析出现错误: {error_msg}",
            "summary": "无法完成岗位匹配分析"
        }
    
    def get_client_info(self) -> Dict[str, Any]:
        """获取客户端信息"""
        return {
            "provider": self.provider,
            "model_info": self.client.get_model_info() if hasattr(self.client, 'get_model_info') else {},
            "connection_status": self.client.test_connection() if hasattr(self.client, 'test_connection') else None
        }
    
    def switch_provider(self, provider: str, model_name: Optional[str] = None) -> None:
        """
        切换AI提供商
        
        Args:
            provider: 新的AI提供商
            model_name: 新的模型名称
        """
        self.provider = provider.lower()
        self.model_name = model_name
        self.client = self._create_client()
        logger.info(f"🔄 AI服务已切换到: {self.provider}")
    
    def call_api_simple(self, prompt: str, **kwargs) -> str:
        """
        简单API调用包装方法（供外部调用）
        
        Args:
            prompt: 完整提示词
            **kwargs: 其他参数
            
        Returns:
            AI响应文本
        """
        return self.client.call_api_simple(prompt, **kwargs)


# 工厂函数，方便快速创建AI服务
def create_ai_service(provider: str = None, model_name: str = None) -> AIService:
    """
    创建AI服务实例
    
    Args:
        provider: AI提供商，如果为None则从配置读取默认值
        model_name: 模型名称
        
    Returns:
        AIService实例
    """
    if not provider:
        try:
            from config.config_manager import ConfigManager
            config_manager = ConfigManager()
            provider = config_manager.get_app_config('ai.default_provider', 'deepseek')
        except Exception:
            provider = 'deepseek'
    
    return AIService(provider, model_name)