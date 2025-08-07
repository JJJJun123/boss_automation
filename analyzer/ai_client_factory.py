#!/usr/bin/env python3
"""
AI客户端工厂 - 简化版，直接创建纯净的AI客户端
移除AIService中间层，直接创建API客户端
"""

import os
from dotenv import load_dotenv

load_dotenv()


class AIClientFactory:
    @staticmethod
    def create_client(provider=None, model_name=None):
        """
        直接创建纯净的AI客户端（重构后的简化版本）
        
        Args:
            provider: AI提供商名称
            model_name: 模型名称
            
        Returns:
            具体的AI客户端实例（不再是AIService）
        """
        return AIClientFactory.create_pure_client(provider, model_name)
    
    @staticmethod
    def create_pure_client(provider=None, model_name=None, use_sdk=True):
        """
        创建纯净的AI客户端，跳过AIService包装层
        
        Args:
            provider: AI提供商名称
            model_name: 模型名称
            use_sdk: 是否使用官方SDK（默认True，如果SDK可用）
            
        Returns:
            具体的AI客户端实例
        """
        # 设置默认提供商
        if not provider:
            try:
                from config.config_manager import ConfigManager
                config_manager = ConfigManager()
                provider = config_manager.get_app_config('ai.default_provider', 'deepseek')
            except Exception:
                provider = 'deepseek'
        
        provider = provider.lower()
        
        # 根据提供商和SDK可用性选择客户端
        if provider == "deepseek":
            from .clients.deepseek_client import DeepSeekClient
            return DeepSeekClient(model_name)
            
        elif provider == "claude":
            if use_sdk:
                try:
                    from .clients.claude_client_sdk import ClaudeClientSDK
                    return ClaudeClientSDK(model_name)
                except ImportError:
                    print("⚠️ Claude SDK不可用，回退到HTTP客户端")
            from .clients.claude_client import ClaudeClient
            return ClaudeClient(model_name)
            
        elif provider == "gemini":
            if use_sdk:
                try:
                    from .clients.gemini_client_sdk import GeminiClientSDK
                    return GeminiClientSDK(model_name)
                except ImportError:
                    print("⚠️ Google Generative AI SDK不可用，回退到HTTP客户端")
            from .clients.gemini_client import GeminiClient
            return GeminiClient(model_name)
            
        elif provider in ["gpt", "openai"]:
            if use_sdk:
                try:
                    from .clients.gpt_client_sdk import GPTClientSDK
                    return GPTClientSDK(model_name)
                except ImportError:
                    print("⚠️ OpenAI SDK不可用，回退到HTTP客户端")
            from .clients.gpt_client import GPTClient
            return GPTClient(model_name)
            
        elif provider == "glm":
            from .clients.glm_client import GLMClient
            return GLMClient(model_name)
            
        else:
            raise ValueError(f"不支持的AI提供商: {provider}")
    
    @staticmethod
    def get_available_models():
        """获取所有可用的AI模型配置"""
        return {
            'deepseek': {
                'models': ['deepseek-chat', 'deepseek-reasoner'],
                'display_name': 'DeepSeek',
                'default_model': 'deepseek-chat'
            },
            'claude': {
                'models': ['claude-3-5-sonnet-20241022', 'claude-3-haiku-20240307'],
                'display_name': 'Claude',
                'default_model': 'claude-3-5-sonnet-20241022'
            },
            'gpt': {
                'models': ['gpt-4o', 'gpt-4o-mini'],
                'display_name': 'GPT',
                'default_model': 'gpt-4o'
            },
            'gemini': {
                'models': ['gemini-pro', 'gemini-pro-vision'],
                'display_name': 'Gemini',
                'default_model': 'gemini-pro'
            },
            'glm': {
                'models': ['glm-4.5', 'glm-4.5-air', 'glm-4'],
                'display_name': 'GLM',
                'default_model': 'glm-4.5'
            }
        }


# 兼容性工厂方法，支持旧版本代码
def create_ai_client(provider=None, model_name=None):
    """
    创建AI客户端（兼容旧版本）
    
    Args:
        provider: AI提供商名称
        model_name: 模型名称
        
    Returns:
        纯净的AI客户端实例
    """
    return AIClientFactory.create_pure_client(provider, model_name)