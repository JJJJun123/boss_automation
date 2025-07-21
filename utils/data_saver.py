#!/usr/bin/env python3
"""
增强的数据保存模块
保存所有搜索到的岗位，而不只是筛选后的结果
"""

import os
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def save_all_job_results(all_jobs, qualified_jobs, filename="data/job_results.json"):
    """
    保存所有岗位结果到JSON文件
    
    Args:
        all_jobs: 所有搜索到的岗位（包括分析后的）
        qualified_jobs: 筛选后的推荐岗位（高分岗位）
        filename: 保存的文件名
    
    Returns:
        bool: 是否保存成功
    """
    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # 构建完整的JSON数据结构
        json_data = {
            "metadata": {
                "generated_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_searched": len(all_jobs),  # 总搜索数
                "total_qualified": len(qualified_jobs),  # 合格数
                "version": "2.0.0"  # 新版本标记
            },
            "all_jobs": all_jobs,  # 所有岗位
            "qualified_jobs": qualified_jobs  # 推荐岗位
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 完整结果已保存到: {filename}")
        logger.info(f"   - 总搜索数: {len(all_jobs)}")
        logger.info(f"   - 推荐岗位: {len(qualified_jobs)}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 保存完整结果失败: {e}")
        return False


def save_legacy_format(jobs, filename="data/job_results.json"):
    """
    使用旧格式保存（向后兼容）
    
    Args:
        jobs: 要保存的岗位列表
        filename: 保存的文件名
    
    Returns:
        bool: 是否保存成功
    """
    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        json_data = {
            "metadata": {
                "generated_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_jobs": len(jobs),
                "version": "1.0.0"
            },
            "jobs": jobs
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        return True
        
    except Exception as e:
        logger.error(f"保存失败: {e}")
        return False


def load_all_job_results(filename="data/job_results.json"):
    """
    加载完整的岗位结果
    
    Args:
        filename: 要加载的文件名
    
    Returns:
        dict: 包含 all_jobs 和 qualified_jobs 的字典
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查版本，支持新旧格式
        version = data.get('metadata', {}).get('version', '1.0.0')
        
        if version == '2.0.0':
            # 新格式：直接返回
            return {
                'all_jobs': data.get('all_jobs', []),
                'qualified_jobs': data.get('qualified_jobs', []),
                'metadata': data.get('metadata', {})
            }
        else:
            # 旧格式：只有筛选后的岗位
            jobs = data.get('jobs', [])
            return {
                'all_jobs': jobs,  # 旧格式中没有区分，所以都是筛选后的
                'qualified_jobs': jobs,
                'metadata': data.get('metadata', {})
            }
            
    except FileNotFoundError:
        logger.warning(f"文件不存在: {filename}")
        return {'all_jobs': [], 'qualified_jobs': [], 'metadata': {}}
    except Exception as e:
        logger.error(f"加载失败: {e}")
        return {'all_jobs': [], 'qualified_jobs': [], 'metadata': {}}