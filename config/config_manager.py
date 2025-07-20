import os
import yaml
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import logging

class ConfigManager:
    """配置管理器 - 统一管理应用配置、用户偏好和密钥"""
    
    def __init__(self, config_dir: str = None):
        """初始化配置管理器
        
        Args:
            config_dir: 配置文件目录，默认为当前文件所在目录
        """
        if config_dir is None:
            config_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.config_dir = config_dir
        self.app_config: Dict[str, Any] = {}
        self.user_preferences: Dict[str, Any] = {}
        self.secrets: Dict[str, Any] = {}
        
        # 加载所有配置
        self._load_all_configs()
    
    def _load_all_configs(self):
        """加载所有配置文件"""
        try:
            # 加载应用配置
            self._load_app_config()
            
            # 加载用户偏好
            self._load_user_preferences()
            
            # 加载密钥配置
            self._load_secrets()
            
            logging.info("所有配置文件加载完成")
            
        except Exception as e:
            logging.error(f"配置加载失败: {e}")
            raise
    
    def _load_app_config(self):
        """加载应用配置"""
        config_path = os.path.join(self.config_dir, "app_config.yaml")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.app_config = yaml.safe_load(f) or {}
            logging.info(f"应用配置加载成功: {config_path}")
        except FileNotFoundError:
            logging.warning(f"应用配置文件不存在: {config_path}")
            self.app_config = {}
        except yaml.YAMLError as e:
            logging.error(f"应用配置文件格式错误: {e}")
            raise
    
    def _load_user_preferences(self):
        """加载用户偏好配置"""
        preferences_path = os.path.join(self.config_dir, "user_preferences.yaml")
        try:
            with open(preferences_path, 'r', encoding='utf-8') as f:
                self.user_preferences = yaml.safe_load(f) or {}
            logging.info(f"用户偏好配置加载成功: {preferences_path}")
        except FileNotFoundError:
            logging.warning(f"用户偏好配置文件不存在: {preferences_path}")
            self.user_preferences = {}
        except yaml.YAMLError as e:
            logging.error(f"用户偏好配置文件格式错误: {e}")
            raise
    
    def _load_secrets(self):
        """加载密钥配置"""
        secrets_path = os.path.join(self.config_dir, "secrets.env")
        try:
            # 加载环境变量
            load_dotenv(secrets_path)
            
            # 读取所有API密钥
            self.secrets = {
                'DEEPSEEK_API_KEY': os.getenv('DEEPSEEK_API_KEY'),
                'CLAUDE_API_KEY': os.getenv('CLAUDE_API_KEY'),
                'GEMINI_API_KEY': os.getenv('GEMINI_API_KEY'),
                'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
                'BAIDU_API_KEY': os.getenv('BAIDU_API_KEY'),
            }
            
            logging.info(f"密钥配置加载成功: {secrets_path}")
        except FileNotFoundError:
            logging.warning(f"密钥配置文件不存在: {secrets_path}")
            self.secrets = {}
    
    def get_app_config(self, key: str = None, default: Any = None) -> Any:
        """获取应用配置
        
        Args:
            key: 配置键，支持点号分隔的嵌套键如 'ai.default_provider'
            default: 默认值
            
        Returns:
            配置值
        """
        if key is None:
            return self.app_config
        
        return self._get_nested_value(self.app_config, key, default)
    
    def get_user_preference(self, key: str = None, default: Any = None) -> Any:
        """获取用户偏好配置
        
        Args:
            key: 配置键，支持点号分隔的嵌套键
            default: 默认值
            
        Returns:
            配置值
        """
        if key is None:
            return self.user_preferences
        
        return self._get_nested_value(self.user_preferences, key, default)
    
    def get_secret(self, key: str, default: Any = None) -> Any:
        """获取密钥配置
        
        Args:
            key: 密钥名称
            default: 默认值
            
        Returns:
            密钥值
        """
        return self.secrets.get(key, default)
    
    def set_user_preference(self, key: str, value: Any):
        """设置用户偏好配置
        
        Args:
            key: 配置键，支持点号分隔的嵌套键
            value: 配置值
        """
        self._set_nested_value(self.user_preferences, key, value)
    
    def save_user_preferences(self):
        """保存用户偏好配置到文件"""
        preferences_path = os.path.join(self.config_dir, "user_preferences.yaml")
        try:
            with open(preferences_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self.user_preferences, f, default_flow_style=False, 
                              allow_unicode=True, indent=2)
            logging.info(f"用户偏好配置保存成功: {preferences_path}")
        except Exception as e:
            logging.error(f"保存用户偏好配置失败: {e}")
            raise
    
    def _get_nested_value(self, data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """获取嵌套字典中的值
        
        Args:
            data: 字典数据
            key: 键，支持点号分隔
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        current = data
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        
        return current
    
    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any):
        """设置嵌套字典中的值
        
        Args:
            data: 字典数据
            key: 键，支持点号分隔
            value: 值
        """
        keys = key.split('.')
        current = data
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def get_search_config(self) -> Dict[str, Any]:
        """获取搜索相关的完整配置"""
        return {
            # 从用户偏好获取
            'keyword': self.get_user_preference('search.keyword', '市场风险管理'),
            'cities': self.get_user_preference('search.selected_cities', ['shanghai']),
            'max_jobs': self.get_user_preference('search.max_jobs', 20),
            'max_analyze_jobs': self.get_user_preference('search.max_analyze_jobs', 10),
            'fetch_details': self.get_user_preference('search.fetch_details', False),
            
            # 从应用配置获取城市映射
            'city_codes': self.get_app_config('cities', {}),
            
            # 爬虫配置
            'crawler_config': self.get_app_config('crawler', {})
        }
    
    def get_ai_config(self) -> Dict[str, Any]:
        """获取AI相关的完整配置"""
        provider = self.get_user_preference('ai_analysis.provider', 'deepseek')
        
        return {
            'provider': provider,
            'api_key': self.get_secret(f'{provider.upper()}_API_KEY'),
            'model_config': self.get_app_config(f'ai.models.{provider}', {}),
            'min_score': self.get_user_preference('ai_analysis.min_score', 6),
            'personal_profile': self.get_user_preference('personal_profile', {})
        }
    
    def validate_config(self) -> bool:
        """验证配置的完整性和有效性
        
        Returns:
            True如果配置有效，否则False
        """
        errors = []
        
        # 检查必需的API密钥
        provider = self.get_user_preference('ai_analysis.provider', 'deepseek')
        api_key = self.get_secret(f'{provider.upper()}_API_KEY')
        
        if not api_key or api_key == f'your_{provider}_api_key_here':
            errors.append(f"缺少有效的{provider.upper()} API密钥")
        
        # 检查搜索配置
        keyword = self.get_user_preference('search.keyword')
        if not keyword:
            errors.append("搜索关键词不能为空")
        
        cities = self.get_user_preference('search.selected_cities', [])
        if not cities:
            errors.append("至少需要选择一个城市")
        
        if errors:
            for error in errors:
                logging.error(f"配置验证失败: {error}")
            return False
        
        return True