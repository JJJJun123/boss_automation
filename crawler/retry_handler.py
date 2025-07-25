#!/usr/bin/env python3
"""
错误处理和重试机制
提供智能重试、错误分类和恢复策略
"""

import logging
import asyncio
import time
import random
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """错误类型枚举"""
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    AUTHENTICATION_ERROR = "auth_error"
    CAPTCHA_ERROR = "captcha_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    PARSING_ERROR = "parsing_error"
    PAGE_LOAD_ERROR = "page_load_error"
    ELEMENT_NOT_FOUND = "element_not_found"
    BROWSER_ERROR = "browser_error"
    UNKNOWN_ERROR = "unknown_error"


class RetryStrategy(Enum):
    """重试策略枚举"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"
    NO_RETRY = "no_retry"


@dataclass
class RetryConfig:
    """重试配置类"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    jitter: bool = True
    backoff_multiplier: float = 2.0
    allowed_error_types: Optional[List[ErrorType]] = None
    
    def __post_init__(self):
        if self.allowed_error_types is None:
            # 默认可重试的错误类型
            self.allowed_error_types = [
                ErrorType.NETWORK_ERROR,
                ErrorType.TIMEOUT_ERROR,
                ErrorType.PAGE_LOAD_ERROR,
                ErrorType.ELEMENT_NOT_FOUND,
                ErrorType.RATE_LIMIT_ERROR
            ]


@dataclass
class ErrorContext:
    """错误上下文信息"""
    error_type: ErrorType
    original_exception: Exception
    attempt_number: int
    total_attempts: int
    elapsed_time: float
    function_name: str
    args: tuple
    kwargs: dict
    additional_info: Dict[str, Any]


class ErrorClassifier:
    """错误分类器"""
    
    @staticmethod
    def classify_error(exception: Exception, context: Dict[str, Any] = None) -> ErrorType:
        """
        分类异常类型
        
        Args:
            exception: 异常对象
            context: 上下文信息
            
        Returns:
            ErrorType: 错误类型
        """
        error_msg = str(exception).lower()
        exception_type = type(exception).__name__
        
        # 网络相关错误
        if any(keyword in error_msg for keyword in [
            'connection', 'network', 'dns', 'resolve', 'unreachable',
            'connection refused', 'connection reset', 'no route'
        ]):
            return ErrorType.NETWORK_ERROR
        
        # 超时错误
        if any(keyword in error_msg for keyword in [
            'timeout', 'timed out', 'time out', 'deadline exceeded'
        ]):
            return ErrorType.TIMEOUT_ERROR
        
        # 认证错误
        if any(keyword in error_msg for keyword in [
            'unauthorized', '401', 'forbidden', '403', 'authentication',
            'login required', 'access denied'
        ]):
            return ErrorType.AUTHENTICATION_ERROR
        
        # 验证码错误
        if any(keyword in error_msg for keyword in [
            'captcha', 'verification', 'verify', 'robot', 'challenge'
        ]):
            return ErrorType.CAPTCHA_ERROR
        
        # 限流错误
        if any(keyword in error_msg for keyword in [
            'rate limit', 'too many requests', '429', 'throttle',
            'quota exceeded', 'api limit'
        ]):
            return ErrorType.RATE_LIMIT_ERROR
        
        # 解析错误
        if any(keyword in error_msg for keyword in [
            'parse', 'json', 'xml', 'decode', 'format', 'invalid response'
        ]):
            return ErrorType.PARSING_ERROR
        
        # 页面加载错误
        if any(keyword in error_msg for keyword in [
            'page not found', '404', 'not found', 'page load',
            'navigation', 'goto failed'
        ]):
            return ErrorType.PAGE_LOAD_ERROR
        
        # 元素未找到
        if any(keyword in error_msg for keyword in [
            'element not found', 'selector', 'element is not attached',
            'no such element', 'element not visible'
        ]):
            return ErrorType.ELEMENT_NOT_FOUND
        
        # 浏览器错误
        if any(keyword in error_msg for keyword in [
            'browser', 'chrome', 'chromium', 'playwright',
            'browser closed', 'context closed'
        ]):
            return ErrorType.BROWSER_ERROR
        
        # 默认为未知错误
        return ErrorType.UNKNOWN_ERROR


