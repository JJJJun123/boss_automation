#!/usr/bin/env python3
"""
DeepSeek API客户端
纯API调用器，不包含任何业务逻辑和提示词
"""

import os
import logging
import requests
import json
import asyncio
import aiohttp
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from ..base_client import BaseAIClient

# 加载配置文件中的环境变量
config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config')
secrets_file = os.path.join(config_dir, 'secrets.env')
load_dotenv(secrets_file)
logger = logging.getLogger(__name__)


class DeepSeekClient(BaseAIClient):
    """DeepSeek API客户端 - 纯API调用器"""
    
    def __init__(self, model_name: Optional[str] = None):
        """
        初始化DeepSeek客户端
        
        Args:
            model_name: 模型名称，默认使用deepseek-v4-pro
        """
        super().__init__(model_name)
        
        # 设置默认模型
        if not self.model_name:
            try:
                from config.config_manager import ConfigManager
                config_manager = ConfigManager()
                self.model_name = config_manager.get_app_config('ai.models.deepseek.model_name', 'deepseek-v4-pro')
            except Exception:
                self.model_name = 'deepseek-v4-pro'
        
        # API配置
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 从配置读取参数
        try:
            from config.config_manager import ConfigManager
            config_manager = ConfigManager()
            deepseek_config = config_manager.get_app_config('ai.models.deepseek', {})
            self.temperature = deepseek_config.get('temperature', 0.3)
            self.max_tokens = deepseek_config.get('max_tokens', 1000)
        except Exception:
            self.temperature = 0.3
            self.max_tokens = 1000
        
        logger.debug(f"DeepSeek客户端初始化完成，使用模型: {self.model_name}")
        
        # 验证配置
        self._validate_configuration()
    
    def _validate_configuration(self) -> None:
        """验证DeepSeek配置"""
        if not self.api_key:
            logger.warning("未设置DEEPSEEK_API_KEY，请在config/secrets.env文件中配置")
    
    def call_api(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        调用DeepSeek API - 系统提示词 + 用户提示词模式
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 其他参数（temperature, max_tokens等）
            
        Returns:
            AI响应文本
        """
        if not self.api_key:
            raise Exception("DeepSeek API Key未配置")
        
        # 合并参数
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        model = kwargs.get('model', self.model_name)
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=60  # 增加超时时间
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                raise Exception(f"DeepSeek API调用失败: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"DeepSeek API网络请求失败: {e}")
        except KeyError as e:
            raise Exception(f"DeepSeek API响应格式错误: {e}")
    
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
            raise Exception("DeepSeek API Key未配置")
        
        # 合并参数
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        model = kwargs.get('model', self.model_name)
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=60  # 增加超时时间
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                raise Exception(f"DeepSeek API调用失败: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"DeepSeek API网络请求失败: {e}")
        except KeyError as e:
            raise Exception(f"DeepSeek API响应格式错误: {e}")
    
    async def call_api_async(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """异步API调用"""
        if not self.api_key:
            raise Exception("DeepSeek API Key未配置")
        
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        model = kwargs.get('model', self.model_name)
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        return result['choices'][0]['message']['content']
                    else:
                        error_text = await response.text()
                        raise Exception(f"DeepSeek API调用失败: {response.status} - {error_text}")
                        
            except aiohttp.ClientError as e:
                raise Exception(f"DeepSeek API网络请求失败: {e}")
            except KeyError as e:
                raise Exception(f"DeepSeek API响应格式错误: {e}")