#!/usr/bin/env python3
"""
测试GLM筛选功能修复
"""

import os
import sys

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer

def test_screening():
    """测试筛选功能"""
    print("=" * 60)
    print("🧪 测试GLM筛选功能修复")
    print("=" * 60)
    
    # 创建分析器（启用筛选模式）
    analyzer = EnhancedJobAnalyzer(
        extraction_provider="glm",
        analysis_provider="deepseek",
        screening_mode=True  # 启用筛选模式
    )
    
    # 测试岗位
    test_jobs = [
        {
            "title": "市场风险分析师",
            "company": "某银行",
            "salary": "20-30K",
            "job_description": "负责市场风险管理，需要金融背景",
            "link": "https://test.com/job1"
        },
        {
            "title": "AI算法工程师",
            "company": "某科技公司",
            "salary": "25-40K",
            "job_description": "负责机器学习算法研发，需要AI背景",
            "link": "https://test.com/job2"
        },
        {
            "title": "销售经理",
            "company": "某电商",
            "salary": "15-20K",
            "job_description": "负责销售团队管理，纯销售岗位",
            "link": "https://test.com/job3"
        }
    ]
    
    print(f"\n📋 测试数据：{len(test_jobs)} 个岗位")
    for i, job in enumerate(test_jobs, 1):
        print(f"   {i}. {job['title']} - {job['company']}")
    
    print("\n🔄 开始分析...")
    
    try:
        # 运行分析
        import asyncio
        market_report, analyzed_jobs = asyncio.run(
            analyzer.analyze_jobs_three_stages(test_jobs)
        )
        
        # 显示结果
        print("\n" + "=" * 60)
        print("📊 分析结果")
        print("=" * 60)
        
        # 统计相关和不相关的岗位
        relevant_count = 0
        irrelevant_count = 0
        
        for job in analyzed_jobs:
            score = job.get('analysis', {}).get('score', 0)
            if score > 0:
                relevant_count += 1
                print(f"✅ {job['title']}: {score:.1f}分 - {job.get('analysis', {}).get('reason', '')}")
            else:
                irrelevant_count += 1
                print(f"❌ {job['title']}: {score:.1f}分 - {job.get('analysis', {}).get('reason', '')}")
        
        print(f"\n📈 统计：")
        print(f"   - 相关岗位：{relevant_count}个")
        print(f"   - 不相关岗位：{irrelevant_count}个")
        
        if relevant_count > 0:
            print("\n✅ 测试通过！筛选功能正常工作")
        else:
            print("\n⚠️ 警告：没有找到相关岗位，可能仍有问题")
            
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_screening()