class RetryHandler:
    """重试处理器"""
    
    def __init__(self, default_config: RetryConfig = None):
        self.default_config = default_config or RetryConfig()
        self.error_classifier = ErrorClassifier()
        self.retry_stats = {
            'total_retries': 0,
            'successful_retries': 0,
            'failed_operations': 0,
            'error_counts': {}
        }
    
    def calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """
        计算重试延迟时间
        
        Args:
            attempt: 当前尝试次数（从0开始）
            config: 重试配置
            
        Returns:
            float: 延迟时间（秒）
        """
        if config.strategy == RetryStrategy.IMMEDIATE:
            delay = 0
        elif config.strategy == RetryStrategy.FIXED_DELAY:
            delay = config.base_delay
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.base_delay * (attempt + 1)
        elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay * (config.backoff_multiplier ** attempt)
        else:
            delay = config.base_delay
        
        # 限制最大延迟
        delay = min(delay, config.max_delay)
        
        # 添加随机抖动
        if config.jitter and delay > 0:
            jitter_amount = delay * 0.1  # 10%的抖动
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay)  # 确保延迟非负
        
        return delay
    
    def should_retry(self, error_type: ErrorType, attempt: int, config: RetryConfig) -> bool:
        """
        判断是否应该重试
        
        Args:
            error_type: 错误类型
            attempt: 当前尝试次数
            config: 重试配置
            
        Returns:
            bool: 是否应该重试
        """
        # 检查是否超过最大尝试次数
        if attempt >= config.max_attempts:
            return False
        
        # 检查错误类型是否可重试
        if error_type not in config.allowed_error_types:
            return False
        
        return True
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        config: RetryConfig = None,
        context: Dict[str, Any] = None,
        **kwargs
    ) -> Any:
        """
        带重试机制执行函数
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            config: 重试配置
            context: 上下文信息
            **kwargs: 函数关键字参数
            
        Returns:
            Any: 函数执行结果
            
        Raises:
            Exception: 最后一次尝试的异常
        """
        retry_config = config or self.default_config
        start_time = time.time()
        last_exception = None
        
        for attempt in range(retry_config.max_attempts):
            try:
                logger.debug(f"执行 {func.__name__} - 尝试 {attempt + 1}/{retry_config.max_attempts}")
                
                # 执行函数
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # 成功执行，更新统计
                if attempt > 0:
                    self.retry_stats['successful_retries'] += 1
                    logger.info(f"✅ {func.__name__} 在第 {attempt + 1} 次尝试后成功")
                
                return result
                
            except Exception as e:
                last_exception = e
                elapsed_time = time.time() - start_time
                
                # 分类错误
                error_type = self.error_classifier.classify_error(e, context)
                
                # 创建错误上下文
                error_context = ErrorContext(
                    error_type=error_type,
                    original_exception=e,
                    attempt_number=attempt + 1,
                    total_attempts=retry_config.max_attempts,
                    elapsed_time=elapsed_time,
                    function_name=func.__name__,
                    args=args,
                    kwargs=kwargs,
                    additional_info=context or {}
                )
                
                # 更新错误统计
                self.retry_stats['error_counts'][error_type.value] = \
                    self.retry_stats['error_counts'].get(error_type.value, 0) + 1
                
                # 判断是否应该重试
                if not self.should_retry(error_type, attempt, retry_config):
                    logger.error(f"❌ {func.__name__} 失败，不重试: {error_type.value} - {e}")
                    self.retry_stats['failed_operations'] += 1
                    raise e
                
                # 计算延迟时间
                delay = self.calculate_delay(attempt, retry_config)
                
                logger.warning(
                    f"⚠️ {func.__name__} 第 {attempt + 1} 次尝试失败: {error_type.value} - {e}"
                )
                logger.info(f"🔄 将在 {delay:.2f} 秒后重试...")
                
                # 执行重试前的钩子函数
                await self._before_retry_hook(error_context)
                
                if delay > 0:
                    await asyncio.sleep(delay)
                
                self.retry_stats['total_retries'] += 1
        
        # 所有重试都失败了
        self.retry_stats['failed_operations'] += 1
        logger.error(f"❌ {func.__name__} 在 {retry_config.max_attempts} 次尝试后仍然失败")
        raise last_exception
    
    async def _before_retry_hook(self, error_context: ErrorContext) -> None:
        """重试前的钩子函数，可以执行一些恢复操作"""
        try:
            # 根据错误类型执行特定的恢复操作
            if error_context.error_type == ErrorType.RATE_LIMIT_ERROR:
                # 限流错误，增加额外延迟
                extra_delay = min(30, error_context.attempt_number * 10)
                logger.info(f"🛑 检测到限流，额外等待 {extra_delay} 秒")
                await asyncio.sleep(extra_delay)
            
            elif error_context.error_type == ErrorType.CAPTCHA_ERROR:
                # 验证码错误，建议人工处理
                logger.warning("🔒 检测到验证码，可能需要人工干预")
                await asyncio.sleep(5)
            
            elif error_context.error_type == ErrorType.AUTHENTICATION_ERROR:
                # 认证错误，清除会话
                logger.warning("🔐 检测到认证错误，可能需要重新登录")
                await asyncio.sleep(3)
            
            elif error_context.error_type == ErrorType.BROWSER_ERROR:
                # 浏览器错误，可能需要重启浏览器
                logger.warning("🌐 检测到浏览器错误，建议重启浏览器实例")
                await asyncio.sleep(2)
            
        except Exception as e:
            logger.debug(f"重试前钩子函数执行失败: {e}")
    
    def get_retry_stats(self) -> Dict[str, Any]:
        """获取重试统计信息"""
        total_operations = (
            self.retry_stats['successful_retries'] +
            self.retry_stats['failed_operations']
        )
        
        success_rate = 0.0
        if total_operations > 0:
            success_rate = (total_operations - self.retry_stats['failed_operations']) / total_operations
        
        return {
            'total_retries': self.retry_stats['total_retries'],
            'successful_retries': self.retry_stats['successful_retries'],
            'failed_operations': self.retry_stats['failed_operations'],
            'success_rate': success_rate,
            'error_counts': self.retry_stats['error_counts'].copy(),
            'most_common_error': self._get_most_common_error()
        }
    
    def _get_most_common_error(self) -> Optional[str]:
        """获取最常见的错误类型"""
        if not self.retry_stats['error_counts']:
            return None
        
        return max(self.retry_stats['error_counts'].items(), key=lambda x: x[1])[0]
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self.retry_stats = {
            'total_retries': 0,
            'successful_retries': 0,
            'failed_operations': 0,
            'error_counts': {}
        }


def retry_on_error(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    allowed_errors: List[ErrorType] = None
):
    """
    装饰器：为函数添加重试机制
    
    Args:
        max_attempts: 最大重试次数
        base_delay: 基础延迟时间
        strategy: 重试策略
        allowed_errors: 允许重试的错误类型
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                strategy=strategy,
                allowed_error_types=allowed_errors
            )
            
            handler = RetryHandler()
            return await handler.execute_with_retry(func, *args, config=config, **kwargs)
        
        return wrapper
    return decorator


# 预定义的重试配置
NETWORK_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=2.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    allowed_error_types=[ErrorType.NETWORK_ERROR, ErrorType.TIMEOUT_ERROR]
)

PARSING_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    strategy=RetryStrategy.LINEAR_BACKOFF,
    allowed_error_types=[ErrorType.PARSING_ERROR, ErrorType.ELEMENT_NOT_FOUND]
)

RATE_LIMIT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=30.0,
    strategy=RetryStrategy.LINEAR_BACKOFF,
    allowed_error_types=[ErrorType.RATE_LIMIT_ERROR]
)

NO_RETRY_CONFIG = RetryConfig(
    max_attempts=1,
    strategy=RetryStrategy.NO_RETRY,
    allowed_error_types=[]
)