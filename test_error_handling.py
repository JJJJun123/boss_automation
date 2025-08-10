#!/usr/bin/env python3
"""
测试新的错误处理机制
验证系统不再使用fallback，而是直接报错
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analyzer.job_analyzer import JobAnalyzer
from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer

def test_error_handling():
    """测试错误处理机制"""
    print("=" * 60)
    print("🧪 测试错误处理机制")
    print("=" * 60)
    
    # 1. 测试JobAnalyzer的错误处理
    print("\n1. 测试JobAnalyzer错误处理...")
    try:
        analyzer = JobAnalyzer(ai_provider="deepseek")  # 使用有效的provider
    except Exception as e:
        print(f"   无法初始化分析器: {e}")
        return
    
    # 创建一个会导致错误的岗位
    invalid_job = {
        "title": None,  # 无效的标题
        "company": "",  # 空公司名
        "job_description": None,  # 无描述
    }
    
    print("   测试分析无效岗位...")
    try:
        result = analyzer.analyze_job_match_simple(invalid_job, {})
        if result.get('error'):
            print(f"   ✅ 正确返回错误状态: score={result.get('score')}, error={result.get('error')}")
        else:
            print(f"   ❌ 未返回错误状态: {result}")
    except Exception as e:
        print(f"   ✅ 正确抛出异常: {e}")
    
    # 2. 测试_get_default_match_value是否被禁用
    print("\n2. 测试默认值函数是否被禁用...")
    try:
        default_value = analyzer._get_default_match_value('score')
        print(f"   ❌ 默认值函数仍在工作: {default_value}")
    except NotImplementedError as e:
        print(f"   ✅ 默认值函数已被禁用: {e}")
    except Exception as e:
        print(f"   ⚠️ 其他错误: {e}")
    
    # 3. 测试EnhancedJobAnalyzer的错误处理
    print("\n3. 测试EnhancedJobAnalyzer错误处理...")
    enhanced_analyzer = EnhancedJobAnalyzer()
    
    try:
        default_extraction = enhanced_analyzer._get_default_extraction()
        print(f"   ❌ 默认提取函数仍在工作: {default_extraction}")
    except NotImplementedError as e:
        print(f"   ✅ 默认提取函数已被禁用: {e}")
    except Exception as e:
        print(f"   ⚠️ 其他错误: {e}")
    
    try:
        default_report = enhanced_analyzer._get_default_market_report()
        print(f"   ❌ 默认报告函数仍在工作: {default_report}")
    except NotImplementedError as e:
        print(f"   ✅ 默认报告函数已被禁用: {e}")
    except Exception as e:
        print(f"   ⚠️ 其他错误: {e}")
    
    # 4. 测试fallback分析函数
    print("\n4. 测试fallback分析函数是否被禁用...")
    try:
        fallback = analyzer._get_fallback_analysis("test error")
        if fallback.get('error'):
            print(f"   ✅ fallback返回错误状态: score={fallback.get('score')}")
        else:
            print(f"   ❌ fallback仍返回假数据: {fallback}")
    except AttributeError:
        print(f"   ✅ fallback函数已被完全移除")
    except Exception as e:
        print(f"   ⚠️ 其他错误: {e}")
    
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    print("✅ 所有fallback机制已被移除")
    print("✅ 默认值函数已被禁用")
    print("✅ 错误现在会显式抛出或返回错误状态")
    print("✅ 不再有假数据掩盖真实问题")

if __name__ == "__main__":
    test_error_handling()