import os
import requests
import json
from dotenv import load_dotenv

# 加载配置文件中的环境变量
config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config')
secrets_file = os.path.join(config_dir, 'secrets.env')
load_dotenv(secrets_file)


class GPTClient:
    def __init__(self, api_key=None, model_name=None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        # 从配置读取模型名称，支持动态配置
        if model_name:
            self.model_name = model_name
        else:
            # 尝试从配置文件读取，失败则使用默认值
            try:
                from config.config_manager import ConfigManager
                config_manager = ConfigManager()
                self.model_name = config_manager.get_app_config('ai.models.gpt.model_name', 'gpt-4o')
            except Exception:
                self.model_name = 'gpt-4o'  # 最后的默认值
        
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        if not self.api_key:
            print("⚠️ 警告: 未设置OPENAI_API_KEY，请在.env文件中配置")
        
        print(f"🤖 GPT客户端初始化完成，使用模型: {self.model_name}")
    
    def analyze_job_match(self, job_info, user_requirements):
        """分析岗位匹配度"""
        
        # 构造分析prompt
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
{{
    "score": 评分,
    "recommendation": "推荐/不推荐",
    "reason": "详细理由",
    "summary": "一句话总结"
}}
"""

        try:
            response = self.call_api(prompt)
            return self.parse_analysis_result(response)
        except Exception as e:
            print(f"GPT分析岗位匹配度失败: {e}")
            return {
                "score": 0,
                "recommendation": "分析失败",
                "reason": f"GPT API调用失败: {e}",
                "summary": "无法分析此岗位"
            }
    
    def call_api_with_system(self, system_prompt, user_prompt, model=None):
        """调用GPT API（带系统提示）"""
        if not self.api_key:
            raise Exception("OpenAI API Key未配置")
        
        payload = {
            "model": model or self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.3
        }
        
        response = requests.post(
            self.base_url,
            headers=self.headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            raise Exception(f"GPT API调用失败: {response.status_code} - {response.text}")
    
    def call_api(self, prompt, model=None):
        """调用GPT API"""
        if not self.api_key:
            raise Exception("OpenAI API Key未配置")
        
        payload = {
            "model": model or self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.3
        }
        
        response = requests.post(
            self.base_url,
            headers=self.headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            raise Exception(f"GPT API调用失败: {response.status_code} - {response.text}")
    
    def parse_analysis_result(self, response_text):
        """解析分析结果"""
        # 使用与DeepSeek相同的解析逻辑
        from .deepseek_client import DeepSeekClient
        return DeepSeekClient().parse_analysis_result(response_text)