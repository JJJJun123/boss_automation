#!/usr/bin/env python3
"""
AI系统测试基准收集器
在重构前收集输入/输出样本作为测试基准
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
from analyzer.ai_client_factory import AIClientFactory
from analyzer.ai_service import create_ai_service

# 测试样本数据
SAMPLE_JOB_INFO = {
    "title": "高级风险管理经理",
    "company": "某大型金融集团",
    "salary": "30K-50K",
    "location": "上海·陆家嘴",
    "description": """
岗位职责：
1. 负责金融产品风险评估与管控
2. 建立和完善风险管理体系
3. 监控市场风险并制定应对策略
4. 协调各部门风险管理工作

任职要求：
1. 金融、经济或相关专业本科以上学历
2. 5年以上风险管理相关工作经验
3. 熟悉风险管理理论和实践
4. 具备较强的数据分析能力
5. 持有FRM、CFA等相关证书优先
""",
    "requirements": ["金融专业", "5年经验", "风险管理", "数据分析", "FRM证书"],
    "company_info": {
        "size": "1000-5000人",
        "industry": "金融/投资/证券",
        "financing": "已上市"
    }
}

SAMPLE_USER_REQUIREMENTS = """
求职意向：
- 市场风险管理相关岗位
- 金融相关岗位（银行、证券、基金）

背景要求：
- 有金融行业经验优先
- 熟悉风险管理、数据分析
- 希望在大中型公司发展

薪资期望：
- 25K-45K/月（可接受范围）

