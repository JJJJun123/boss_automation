#!/usr/bin/env python3
"""
Gemini API客户端
纯API调用器，不包含任何业务逻辑和提示词
"""

import os
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from ..base_client import BaseAIClient

# 加载配置文件中的环境变量
config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config')
secrets_file = os.path.join(config_dir, 'secrets.env')
load_dotenv(secrets_file)


class GeminiClient(BaseAIClient):
    """Gemini API客户端 - 纯API调用器"""
    
    def __init__(self, model_name: Optional[str] = None):
        """
        初始化Gemini客户端
        
        Args:
            model_name: 模型名称，默认使用gemini-pro
        """
        super().__init__(model_name)
        
        # 设置默认模型
        if not self.model_name:
            try:
                from config.config_manager import ConfigManager
                config_manager = ConfigManager()
                self.model_name = config_manager.get_app_config('ai.models.gemini.model_name', 'gemini-pro')
            except Exception:
                self.model_name = 'gemini-pro'
        
        # API配置
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        
        # 从配置读取参数
        try:
            from config.config_manager import ConfigManager
            config_manager = ConfigManager()
            gemini_config = config_manager.get_app_config('ai.models.gemini', {})
            self.temperature = gemini_config.get('temperature', 0.3)
            self.max_tokens = gemini_config.get('max_tokens', 1000)
        except Exception:
            self.temperature = 0.3
            self.max_tokens = 1000
        
        print(f"🤖 Gemini客户端初始化完成，使用模型: {self.model_name}")
        
        # 验证配置
        self._validate_configuration()
    
    def _validate_configuration(self) -> None:
        """验证Gemini配置"""
        if not self.api_key:
            print("⚠️ 警告: 未设置GEMINI_API_KEY，请在config/secrets.env文件中配置")
    
    def call_api(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        调用Gemini API - 系统提示词 + 用户提示词模式
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 其他参数
            
        Returns:
            AI响应文本
        """
        if not self.api_key:
            raise Exception("Gemini API Key未配置")
        
        # Gemini将系统提示词和用户提示词合并
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # 合并参数
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        
        url = f"{self.base_url}?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": combined_prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                raise Exception(f"Gemini API调用失败: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Gemini API网络请求失败: {e}")
        except KeyError as e:
            raise Exception(f"Gemini API响应格式错误: {e}")
    
    def call_api_simple(self, prompt: str, **kwargs) -> str:
        """
        简单API调用 - 单一提示词模式
        
        Args:
            prompt: 完整提示词
            **kwargs: 其他参数
            
        Returns:
            AI响应文本
        """
        if not self.api_key:
            raise Exception("Gemini API Key未配置")
        
        # 合并参数
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        
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
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                raise Exception(f"Gemini API调用失败: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Gemini API网络请求失败: {e}")
        except KeyError as e:
            raise Exception(f"Gemini API响应格式错误: {e}")