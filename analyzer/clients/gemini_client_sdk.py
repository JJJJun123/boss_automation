#!/usr/bin/env python3
"""
Gemini API客户端 - 使用官方Google Generative AI SDK
纯API调用器，不包含任何业务逻辑和提示词
"""

import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from ..base_client import BaseAIClient

# 加载配置文件中的环境变量
config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config')
secrets_file = os.path.join(config_dir, 'secrets.env')
load_dotenv(secrets_file)
logger = logging.getLogger(__name__)

# 导入Google Generative AI SDK
try:
    import google.generativeai as genai
    GOOGLE_SDK_AVAILABLE = True
except ImportError:
    GOOGLE_SDK_AVAILABLE = False
    logger.warning("Google Generative AI SDK未安装，请运行: pip install google-generativeai")


class GeminiClientSDK(BaseAIClient):
    """Gemini API客户端 - 使用官方SDK"""
    
    def __init__(self, model_name: Optional[str] = None):
        """
        初始化Gemini客户端
        
        Args:
            model_name: 模型名称，默认使用gemini-pro
        """
        super().__init__(model_name)
        
        if not GOOGLE_SDK_AVAILABLE:
            raise ImportError("Google Generative AI SDK未安装，请运行: pip install google-generativeai")
        
        # 设置默认模型
        if not self.model_name:
            try:
                from config.config_manager import ConfigManager
                config_manager = ConfigManager()
                self.model_name = config_manager.get_app_config('ai.models.gemini.model_name', 'gemini-pro')
            except Exception:
                self.model_name = 'gemini-pro'
        
        # 初始化Google Generative AI
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.warning("未设置GEMINI_API_KEY，请在config/secrets.env文件中配置")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.model_name)
        
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
        
        logger.debug(f"Gemini客户端(SDK版)初始化完成，使用模型: {self.model_name}")
        
        # 验证配置
        self._validate_configuration()
    
    def _validate_configuration(self) -> None:
        """验证Gemini配置"""
        if not os.getenv('GEMINI_API_KEY'):
            logger.warning("未设置GEMINI_API_KEY，API调用将失败")
    
    def call_api(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        调用Gemini API - 系统提示词 + 用户提示词模式
        
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
        
        # Gemini将系统提示词和用户提示词合并
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # 创建生成配置
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens
        )
        
        try:
            # 使用官方SDK调用API
            response = self.model.generate_content(
                combined_prompt,
                generation_config=generation_config
            )
            
            # 返回响应内容
            return response.text
            
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                raise Exception("Gemini API Key未配置或无效")
            elif "quota" in error_msg.lower() or "rate" in error_msg.lower():
                raise Exception("Gemini API配额不足或达到速率限制，请稍后重试")
            elif "model" in error_msg.lower():
                raise Exception(f"不支持的模型: {self.model_name}")
            else:
                raise Exception(f"Gemini API调用失败: {error_msg}")
    
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
        
        # 创建生成配置
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens
        )
        
        try:
            # 使用官方SDK调用API
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # 返回响应内容
            return response.text
            
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                raise Exception("Gemini API Key未配置或无效")
            elif "quota" in error_msg.lower() or "rate" in error_msg.lower():
                raise Exception("Gemini API配额不足或达到速率限制，请稍后重试")
            else:
                raise Exception(f"Gemini API调用失败: {error_msg}")
    
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
        
        # Gemini将系统提示词和用户提示词合并
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # 创建生成配置
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens
        )
        
        try:
            # 创建流式响应
            response = self.model.generate_content(
                combined_prompt,
                generation_config=generation_config,
                stream=True
            )
            
            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            raise Exception(f"Gemini流式API调用失败: {e}")