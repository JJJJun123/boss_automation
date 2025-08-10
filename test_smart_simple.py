#!/usr/bin/env python3
"""
简单测试智能分层分析器
"""

import os
import sys

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analyzer.smart_job_analyzer import SmartJobAnalyzer

def main():
    print("=" * 60)
    print("🧪 测试智能分层分析器（简化版）")
    print("=" * 60)
    
    # 创建分析器
    print("\n1. 创建分析器实例...")
    try:
        analyzer = SmartJobAnalyzer()
        print("✅ 分析器创建成功")
    except Exception as e:
        print(f"❌ 分析器创建失败: {e}")
        return
    
    # 测试岗位
    test_job = {
        "title": "风险管理经理",
        "company": "某银行",
        "salary": "25-35K",
        "job_description": "负责市场风险管理，需要3年经验",
        "link": "https://test.com/job1"
    }
    
    # 测试各个组件
    print("\n2. 测试缓存系统...")
    job_id = analyzer._generate_job_id(test_job)
    print(f"   生成的岗位ID: {job_id}")
    
    print("\n3. 测试提取提示词生成...")
    prompt = analyzer._build_batch_extract_prompt([test_job])
    print(f"   提示词长度: {len(prompt)} 字符")
    print(f"   提示词预览: {prompt[:200]}...")
    
    print("\n4. 测试评分提示词生成...")
    score_prompt = analyzer._build_batch_score_prompt([test_job], None)
    print(f"   提示词长度: {len(score_prompt)} 字符")
    
    print("\n5. 测试默认值生成...")
    default_extraction = analyzer._get_default_extraction()
    print(f"   默认提取结果: {list(default_extraction.keys())}")
    
    print("\n✅ 基础功能测试完成")
    
    # 测试简单分析（1个岗位）
    print("\n" + "=" * 60)
    print("6. 测试单岗位分析...")
    print("=" * 60)
    
    try:
        result = analyzer.analyze_jobs_smart([test_job])
        print("\n✅ 分析完成！")
        print(f"   - 总岗位数: {result['total_jobs']}")
        print(f"   - API调用: {result['cost_analysis']['total_api_calls']}次")
        print(f"   - 缓存命中: {result['cost_analysis']['cache_hits']}次")
        print(f"   - 预估成本: {result['cost_analysis']['estimated_cost']}")
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()