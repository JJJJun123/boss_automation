#!/usr/bin/env python3
"""
AI客户端工厂 - 重构为使用统一的AI服务架构
支持快速创建AI服务实例，使用统一的提示词模板和纯API客户端
"""

import os
from dotenv import load_dotenv
from .ai_service import AIService, create_ai_service

load_dotenv()


class AIClientFactory:
    @staticmethod
    def create_client(provider=None, model_name=None):
        """
        创建AI服务实例（兼容旧版本接口）
        
        Args:
            provider: AI提供商名称
            model_name: 模型名称
            
        Returns:
            AIService实例
        """
        # 使用新的统一AI服务
        return create_ai_service(provider, model_name)
    
    @staticmethod
    def create_ai_service(provider=None, model_name=None):
        """
        创建AI服务实例（推荐使用的新接口）
        
        Args:
            provider: AI提供商名称
            model_name: 模型名称
            
        Returns:
            AIService实例
        """
        return create_ai_service(provider, model_name)
    
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
        AIService实例
    """
    return create_ai_service(provider, model_name)