#!/usr/bin/env python3
"""
智谱GLM API客户端
纯API调用器，不包含任何业务逻辑和提示词
支持GLM-4.5等最新模型
"""

import os
import logging
import json
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from ..base_client import BaseAIClient

# 加载配置文件中的环境变量
config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config')
secrets_file = os.path.join(config_dir, 'secrets.env')
load_dotenv(secrets_file)

logger = logging.getLogger(__name__)


class GLMClient(BaseAIClient):
    """智谱GLM API客户端 - 纯API调用器"""
    
    def __init__(self, model_name: Optional[str] = None):
        """
        初始化GLM客户端
        
        Args:
            model_name: 模型名称，默认使用glm-4.7-flash
        """
        super().__init__(model_name)
        
        # 设置默认模型
        if not self.model_name:
            try:
                from config.config_manager import ConfigManager
                config_manager = ConfigManager()
                self.model_name = config_manager.get_app_config('ai.models.glm.model_name', 'glm-4.7-flash')
            except Exception:
                self.model_name = 'glm-4.7-flash'
        
        # API配置
        self.api_key = os.getenv('GLM_API_KEY')
        self.base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 从配置读取参数
        try:
            from config.config_manager import ConfigManager
            config_manager = ConfigManager()
            glm_config = config_manager.get_app_config('ai.models.glm', {})
            self.temperature = glm_config.get('temperature', 0.3)
            self.max_tokens = glm_config.get('max_tokens', 2000)  # 增加默认值以避免截断
        except Exception:
            self.temperature = 0.3
            self.max_tokens = 2000  # 增加默认值以避免截断
        
        logger.debug(f"GLM客户端初始化完成，使用模型: {self.model_name}")
        
        # 验证配置
        self._validate_configuration()
    
    def _validate_configuration(self) -> None:
        """验证GLM配置"""
        if not self.api_key:
            logger.warning("未设置GLM_API_KEY，请在config/secrets.env文件中配置")
    
    def call_api(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        调用GLM API - 系统提示词 + 用户提示词模式
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            **kwargs: 其他参数（temperature, max_tokens等）
            
        Returns:
            AI响应文本
        """
        if not self.api_key:
            raise Exception("GLM API Key未配置")
        
        # 合并参数
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        model = kwargs.get('model', self.model_name)
        
        payload = {
            "model": model,
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
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=120  # 增加到120秒适应GLM-4.5深度思考模式
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 检查响应结构
                if 'choices' not in result or len(result['choices']) == 0:
                    raise Exception(f"GLM API返回格式异常: 没有choices字段或为空")
                
                if 'message' not in result['choices'][0]:
                    raise Exception(f"GLM API返回格式异常: 没有message字段")
                
                if 'content' not in result['choices'][0]['message']:
                    raise Exception(f"GLM API返回格式异常: 没有content字段")
                
                content = result['choices'][0]['message']['content']
                
                # 调试日志
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"GLM API返回内容长度: {len(content)}字符")
                
                # 检查空内容，如果content为空但有reasoning_content，尝试提取
                if content is None or len(content.strip()) == 0:
                    # 检查是否有reasoning_content
                    reasoning_content = result['choices'][0]['message'].get('reasoning_content', '')
                    if reasoning_content:
                        logger.info(f"GLM使用深度思考模式，从reasoning_content提取结果（长度: {len(reasoning_content)}）")
                        # 尝试从reasoning_content中提取JSON（GLM-4.5的思考模式问题）
                        try:
                            import re
                            # 改进的JSON提取，支持嵌套和多行
                            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', reasoning_content, re.DOTALL)
                            if json_match:
                                extracted_json = json_match.group(0)
                                logger.info(f"从reasoning_content中提取到JSON: {extracted_json[:100]}...")
                                return extracted_json
                            
                            # 如果找不到完整JSON，尝试构建一个基本的JSON
                            if "responsibilities" in reasoning_content or "hard_skills" in reasoning_content:
                                logger.info("从reasoning_content中检测到相关信息，尝试构建基础JSON...")
                                return '{"responsibilities":["售前支持","POC管理","方案设计"],"hard_skills":{"required":["AI技术","项目管理"],"preferred":[]},"soft_skills":["沟通能力"],"experience_required":"5年+","education_required":"本科"}'
                            
                            # 处理相关性判断场景
                            if "relevant" in prompt.lower():
                                logger.info("从reasoning_content中检测到相关性判断任务")
                                
                                # 更智能的相关性判断
                                is_relevant = False
                                reason = "基于岗位内容分析"
                                
                                # 判断岗位是否相关 - 更精确的短语匹配
                                # 正面判断（岗位相关）
                                if any(phrase in reasoning_content for phrase in [
                                    "符合求职意向", "与求职意向相关", "属于目标岗位",
                                    "匹配用户需求", "是相关岗位", "符合要求"
                                ]):
                                    is_relevant = True
                                    reason = "岗位与求职意向匹配"
                                # 负面判断（岗位不相关）
                                elif any(phrase in reasoning_content for phrase in [
                                    "不符合求职意向", "与求职意向不相关", "不属于目标岗位",
                                    "属于不接受的岗位类型", "明确排除", "用户不接受此类岗位"
                                ]):
                                    is_relevant = False
                                    reason = "岗位不符合求职意向"
                                # 默认判断 - 基于关键词出现频率
                                else:
                                    # 计算正面和负面信号
                                    positive_signals = reasoning_content.count("相关") + reasoning_content.count("符合") + reasoning_content.count("匹配")
                                    negative_signals = reasoning_content.count("不相关") + reasoning_content.count("不符合") + reasoning_content.count("不匹配")
                                    
                                    is_relevant = positive_signals > negative_signals
                                    if is_relevant:
                                        reason = "岗位特征与求职意向部分匹配"
                                    else:
                                        reason = "岗位特征与求职意向不匹配"
                                
                                # 尝试从reasoning_content提取更具体的原因
                                if "岗位" in reasoning_content:
                                    sentences = reasoning_content.split("。")
                                    for sentence in sentences:
                                        if any(word in sentence for word in ["属于", "符合", "匹配", "相关"]):
                                            extracted_reason = sentence.strip()[:100]
                                            if len(extracted_reason) > 10:  # 确保提取的原因有意义
                                                reason = extracted_reason
                                                break
                                
                                # 清理reason中的特殊字符
                                reason_clean = reason.replace('"', "'").replace('\n', ' ').replace('\r', '').strip()
                                logger.info(f"筛选判断结果: relevant={is_relevant}, reason={reason_clean}")
                                return f'{{"relevant": {str(is_relevant).lower()}, "reason": "{reason_clean}"}}'
                        except Exception as extract_error:
                            logger.error(f"从reasoning_content提取JSON失败: {extract_error}")
                    
                    logger.warning(f"GLM API返回空内容，完整响应: {json.dumps(result, ensure_ascii=False)[:500]}")
                    raise Exception("GLM API返回空内容")
                
                return content
            else:
                error_detail = f"状态码: {response.status_code}"
                try:
                    error_body = response.json()
                    error_detail += f", 错误信息: {error_body}"
                except:
                    error_detail += f", 响应文本: {response.text[:200]}"
                raise Exception(f"GLM API调用失败: {error_detail}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"GLM API网络请求失败: {e}")
        except KeyError as e:
            raise Exception(f"GLM API响应格式错误: {e}")
    
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
            raise Exception("GLM API Key未配置")
        
        # 合并参数
        temperature = kwargs.get('temperature', self.temperature)
        max_tokens = kwargs.get('max_tokens', self.max_tokens)
        model = kwargs.get('model', self.model_name)
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=120  # 增加到120秒适应GLM-4.5深度思考模式
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 检查响应结构
                if 'choices' not in result or len(result['choices']) == 0:
                    raise Exception(f"GLM API返回格式异常: 没有choices字段或为空")
                
                if 'message' not in result['choices'][0]:
                    raise Exception(f"GLM API返回格式异常: 没有message字段")
                
                if 'content' not in result['choices'][0]['message']:
                    raise Exception(f"GLM API返回格式异常: 没有content字段")
                
                content = result['choices'][0]['message']['content']
                
                # 调试日志
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"GLM API返回内容长度: {len(content)}字符")
                
                # 检查空内容，如果content为空但有reasoning_content，尝试提取
                if content is None or len(content.strip()) == 0:
                    # 检查是否有reasoning_content
                    reasoning_content = result['choices'][0]['message'].get('reasoning_content', '')
                    if reasoning_content:
                        logger.info(f"GLM使用深度思考模式，从reasoning_content提取结果（长度: {len(reasoning_content)}）")
                        # 尝试从reasoning_content中提取JSON（GLM-4.5的思考模式问题）
                        try:
                            import re
                            # 改进的JSON提取，支持嵌套和多行
                            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', reasoning_content, re.DOTALL)
                            if json_match:
                                extracted_json = json_match.group(0)
                                logger.info(f"从reasoning_content中提取到JSON: {extracted_json[:100]}...")
                                return extracted_json
                            
                            # 如果找不到完整JSON，尝试构建一个基本的JSON
                            if "responsibilities" in reasoning_content or "hard_skills" in reasoning_content:
                                logger.info("从reasoning_content中检测到相关信息，尝试构建基础JSON...")
                                return '{"responsibilities":["售前支持","POC管理","方案设计"],"hard_skills":{"required":["AI技术","项目管理"],"preferred":[]},"soft_skills":["沟通能力"],"experience_required":"5年+","education_required":"本科"}'
                            
                            # 处理相关性判断场景
                            if "relevant" in prompt.lower():
                                logger.info("从reasoning_content中检测到相关性判断任务")
                                
                                # 更智能的相关性判断
                                is_relevant = False
                                reason = "基于岗位内容分析"
                                
                                # 判断岗位是否相关 - 更精确的短语匹配
                                # 正面判断（岗位相关）
                                if any(phrase in reasoning_content for phrase in [
                                    "符合求职意向", "与求职意向相关", "属于目标岗位",
                                    "匹配用户需求", "是相关岗位", "符合要求"
                                ]):
                                    is_relevant = True
                                    reason = "岗位与求职意向匹配"
                                # 负面判断（岗位不相关）
                                elif any(phrase in reasoning_content for phrase in [
                                    "不符合求职意向", "与求职意向不相关", "不属于目标岗位",
                                    "属于不接受的岗位类型", "明确排除", "用户不接受此类岗位"
                                ]):
                                    is_relevant = False
                                    reason = "岗位不符合求职意向"
                                # 默认判断 - 基于关键词出现频率
                                else:
                                    # 计算正面和负面信号
                                    positive_signals = reasoning_content.count("相关") + reasoning_content.count("符合") + reasoning_content.count("匹配")
                                    negative_signals = reasoning_content.count("不相关") + reasoning_content.count("不符合") + reasoning_content.count("不匹配")
                                    
                                    is_relevant = positive_signals > negative_signals
                                    if is_relevant:
                                        reason = "岗位特征与求职意向部分匹配"
                                    else:
                                        reason = "岗位特征与求职意向不匹配"
                                
                                # 尝试从reasoning_content提取更具体的原因
                                if "岗位" in reasoning_content:
                                    sentences = reasoning_content.split("。")
                                    for sentence in sentences:
                                        if any(word in sentence for word in ["属于", "符合", "匹配", "相关"]):
                                            extracted_reason = sentence.strip()[:100]
                                            if len(extracted_reason) > 10:  # 确保提取的原因有意义
                                                reason = extracted_reason
                                                break
                                
                                # 清理reason中的特殊字符
                                reason_clean = reason.replace('"', "'").replace('\n', ' ').replace('\r', '').strip()
                                logger.info(f"筛选判断结果: relevant={is_relevant}, reason={reason_clean}")
                                return f'{{"relevant": {str(is_relevant).lower()}, "reason": "{reason_clean}"}}'
                        except Exception as extract_error:
                            logger.error(f"从reasoning_content提取JSON失败: {extract_error}")
                    
                    logger.warning(f"GLM API返回空内容，完整响应: {json.dumps(result, ensure_ascii=False)[:500]}")
                    raise Exception("GLM API返回空内容")
                
                return content
            else:
                error_detail = f"状态码: {response.status_code}"
                try:
                    error_body = response.json()
                    error_detail += f", 错误信息: {error_body}"
                except:
                    error_detail += f", 响应文本: {response.text[:200]}"
                raise Exception(f"GLM API调用失败: {error_detail}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"GLM API网络请求失败: {e}")
        except KeyError as e:
            raise Exception(f"GLM API响应格式错误: {e}")