地理位置：
- 上海优先，其他一线城市可考虑
"""

SAMPLE_RESUME_ANALYSIS = {
    "competitiveness_score": 7.5,
    "skills": ["风险管理", "数据分析", "Python", "金融建模"],
    "experience_years": 4,
    "education": "金融学硕士",
    "strengths": ["风险评估经验丰富", "具备相关技术技能"],
    "weaknesses": ["工作年限略少", "缺少FRM证书"]
}

class AIBaselineCollector:
    """AI基准数据收集器"""
    
    def __init__(self):
        self.test_results = {}
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def collect_job_analyzer_baseline(self):
        """收集JobAnalyzer的输入输出基准"""
        print("📊 收集JobAnalyzer基准数据...")
        
        try:
            # 测试不同的AI提供商
            providers = ['deepseek']  # 先测试一个，避免API调用过多
            
            for provider in providers:
                print(f"\n🤖 测试提供商: {provider}")
                
                # 创建JobAnalyzer实例
                analyzer = JobAnalyzer(ai_provider=provider)
                
                # 设置简历分析结果
                analyzer.set_resume_analysis(SAMPLE_RESUME_ANALYSIS)
                
                # 测试analyze_jobs方法
                print("  测试 analyze_jobs...")
                result = analyzer.analyze_jobs([SAMPLE_JOB_INFO])
                
                self.test_results[f'job_analyzer_{provider}'] = {
                    'input': {
                        'job_info': SAMPLE_JOB_INFO,
                        'resume_analysis': SAMPLE_RESUME_ANALYSIS,
                        'user_requirements': SAMPLE_USER_REQUIREMENTS
                    },
                    'output': result,
                    'method': 'analyze_jobs',
                    'timestamp': self.timestamp
                }
                
                print(f"  ✅ {provider} 基准数据收集完成")
                
        except Exception as e:
            print(f"❌ JobAnalyzer基准收集失败: {e}")
            self.test_results['job_analyzer_error'] = str(e)
    
    def collect_ai_service_baseline(self):
        """收集AIService的输入输出基准"""
        print("\n📊 收集AIService基准数据...")
        
        try:
            # 创建AI服务
            ai_service = create_ai_service('deepseek')
            
            # 测试analyze_job_match方法
            print("  测试 analyze_job_match...")
            result = ai_service.analyze_job_match(
                job_info=SAMPLE_JOB_INFO,
                resume_analysis=SAMPLE_RESUME_ANALYSIS
            )
            
            self.test_results['ai_service_job_match'] = {
                'input': {
                    'job_info': SAMPLE_JOB_INFO,
                    'resume_analysis': SAMPLE_RESUME_ANALYSIS
                },
                'output': result,
                'method': 'analyze_job_match',
                'timestamp': self.timestamp
            }
            
            # 测试analyze_job_match_simple方法
            print("  测试 analyze_job_match_simple...")
            result_simple = ai_service.analyze_job_match_simple(
                job_info=SAMPLE_JOB_INFO,
                user_requirements=SAMPLE_USER_REQUIREMENTS
            )
            
            self.test_results['ai_service_job_match_simple'] = {
                'input': {
                    'job_info': SAMPLE_JOB_INFO,
                    'user_requirements': SAMPLE_USER_REQUIREMENTS
                },
                'output': result_simple,
                'method': 'analyze_job_match_simple',
                'timestamp': self.timestamp
            }
            
            print("  ✅ AIService 基准数据收集完成")
            
        except Exception as e:
            print(f"❌ AIService基准收集失败: {e}")
            self.test_results['ai_service_error'] = str(e)
    
    def collect_ai_client_baseline(self):
        """收集AI客户端的输入输出基准"""
        print("\n📊 收集AI客户端基准数据...")
        
        try:
            # 创建DeepSeek客户端
            client = AIClientFactory.create_client('deepseek')
            
            # 测试基础API调用
            system_prompt = "你是一个专业的职业匹配分析师。"
            user_prompt = f"请分析以下岗位信息：{json.dumps(SAMPLE_JOB_INFO, ensure_ascii=False, indent=2)}"
            
            print("  测试 call_api...")
            if hasattr(client, 'call_api'):
                response = client.call_api(system_prompt, user_prompt)
                
                self.test_results['ai_client_call_api'] = {
                    'input': {
                        'system_prompt': system_prompt,
                        'user_prompt': user_prompt
                    },
                    'output': response,
                    'method': 'call_api',
                    'timestamp': self.timestamp
                }
            
            # 测试简单API调用
            simple_prompt = f"分析这个岗位：{SAMPLE_JOB_INFO['title']}"
            
            print("  测试 call_api_simple...")
            if hasattr(client, 'call_api_simple'):
                response_simple = client.call_api_simple(simple_prompt)
                
                self.test_results['ai_client_call_api_simple'] = {
                    'input': {
                        'prompt': simple_prompt
                    },
                    'output': response_simple,
                    'method': 'call_api_simple',
                    'timestamp': self.timestamp
                }
            
            print("  ✅ AI客户端 基准数据收集完成")
            
        except Exception as e:
            print(f"❌ AI客户端基准收集失败: {e}")
            self.test_results['ai_client_error'] = str(e)
    
    def save_baseline_data(self):
        """保存基准数据到文件"""
        filename = f"ai_baseline_{self.timestamp}.json"
        filepath = os.path.join("data", filename)
        
        # 确保data目录存在
        os.makedirs("data", exist_ok=True)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.test_results, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 基准数据已保存到: {filepath}")
            print(f"📊 收集了 {len(self.test_results)} 个测试样本")
            
        except Exception as e:
            print(f"❌ 保存基准数据失败: {e}")
    
    def run_collection(self):
        """运行完整的基准数据收集"""
        print("🚀 开始收集AI系统测试基准数据")
        print("="*60)
        
        # 收集各层级的基准数据
        self.collect_job_analyzer_baseline()
        self.collect_ai_service_baseline() 
        self.collect_ai_client_baseline()
        
        # 保存数据
        self.save_baseline_data()
        
        # 显示摘要
        print("\n📋 收集摘要:")
        for key, value in self.test_results.items():
            if isinstance(value, dict) and 'method' in value:
                print(f"  ✅ {key}: {value['method']}")
            else:
                print(f"  ❌ {key}: 错误")

def main():
    """主函数"""
    collector = AIBaselineCollector()
    collector.run_collection()

if __name__ == "__main__":
    main()