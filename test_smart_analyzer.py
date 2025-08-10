#!/usr/bin/env python3
"""
测试智能分层岗位分析器
"""

import json
from analyzer.smart_job_analyzer import SmartJobAnalyzer

def create_test_jobs():
    """创建测试岗位数据"""
    return [
        {
            "title": "市场风险分析师",
            "company": "某大型银行",
            "salary": "20-30K",
            "job_description": """
            岗位职责：
            1. 负责市场风险的识别、评估和监控
            2. 制定市场风险管理策略和政策
            3. 进行压力测试和情景分析
            4. 撰写市场风险报告
            
            任职要求：
            1. 金融、经济学等相关专业本科及以上学历
            2. 3年以上市场风险管理经验
            3. 熟悉VaR、压力测试等风险管理工具
            4. 精通Python、SQL等数据分析工具
            5. 具备FRM或CFA证书优先
            """,
            "link": "https://example.com/job1"
        },
        {
            "title": "AI算法工程师",
            "company": "某科技公司",
            "salary": "25-40K",
            "job_description": """
            岗位职责：
            1. 负责机器学习模型的研发和优化
            2. 设计和实现深度学习算法
            3. 参与AI产品的架构设计
            
            任职要求：
            1. 计算机相关专业硕士及以上学历
            2. 精通Python、TensorFlow或PyTorch
            3. 有NLP或计算机视觉项目经验
            4. 发表过相关论文者优先
            """,
            "link": "https://example.com/job2"
        },
        {
            "title": "销售经理",
            "company": "某电商公司",
            "salary": "15-25K",
            "job_description": """
            岗位职责：
            1. 负责销售团队管理
            2. 制定销售策略
            3. 维护客户关系
            
            任职要求：
            1. 3年以上销售管理经验
            2. 有电商行业背景优先
            """,
            "link": "https://example.com/job3"
        }
    ]

def create_test_resume():
    """创建测试简历数据"""
    return {
        "name": "张三",
        "skills": ["Python", "风险管理", "数据分析", "机器学习"],
        "experience_years": 5,
        "education": "硕士",
        "expected_salary": "25-35K"
    }

def test_smart_analyzer():
    """测试智能分析器"""
    print("=" * 60)
    print("🧪 开始测试智能分层岗位分析器")
    print("=" * 60)
    
    # 创建分析器实例
    analyzer = SmartJobAnalyzer()
    
    # 准备测试数据
    test_jobs = create_test_jobs()
    test_resume = create_test_resume()
    
    print(f"\n📋 测试数据：")
    print(f"   - 岗位数量：{len(test_jobs)}")
    print(f"   - 简历信息：{test_resume['name']}, {test_resume['experience_years']}年经验")
    
    # 运行分析
    print("\n🔄 开始智能分析...")
    result = analyzer.analyze_jobs_smart(test_jobs, test_resume)
    
    # 显示结果
    print("\n" + "=" * 60)
    print("📊 分析结果")
    print("=" * 60)
    
    # 统计信息
    print(f"\n📈 统计信息：")
    print(f"   - 总岗位数：{result['total_jobs']}")
    print(f"   - 平均分数：{result['statistics']['average_score']:.2f}")
    print(f"   - 高匹配度：{result['statistics']['high_match_count']}个")
    print(f"   - 中匹配度：{result['statistics']['medium_match_count']}个")
    print(f"   - 低匹配度：{result['statistics']['low_match_count']}个")
    
    # 成本分析
    print(f"\n💰 成本分析：")
    cost_analysis = result['cost_analysis']
    print(f"   - API调用次数：{cost_analysis['total_api_calls']}")
    print(f"   - 缓存命中次数：{cost_analysis['cache_hits']}")
    print(f"   - 预估成本：{cost_analysis['estimated_cost']}")
    
    # TOP岗位详情
    print(f"\n🏆 TOP岗位详细分析：")
    for i, job in enumerate(result['top_jobs_detailed'][:3], 1):
        print(f"\n   {i}. {job['title']} - {job['company']}")
        print(f"      评分：{job.get('score', 0):.1f}/10")
        print(f"      匹配理由：{job.get('match_reason', '未知')}")
        
        if 'deep_analysis' in job:
            analysis = job['deep_analysis']
            print(f"      深度分析：{analysis.get('summary', '无')[:100]}...")
    
    # 保存结果
    output_file = "data/smart_analyzer_test_result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 完整结果已保存到：{output_file}")
    
    return result

if __name__ == "__main__":
    # 运行测试
    test_smart_analyzer()