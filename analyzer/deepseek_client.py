import requests
import json
import os
import asyncio
import aiohttp
from dotenv import load_dotenv

# 加载配置文件中的环境变量
config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config')
secrets_file = os.path.join(config_dir, 'secrets.env')
load_dotenv(secrets_file)


class DeepSeekClient:
    def __init__(self, api_key=None, model_name=None):
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        
        # 从配置读取模型名称，支持动态配置
        if model_name:
            self.model_name = model_name
        else:
            # 尝试从配置文件读取，失败则使用默认值
            try:
                from config.config_manager import ConfigManager
                config_manager = ConfigManager()
                self.model_name = config_manager.get_app_config('ai.models.deepseek.model_name', 'deepseek-chat')
            except Exception:
                self.model_name = 'deepseek-chat'  # 最后的默认值
        
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        if not self.api_key:
            print("⚠️ 警告: 未设置DEEPSEEK_API_KEY，请在.env文件中配置")
        
        print(f"🤖 DeepSeek客户端初始化完成，使用模型: {self.model_name}")
    
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
            print(f"分析岗位匹配度失败: {e}")
            return {
                "score": 0,
                "recommendation": "分析失败",
                "reason": f"API调用失败: {e}",
                "summary": "无法分析此岗位"
            }
    
    def call_api_with_system(self, system_prompt, user_prompt, model=None):
        """调用DeepSeek API（带系统提示）"""
        if not self.api_key:
            raise Exception("API Key未配置")
        
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
            raise Exception(f"API调用失败: {response.status_code} - {response.text}")
    
    def call_api(self, prompt, model=None):
        """调用DeepSeek API"""
        if not self.api_key:
            raise Exception("API Key未配置")
        
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
            raise Exception(f"API调用失败: {response.status_code} - {response.text}")
    
    def parse_analysis_result(self, response_text):
        """解析分析结果"""
        try:
            # 尝试从响应中提取JSON
            response_text = response_text.strip()
            
            # 如果响应包含```json标记，提取其中的JSON
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
            elif "{" in response_text and "}" in response_text:
                # 直接提取JSON部分
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_text = response_text[start:end]
            else:
                json_text = response_text
            
            result = json.loads(json_text)
            
            # 验证必要字段
            required_fields = ['score', 'recommendation', 'reason', 'summary']
            for field in required_fields:
                if field not in result:
                    result[field] = "未提供"
            
            # 确保score是数字
            try:
                result['score'] = float(result['score'])
            except:
                result['score'] = 0
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            print(f"原始响应: {response_text}")
            
            # fallback: 尝试从文本中提取信息
            return self.extract_info_from_text(response_text)
    
    def extract_info_from_text(self, text):
        """从纯文本中提取信息（fallback方法）"""
        score = 5  # 默认分数
        recommendation = "需要人工判断"
        reason = text[:200] + "..." if len(text) > 200 else text
        summary = "AI分析结果解析失败"
        
        # 尝试提取分数
        import re
        score_match = re.search(r'评分[：:]\s*(\d+)', text)
        if score_match:
            score = int(score_match.group(1))
        
        # 尝试判断推荐状态
        if "推荐" in text and "不推荐" not in text:
            recommendation = "推荐"
        elif "不推荐" in text:
            recommendation = "不推荐"
        
        return {
            "score": score,
            "recommendation": recommendation,
            "reason": reason,
            "summary": summary
        }
    
    async def analyze_async(self, prompt, model=None):
        """异步调用DeepSeek API"""
        if not self.api_key:
            raise Exception("API Key未配置")
        
        payload = {
            "model": model or self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.3
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result['choices'][0]['message']['content']
                else:
                    error_text = await response.text()
                    raise Exception(f"API调用失败: {response.status} - {error_text}")