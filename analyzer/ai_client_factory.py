import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()


class AIClientFactory:
    @staticmethod
    def create_client(provider=None, model_name=None):
        """创建AI客户端工厂"""
        provider = provider or os.getenv('AI_PROVIDER', 'deepseek')
        
        # 从配置管理器读取模型配置
        try:
            from config.config_manager import ConfigManager
            config_manager = ConfigManager()
            if not model_name:
                model_name = config_manager.get_app_config(f'ai.models.{provider.lower()}.model_name')
        except Exception:
            pass  # 如果配置读取失败，使用默认值
        
        if provider.lower() == 'deepseek':
            from .deepseek_client import DeepSeekClient
            return DeepSeekClient(model_name=model_name)
        elif provider.lower() == 'claude':
            return ClaudeClient(model_name=model_name)
        elif provider.lower() == 'gemini':
            return GeminiClient(model_name=model_name)
        else:
            raise ValueError(f"不支持的AI provider: {provider}")


class ClaudeClient:
    def __init__(self, api_key=None, model_name=None):
        self.api_key = api_key or os.getenv('CLAUDE_API_KEY')
        self.model_name = model_name or "claude-3-haiku-20240307"  # 默认使用Haiku模型
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        if not self.api_key:
            print("⚠️ 警告: 未设置CLAUDE_API_KEY")
        
        print(f"🤖 Claude客户端初始化完成，使用模型: {self.model_name}")
    
    def analyze_job_match(self, job_info, user_requirements):
        """分析岗位匹配度"""
        prompt = f"""
你是一个专业的职业匹配分析师。请分析以下岗位信息与求职者要求的匹配度。

岗位信息：
- 标题：{job_info.get('title', '')}
- 公司：{job_info.get('company', '')}
- 薪资：{job_info.get('salary', '')}
- 标签/要求：{', '.join(job_info.get('tags', []))}
- 公司信息：{job_info.get('company_info', '')}

求职者要求：
{user_requirements}

请从以下几个维度进行分析：
1. 岗位类型匹配度（是否符合求职意向）
2. 技能要求匹配度
3. 薪资合理性
4. 公司背景适合度

最后给出：
- 综合匹配度评分（1-10分，10分最高）
- 推荐理由（如果分数>=7）或不推荐理由（如果分数<7）
- 一句话总结

请以JSON格式回复：
{{"score": 评分, "recommendation": "推荐/不推荐", "reason": "详细理由", "summary": "一句话总结"}}
"""

        try:
            response = self.call_api(prompt)
            return self.parse_analysis_result(response)
        except Exception as e:
            print(f"Claude分析岗位匹配度失败: {e}")
            return {
                "score": 0,
                "recommendation": "分析失败",
                "reason": f"Claude API调用失败: {e}",
                "summary": "无法分析此岗位"
            }
    
    def call_api(self, prompt):
        """调用Claude API"""
        if not self.api_key:
            raise Exception("Claude API Key未配置")
        
        payload = {
            "model": self.model_name,
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        response = requests.post(
            self.base_url,
            headers=self.headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['content'][0]['text']
        else:
            raise Exception(f"Claude API调用失败: {response.status_code} - {response.text}")
    
    def parse_analysis_result(self, response_text):
        """解析分析结果"""
        # 使用与DeepSeek相同的解析逻辑
        from .deepseek_client import DeepSeekClient
        return DeepSeekClient().parse_analysis_result(response_text)


class GeminiClient:
    def __init__(self, api_key=None, model_name=None):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self.model_name = model_name or "gemini-pro"  # 默认使用gemini-pro
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        
        if not self.api_key:
            print("⚠️ 警告: 未设置GEMINI_API_KEY")
        
        print(f"🤖 Gemini客户端初始化完成，使用模型: {self.model_name}")
    
    def analyze_job_match(self, job_info, user_requirements):
        """分析岗位匹配度"""
        prompt = f"""
你是一个专业的职业匹配分析师。请分析以下岗位信息与求职者要求的匹配度。

岗位信息：
- 标题：{job_info.get('title', '')}
- 公司：{job_info.get('company', '')}
- 薪资：{job_info.get('salary', '')}
- 标签/要求：{', '.join(job_info.get('tags', []))}
- 公司信息：{job_info.get('company_info', '')}

求职者要求：
{user_requirements}

请从以下几个维度进行分析：
1. 岗位类型匹配度（是否符合求职意向）
2. 技能要求匹配度
3. 薪资合理性
4. 公司背景适合度

最后给出：
- 综合匹配度评分（1-10分，10分最高）
- 推荐理由（如果分数>=7）或不推荐理由（如果分数<7）
- 一句话总结

请以JSON格式回复：
{{"score": 评分, "recommendation": "推荐/不推荐", "reason": "详细理由", "summary": "一句话总结"}}
"""

        try:
            response = self.call_api(prompt)
            return self.parse_analysis_result(response)
        except Exception as e:
            print(f"Gemini分析岗位匹配度失败: {e}")
            return {
                "score": 0,
                "recommendation": "分析失败",
                "reason": f"Gemini API调用失败: {e}",
                "summary": "无法分析此岗位"
            }
    
    def call_api(self, prompt):
        """调用Gemini API"""
        if not self.api_key:
            raise Exception("Gemini API Key未配置")
        
        url = f"{self.base_url}?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            raise Exception(f"Gemini API调用失败: {response.status_code} - {response.text}")
    
    def parse_analysis_result(self, response_text):
        """解析分析结果"""
        # 使用与DeepSeek相同的解析逻辑
        from .deepseek_client import DeepSeekClient
        return DeepSeekClient().parse_analysis_result(response_text)