#!/usr/bin/env python3
"""
简历信息管理器
负责简历信息的持久化存储和读取
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ResumeManager:
    """简历信息管理器"""
    
    def __init__(self):
        """初始化简历管理器"""
        # 创建data目录（如果不存在）
        self.data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
            'data'
        )
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 简历信息文件路径
        self.resume_file = os.path.join(self.data_dir, 'resume_profile.json')
        
        # 当前简历信息缓存
        self._current_resume: Optional[Dict[str, Any]] = None
        
        # 加载已有的简历信息
        self.load_resume()
    
    def save_resume(self, resume_data: Dict[str, Any]) -> bool:
        """
        保存简历信息到文件
        
        Args:
            resume_data: 简历数据字典，包含AI解析的所有信息
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 添加元数据
            resume_data['last_updated'] = datetime.now().isoformat()
            resume_data['version'] = '2.0'
            
            # 保存到文件
            with open(self.resume_file, 'w', encoding='utf-8') as f:
                json.dump(resume_data, f, ensure_ascii=False, indent=2)
            
            # 更新缓存
            self._current_resume = resume_data
            
            logger.info(f"简历信息已保存到 {self.resume_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存简历信息失败: {e}")
            return False
    
    def load_resume(self) -> Optional[Dict[str, Any]]:
        """
        从文件加载简历信息
        
        Returns:
            Dict或None: 简历数据字典，如果不存在则返回None
        """
        try:
            if os.path.exists(self.resume_file):
                with open(self.resume_file, 'r', encoding='utf-8') as f:
                    self._current_resume = json.load(f)
                logger.info(f"已加载简历信息，最后更新: {self._current_resume.get('last_updated', '未知')}")
                return self._current_resume
            else:
                logger.info("未找到已保存的简历信息")
                return None
                
        except Exception as e:
            logger.error(f"加载简历信息失败: {e}")
            return None
    
    def get_current_resume(self) -> Optional[Dict[str, Any]]:
        """
        获取当前的简历信息
        
        Returns:
            Dict或None: 当前的简历数据
        """
        return self._current_resume
    
    def has_resume(self) -> bool:
        """
        检查是否有已保存的简历信息
        
        Returns:
            bool: 是否存在简历信息
        """
        return self._current_resume is not None
    
    def get_personal_profile(self) -> Dict[str, Any]:
        """
        获取个人信息用于岗位匹配
        
        Returns:
            Dict: 包含技能、经验、求职意向等信息
        """
        if not self._current_resume:
            return {}
        
        # 构建用于岗位匹配的profile - 适配新的LangGPT格式
        profile = {
            'name': self._current_resume.get('basic_info', {}).get('name', '未知'),
            'skills': self._current_resume.get('skills', []),
            'experience_years': self._current_resume.get('experience_years', 0),
            'education': self._current_resume.get('education_info', {}),
            'work_experience': self._current_resume.get('work_experience', []),
            'strengths': self._current_resume.get('strengths', []),
            'weaknesses': self._current_resume.get('weaknesses', []),  # 新增劣势字段
            'job_intentions': self._current_resume.get('job_intentions', []),
            'salary_expectations': self._current_resume.get('salary_expectations', {}),
            'resume_core': self._current_resume.get('resume_core', {}),  # 新增结构化数据
            'resume_text': self._current_resume.get('resume_text', '')  # 原始简历文本
        }
        
        return profile
    
    def update_job_intentions(self, intentions: list) -> bool:
        """
        更新求职意向
        
        Args:
            intentions: 求职意向列表
            
        Returns:
            bool: 更新是否成功
        """
        if not self._current_resume:
            logger.error("没有简历信息可更新")
            return False
        
        self._current_resume['job_intentions'] = intentions
        return self.save_resume(self._current_resume)
    
    def update_salary_expectations(self, min_salary: int, max_salary: int) -> bool:
        """
        更新薪资期望
        
        Args:
            min_salary: 最低期望薪资
            max_salary: 最高期望薪资
            
        Returns:
            bool: 更新是否成功
        """
        if not self._current_resume:
            logger.error("没有简历信息可更新")
            return False
        
        self._current_resume['salary_expectations'] = {
            'min': min_salary,
            'max': max_salary
        }
        return self.save_resume(self._current_resume)
    
    def clear_resume(self) -> bool:
        """
        清除简历信息
        
        Returns:
            bool: 清除是否成功
        """
        try:
            if os.path.exists(self.resume_file):
                os.remove(self.resume_file)
            self._current_resume = None
            logger.info("简历信息已清除")
            return True
        except Exception as e:
            logger.error(f"清除简历信息失败: {e}")
            return False