#!/usr/bin/env python3
"""
AI系统重构验证测试
验证重构后的结果与基准数据是否一致
"""

import os
import sys
import json
import asyncio
from typing import Dict, Any
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analyzer.job_analyzer import JobAnalyzer

# 从基准数据文件读取测试样本
def load_baseline_data():
    """加载基准数据"""
    baseline_file = "data/ai_baseline_20250807_130703.json"
    
    if not os.path.exists(baseline_file):
        print(f"❌ 基准数据文件不存在: {baseline_file}")
        return None
    
    with open(baseline_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def compare_analysis_results(baseline_result, new_result, test_name):
    """比较分析结果"""
    print(f"\n🔍 对比测试: {test_name}")
    print("=" * 50)
    
    # 提取关键字段进行比较
    if isinstance(baseline_result, list) and len(baseline_result) > 0:
        # JobAnalyzer返回的是列表，取第一个元素的分析结果
        baseline_analysis = baseline_result[0].get('analysis', {})
    elif isinstance(baseline_result, dict) and 'analysis' in baseline_result:
        baseline_analysis = baseline_result['analysis']
    else:
        baseline_analysis = baseline_result
    
    if isinstance(new_result, list) and len(new_result) > 0:
        new_analysis = new_result[0].get('analysis', {})
    elif isinstance(new_result, dict) and 'analysis' in new_result:
        new_analysis = new_result['analysis']
    else:
        new_analysis = new_result
    
    # 比较关键指标
    comparisons = []
    
    # 比较总分
    baseline_score = baseline_analysis.get('overall_score', 0)
    new_score = new_analysis.get('overall_score', 0)
    score_diff = abs(float(baseline_score) - float(new_score))
    comparisons.append(("overall_score", baseline_score, new_score, score_diff))
    
    # 比较推荐等级
    baseline_rec = baseline_analysis.get('recommendation', '')
    new_rec = new_analysis.get('recommendation', '')
    rec_match = baseline_rec == new_rec
    comparisons.append(("recommendation", baseline_rec, new_rec, rec_match))
    
    # 比较维度评分（如果存在）
    if 'dimension_scores' in baseline_analysis and 'dimension_scores' in new_analysis:
        baseline_dims = baseline_analysis['dimension_scores']
        new_dims = new_analysis['dimension_scores']
        
        for dim in ['job_match', 'skill_match', 'experience_match']:
            if dim in baseline_dims and dim in new_dims:
                baseline_dim_score = baseline_dims[dim]
                new_dim_score = new_dims[dim] 
                dim_diff = abs(float(baseline_dim_score) - float(new_dim_score))
                comparisons.append((f"dimension.{dim}", baseline_dim_score, new_dim_score, dim_diff))
    
    # 输出对比结果
    print("📊 对比结果:")
    all_passed = True
    
    for metric, baseline_val, new_val, diff_or_match in comparisons:
        if metric == "recommendation":
            status = "✅" if diff_or_match else "❌"
            if not diff_or_match:
                all_passed = False
            print(f"  {status} {metric}: '{baseline_val}' → '{new_val}' ({'匹配' if diff_or_match else '不匹配'})")
        else:
            # 数值比较，允许小幅差异
            tolerance = 1.0  # 允许1分的差异
            status = "✅" if diff_or_match <= tolerance else "❌" 
            if diff_or_match > tolerance:
                all_passed = False
            print(f"  {status} {metric}: {baseline_val} → {new_val} (差异: {diff_or_match:.1f})")
    
    return all_passed

class AIRefactorValidator:
    """AI重构验证器"""
    
    def __init__(self, baseline_data):
        self.baseline_data = baseline_data
        self.test_results = {}
    
    def test_job_analyzer_refactored(self):
        """测试重构后的JobAnalyzer"""
        print("🧪 测试重构后的JobAnalyzer...")
        
        baseline_test = self.baseline_data.get('job_analyzer_deepseek')
        if not baseline_test:
            print("❌ 基准数据中没有job_analyzer_deepseek测试")
            return False
            
        try:
            # 获取基准输入数据
            baseline_input = baseline_test['input']
            job_info = baseline_input['job_info']
            resume_analysis = baseline_input['resume_analysis']
            baseline_output = baseline_test['output']
            
            # 创建重构后的JobAnalyzer
            analyzer = JobAnalyzer(ai_provider='deepseek')
            analyzer.set_resume_analysis(resume_analysis)
            
            # 运行分析
            new_result = analyzer.analyze_jobs([job_info])
            
            # 对比结果
            passed = compare_analysis_results(baseline_output, new_result, "JobAnalyzer重构")
            
            self.test_results['job_analyzer_refactored'] = {
                'passed': passed,
                'baseline_score': baseline_output[0]['analysis']['overall_score'] if isinstance(baseline_output, list) else baseline_output.get('analysis', {}).get('overall_score', 0),
                'new_score': new_result[0]['analysis']['overall_score'] if new_result else 0,
                'method': 'analyze_jobs'
            }
            
            return passed
            
        except Exception as e:
            print(f"❌ JobAnalyzer测试失败: {e}")
            self.test_results['job_analyzer_refactored'] = {
                'passed': False,
                'error': str(e)
            }
            return False
    
    def test_direct_ai_methods(self):
        """测试JobAnalyzer中新添加的直接AI方法"""
        print("\n🧪 测试JobAnalyzer的直接AI方法...")
        
        baseline_ai_service = self.baseline_data.get('ai_service_job_match')
        if not baseline_ai_service:
            print("❌ 基准数据中没有ai_service_job_match测试")
            return False
        
        try:
            # 获取基准输入数据
            baseline_input = baseline_ai_service['input']
            job_info = baseline_input['job_info']
            resume_analysis = baseline_input['resume_analysis']
            baseline_output = baseline_ai_service['output']
            
            # 创建JobAnalyzer并测试新方法
            analyzer = JobAnalyzer(ai_provider='deepseek')
            
            # 测试analyze_job_match方法（从AIService移过来的）
            new_result = analyzer.analyze_job_match(job_info, resume_analysis)
            
            # 对比结果
            passed = compare_analysis_results(baseline_output, new_result, "直接AI方法")
            
            self.test_results['direct_ai_method'] = {
                'passed': passed,
                'baseline_score': baseline_output.get('overall_score', 0),
                'new_score': new_result.get('overall_score', 0),
                'method': 'analyze_job_match'
            }
            
            return passed
            
        except Exception as e:
            print(f"❌ 直接AI方法测试失败: {e}")
            self.test_results['direct_ai_method'] = {
                'passed': False,
                'error': str(e)
            }
            return False
    
    def run_validation(self):
        """运行完整验证"""
        print("🚀 开始AI系统重构验证")
        print("=" * 60)
        
        # 运行所有测试
        tests = [
            self.test_job_analyzer_refactored,
            self.test_direct_ai_methods
        ]
        
        results = []
        for test in tests:
            try:
                result = test()
                results.append(result)
            except Exception as e:
                print(f"❌ 测试执行异常: {e}")
                results.append(False)
        
        # 生成测试报告
        self.generate_report(results)
        
        return all(results)
    
    def generate_report(self, results):
        """生成测试报告"""
        print("\n" + "=" * 60)
        print("📋 重构验证报告")
        print("=" * 60)
        
        passed_count = sum(1 for r in results if r)
        total_count = len(results)
        
        print(f"总测试数: {total_count}")
        print(f"通过测试: {passed_count}")
        print(f"失败测试: {total_count - passed_count}")
        print(f"通过率: {passed_count/total_count*100:.1f}%")
        
        print("\n📊 详细结果:")
        for test_name, test_data in self.test_results.items():
            if test_data.get('passed', False):
                print(f"  ✅ {test_name}: 通过")
                if 'baseline_score' in test_data and 'new_score' in test_data:
                    print(f"      评分对比: {test_data['baseline_score']} → {test_data['new_score']}")
            else:
                print(f"  ❌ {test_name}: 失败")
                if 'error' in test_data:
                    print(f"      错误: {test_data['error']}")
        
        if all(results):
            print(f"\n🎉 重构成功！所有测试通过，可以安全移除AIService层。")
        else:
            print(f"\n⚠️ 重构存在问题，请检查失败的测试用例。")

def main():
    """主函数"""
    # 加载基准数据
    baseline_data = load_baseline_data()
    if not baseline_data:
        return
    
    # 运行验证
    validator = AIRefactorValidator(baseline_data)
    success = validator.run_validation()
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)