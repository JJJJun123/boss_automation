#!/usr/bin/env python3
"""
测试市场分析报告功能
验证EnhancedJobAnalyzer能正确生成市场分析数据
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer

def test_market_analysis():
    """测试市场分析报告生成"""
    print("=" * 60)
    print("🧪 测试EnhancedJobAnalyzer市场分析报告")
    print("=" * 60)
    
    # 1. 创建EnhancedJobAnalyzer实例
    print("\n1. 创建EnhancedJobAnalyzer实例...")
    try:
        analyzer = EnhancedJobAnalyzer(
            extraction_provider="glm",
            analysis_provider="deepseek"
        )
        print("   ✅ 分析器创建成功")
    except Exception as e:
        print(f"   ❌ 分析器创建失败: {e}")
        return
    
    # 2. 创建测试岗位数据
    print("\n2. 创建测试岗位数据...")
    test_jobs = [
        {
            "title": "风险管理经理",
            "company": "某银行",
            "salary": "25-35K",
            "job_description": "负责市场风险管理，需要熟悉金融衍生品，有3-5年经验",
            "job_requirements": "本科及以上学历，金融相关专业，CFA/FRM优先",
            "work_location": "上海"
        },
        {
            "title": "AI算法工程师",
            "company": "某科技公司",
            "salary": "30-50K",
            "job_description": "负责机器学习模型开发，深度学习算法优化",
            "job_requirements": "硕士及以上学历，计算机相关专业，熟悉Python/TensorFlow",
            "work_location": "北京"
        },
        {
            "title": "咨询顾问",
            "company": "某咨询公司",
            "salary": "20-30K",
            "job_description": "提供企业战略咨询服务，参与项目管理",
            "job_requirements": "本科及以上学历，有咨询行业经验优先",
            "work_location": "深圳"
        }
    ]
    print(f"   ✅ 创建了{len(test_jobs)}个测试岗位")
    
    # 3. 运行分析
    print("\n3. 运行三阶段分析...")
    try:
        analyzed_jobs = analyzer.analyze_jobs(test_jobs)
        print(f"   ✅ 分析完成，返回{len(analyzed_jobs)}个岗位")
    except Exception as e:
        print(f"   ❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. 获取市场分析报告
    print("\n4. 获取市场分析报告...")
    market_analysis = analyzer.get_market_analysis()
    
    if market_analysis:
        print("   ✅ 成功获取市场分析报告")
        print("\n   📊 报告内容：")
        
        # 检查关键字段
        if 'skill_requirements' in market_analysis:
            print(f"   - 包含技能要求: ✅")
            skill_req = market_analysis['skill_requirements']
            if 'hard_skills' in skill_req:
                hard_skills = skill_req['hard_skills']
                if 'core_required' in hard_skills and hard_skills['core_required']:
                    print(f"     核心必备技能: {len(hard_skills['core_required'])}个")
                    for skill in hard_skills['core_required'][:3]:
                        print(f"       • {skill.get('name', skill)}")
        else:
            print(f"   - 包含技能要求: ❌")
        
        if 'core_responsibilities' in market_analysis:
            responsibilities = market_analysis['core_responsibilities']
            if responsibilities:
                print(f"   - 核心职责: {len(responsibilities)}条")
                for resp in responsibilities[:3]:
                    print(f"       • {resp}")
        else:
            print(f"   - 核心职责: ❌")
        
        if 'key_findings' in market_analysis:
            findings = market_analysis['key_findings']
            if findings:
                print(f"   - 关键发现: {len(findings)}条")
                for finding in findings[:3]:
                    print(f"       • {finding}")
        else:
            print(f"   - 关键发现: ❌")
        
        if 'market_overview' in market_analysis:
            overview = market_analysis['market_overview']
            print(f"   - 市场概览: ✅")
            print(f"     分析岗位数: {overview.get('total_jobs_analyzed', 0)}")
        
        # 保存完整报告到文件
        with open('test_market_analysis_output.json', 'w', encoding='utf-8') as f:
            json.dump(market_analysis, f, ensure_ascii=False, indent=2)
        print("\n   💾 完整报告已保存到 test_market_analysis_output.json")
        
    else:
        print("   ❌ 未能获取市场分析报告")
        print("   检查market_report:", hasattr(analyzer, 'market_report'))
        if hasattr(analyzer, 'market_report'):
            print("   market_report内容:", analyzer.market_report)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_market_analysis()