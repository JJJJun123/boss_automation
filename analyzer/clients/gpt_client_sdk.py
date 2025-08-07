#!/usr/bin/env python3
"""
GPT API客户端 - 使用官方OpenAI SDK
纯API调用器，不包含任何业务逻辑和提示词
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from ..base_client import BaseAIClient

# 加载配置文件中的环境变量
config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config')
secrets_file = os.path.join(config_dir, 'secrets.env')
load_dotenv(secrets_file)

# 导入OpenAI SDK
try:
    from openai import OpenAI
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OPENAI_SDK_AVAILABLE = False
    print("⚠️ OpenAI SDK未安装，请运行: pip install openai")


class GPTClientSDK(BaseAIClient):
    """GPT API客户端 - 使用官方SDK"""
    
    def __init__(self, model_name: Optional[str] = None):
        """
        初始化GPT客户端
        
        Args:
            model_name: 模型名称，默认使用gpt-4o-mini
        """
        super().__init__(model_name)
        
        if not OPENAI_SDK_AVAILABLE:
            raise ImportError("OpenAI SDK未安装，请运行: pip install openai")
        
        # 设置默认模型
        if not self.model_name:
            try:
                from config.config_manager import ConfigManager
                config_manager = ConfigManager()
                self.model_name = config_manager.get_app_config('ai.models.gpt.model_name', 'gpt-4o-mini')
            except Exception:
                self.model_name = 'gpt-4o-mini'
        
        # 初始化OpenAI客户端
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("⚠️ 警告: 未设置OPENAI_API_KEY，请在config/secrets.env文件中配置")
        
        self.client = OpenAI(api_key=api_key)
        
        # 从配置读取参数
        try:
            from config.config_manager import ConfigManager
            config_manager = ConfigManager()
            gpt_config = config_manager.get_app_config('ai.models.gpt', {})
            self.temperature = gpt_config.get('temperature', 0.3)
            self.max_tokens = gpt_config.get('max_tokens', 1000)
        except Exception:
            self.temperature = 0.3
            self.max_tokens = 1000
        
        print(f"🤖 GPT客户端(SDK版)初始化完成，使用模型: {self.model_name}")
        
        # 验证配置
        self._validate_configuration()
    
    def _validate_configuration(self) -> None:
        """验证GPT配置"""
        if not os.getenv('OPENAI_API_KEY'):
            print("⚠️ 警告: 未设置OPENAI_API_KEY，API调用将失败")
    
    def call_api(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        调用GPT API - 系统提示词 + 用户提示词模式
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 其他参数（temperature, max_tokens等）
            
        Returns:
            AI响应文本
        """
        # 合并参数
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        model = kwargs.get('model', self.model_name)
        
        try:
            # 使用官方SDK调用API
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # 返回响应内容
            return response.choices[0].message.content
            
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower():
                raise Exception("OpenAI API Key未配置或无效")
            elif "rate_limit" in error_msg.lower():
                raise Exception("OpenAI API达到速率限制，请稍后重试")
            elif "model" in error_msg.lower():
                raise Exception(f"不支持的模型: {model}")
            else:
                raise Exception(f"OpenAI API调用失败: {error_msg}")
    
    def call_api_simple(self, prompt: str, **kwargs) -> str:
        """
        简单API调用 - 单一提示词模式
        
        Args:
            prompt: 完整提示词
            **kwargs: 其他参数
            
        Returns:
            AI响应文本
        """
        # 合并参数
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        model = kwargs.get('model', self.model_name)
        
        try:
            # 使用官方SDK调用API
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # 返回响应内容
            return response.choices[0].message.content
            
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower():
                raise Exception("OpenAI API Key未配置或无效")
            elif "rate_limit" in error_msg.lower():
                raise Exception("OpenAI API达到速率限制，请稍后重试")
            else:
                raise Exception(f"OpenAI API调用失败: {error_msg}")
    
    def call_api_stream(self, system_prompt: str, user_prompt: str, **kwargs):
        """
        流式API调用 - 支持实时响应
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 其他参数
            
        Yields:
            流式响应片段
        """
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        model = kwargs.get('model', self.model_name)
        
        try:
            # 创建流式响应
            stream = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            # 逐块返回响应
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            raise Exception(f"OpenAI流式API调用失败: {e}")