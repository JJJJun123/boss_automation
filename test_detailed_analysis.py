#!/usr/bin/env python3
"""
测试详细匹配分析功能
验证无简历时也能获得详细的分析结果
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer

def test_detailed_analysis():
    """测试详细分析功能"""
    print("=" * 60)
    print("🧪 测试详细匹配分析（无简历模式）")
    print("=" * 60)
    
    # 1. 创建分析器
    print("\n1. 创建EnhancedJobAnalyzer...")
    try:
        analyzer = EnhancedJobAnalyzer(
            extraction_provider="glm",
            analysis_provider="deepseek"
        )
        print("   ✅ 分析器创建成功")
    except Exception as e:
        print(f"   ❌ 创建失败: {e}")
        return
    
    # 2. 创建测试岗位
    print("\n2. 创建测试岗位...")
    test_job = {
        "title": "Python后端开发工程师",
        "company": "某科技公司",
        "salary": "20-30K",
        "job_description": """
        职责：
        1. 负责后端服务开发，使用Python/Django框架
        2. 设计和优化数据库结构
        3. 编写高质量的代码和技术文档
        4. 参与产品需求评审和技术方案设计
        """,
        "job_requirements": """
        要求：
        1. 本科及以上学历，计算机相关专业
        2. 3年以上Python开发经验
        3. 熟练掌握Django/Flask框架
        4. 熟悉MySQL、Redis等数据库
        5. 了解Docker、K8s等容器技术（加分项）
        6. 有微服务架构经验（加分项）
        """,
        "work_location": "上海"
    }
    
    # 3. 测试无简历分析
    print("\n3. 测试无简历模式的详细分析...")
    print("   （确认没有上传简历）")
    
    # 确保没有简历数据
    analyzer.resume_analysis = None
    
    try:
        # 分析单个岗位
        analyzed_jobs = analyzer.analyze_jobs([test_job])
        
        if analyzed_jobs and len(analyzed_jobs) > 0:
            job_result = analyzed_jobs[0]
            analysis = job_result.get('analysis', {})
            
            print("\n   📊 分析结果：")
            print(f"   总体评分: {analysis.get('overall_score', 0)}/10")
            print(f"   推荐级别: {analysis.get('recommendation', '未知')}")
            print(f"   优先级: {analysis.get('priority_level', '未知')}")
            
            # 检查新增字段
            if 'matched_skills' in analysis:
                print(f"\n   ✅ 匹配技能: {', '.join(analysis['matched_skills'][:3]) if analysis['matched_skills'] else '无'}")
            
            if 'missing_skills' in analysis:
                print(f"   ❌ 缺失技能: {', '.join(analysis['missing_skills'][:3]) if analysis['missing_skills'] else '无'}")
            
            if 'extra_advantages' in analysis:
                print(f"   ⭐ 额外优势: {', '.join(analysis['extra_advantages'][:3]) if analysis['extra_advantages'] else '无'}")
            
            if 'skill_coverage_detail' in analysis:
                print(f"\n   📋 技能覆盖: {analysis['skill_coverage_detail']}")
            
            # 检查维度评分
            if 'dimension_scores' in analysis:
                print("\n   📈 维度评分:")
                scores = analysis['dimension_scores']
                new_dimensions = ['skill_coverage', 'keyword_match', 'hard_requirements']
                for dim in new_dimensions:
                    if dim in scores:
                        print(f"      {dim}: {scores[dim]}/10")
            
            # 检查面试建议
            if 'interview_preparation' in analysis:
                print(f"\n   💡 面试准备建议: {len(analysis['interview_preparation'])}条")
                for tip in analysis['interview_preparation'][:2]:
                    print(f"      • {tip}")
            
            # 保存完整结果
            with open('test_detailed_analysis_output.json', 'w', encoding='utf-8') as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2)
            print("\n   💾 完整结果已保存到 test_detailed_analysis_output.json")
            
        else:
            print("   ❌ 没有返回分析结果")
            
    except Exception as e:
        print(f"   ❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_detailed_analysis()