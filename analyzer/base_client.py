#!/usr/bin/env python3
"""
AI客户端抽象基类
定义统一的接口，所有AI客户端都必须实现这些方法
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseAIClient(ABC):
    """AI客户端抽象基类"""
    
    def __init__(self, model_name: Optional[str] = None):
        """
        初始化AI客户端
        
        Args:
            model_name: 模型名称，如果为None则使用默认模型
        """
        self.model_name = model_name
        # 注意：_validate_configuration() 应在子类中的__init__最后调用
    
    @abstractmethod
    def call_api(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        调用AI API - 系统提示词 + 用户提示词模式
        
        Args:
            system_prompt: 系统提示词（定义AI的角色和行为）
            user_prompt: 用户提示词（具体的任务和数据）
            **kwargs: 其他API参数（如temperature, max_tokens等）
            
        Returns:
            AI的响应文本
            
        Raises:
            Exception: API调用失败时抛出异常
        """
        pass
    
    @abstractmethod
    def call_api_simple(self, prompt: str, **kwargs) -> str:
        """
        简单API调用 - 单一提示词模式
        
        Args:
            prompt: 完整的提示词
            **kwargs: 其他API参数
            
        Returns:
            AI的响应文本
            
        Raises:
            Exception: API调用失败时抛出异常
        """
        pass
    
    @abstractmethod
    def _validate_configuration(self) -> None:
        """
        验证客户端配置（API Key等）
        
        Raises:
            Exception: 配置无效时抛出异常
        """
        pass
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            包含模型名称、提供商等信息的字典
        """
        return {
            "model_name": self.model_name,
            "provider": self.__class__.__name__.replace("Client", "").lower(),
            "max_tokens": getattr(self, "max_tokens", 1000),
            "temperature": getattr(self, "temperature", 0.3)
        }
    
    def test_connection(self) -> bool:
        """
        测试API连接
        
        Returns:
            连接成功返回True，否则返回False
        """
        try:
            response = self.call_api_simple("Hello", max_tokens=10)
            return bool(response and len(response.strip()) > 0)
        except Exception:
            return False