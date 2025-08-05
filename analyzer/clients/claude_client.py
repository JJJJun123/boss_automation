#!/usr/bin/env python3
"""
Claude API客户端
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


class ClaudeClient(BaseAIClient):
    """Claude API客户端 - 纯API调用器"""
    
    def __init__(self, model_name: Optional[str] = None):
        """
        初始化Claude客户端
        
        Args:
            model_name: 模型名称，默认使用claude-3-5-sonnet-20241022
        """
        super().__init__(model_name)
        
        # 设置默认模型
        if not self.model_name:
            try:
                from config.config_manager import ConfigManager
                config_manager = ConfigManager()
                self.model_name = config_manager.get_app_config('ai.models.claude.model_name', 'claude-3-5-sonnet-20241022')
            except Exception:
                self.model_name = 'claude-3-5-sonnet-20241022'
        
        # API配置
        self.api_key = os.getenv('CLAUDE_API_KEY')
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        # 从配置读取参数
        try:
            from config.config_manager import ConfigManager
            config_manager = ConfigManager()
            claude_config = config_manager.get_app_config('ai.models.claude', {})
            self.temperature = claude_config.get('temperature', 0.3)
            self.max_tokens = claude_config.get('max_tokens', 1000)
        except Exception:
            self.temperature = 0.3
            self.max_tokens = 1000
        
        print(f"🤖 Claude客户端初始化完成，使用模型: {self.model_name}")
        
        # 验证配置
        self._validate_configuration()
    
    def _validate_configuration(self) -> None:
        """验证Claude配置"""
        if not self.api_key:
            print("⚠️ 警告: 未设置CLAUDE_API_KEY，请在config/secrets.env文件中配置")
    
    def call_api(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        调用Claude API - 系统提示词 + 用户提示词模式
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 其他参数（temperature, max_tokens等）
            
        Returns:
            AI响应文本
        """
        if not self.api_key:
            raise Exception("Claude API Key未配置")
        
        # 合并参数
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        model = kwargs.get('model', self.model_name)
        
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,  # Claude的系统提示词格式
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        }
        
        try:
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
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Claude API网络请求失败: {e}")
        except KeyError as e:
            raise Exception(f"Claude API响应格式错误: {e}")
    
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
            raise Exception("Claude API Key未配置")
        
        # 合并参数
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        model = kwargs.get('model', self.model_name)
        
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        try:
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
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Claude API网络请求失败: {e}")
        except KeyError as e:
            raise Exception(f"Claude API响应格式错误: {e}")