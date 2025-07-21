#!/usr/bin/env python3
"""
测试所有岗位显示功能
验证点击"总搜索数"是否能显示所有岗位
"""

import json
import os
from utils.data_saver import save_all_job_results, load_all_job_results


def create_test_data():
    """创建测试数据"""
    # 模拟搜索到的所有岗位（包括低分的）
    all_jobs = [
        {
            "title": "AI产品经理（高分）",
            "company": "大型科技公司",
            "salary": "30-50K",
            "analysis": {"score": 8.5, "recommendation": "推荐"}
        },
        {
            "title": "数据分析师（中分）",
            "company": "中型金融公司",
            "salary": "20-30K",
            "analysis": {"score": 6.5, "recommendation": "一般"}
        },
        {
            "title": "前端工程师（低分）",
            "company": "初创公司",
            "salary": "15-25K",
            "analysis": {"score": 4.0, "recommendation": "不推荐"}
        },
        {
            "title": "风险管理专家（高分）",
            "company": "大型银行",
            "salary": "35-55K",
            "analysis": {"score": 9.0, "recommendation": "强烈推荐"}
        },
        {
            "title": "运营专员（低分）",
            "company": "小型电商",
            "salary": "8-12K",
            "analysis": {"score": 3.5, "recommendation": "不推荐"}
        }
    ]
    
    # 筛选出高分岗位（>= 7分）
    qualified_jobs = [job for job in all_jobs if job['analysis']['score'] >= 7.0]
    
    print(f"🔍 创建测试数据:")
    print(f"   - 总搜索数: {len(all_jobs)} 个岗位")
    print(f"   - 推荐岗位: {len(qualified_jobs)} 个岗位")
    
    return all_jobs, qualified_jobs


def test_save_and_load():
    """测试保存和加载功能"""
    print("\n📝 测试数据保存功能...")
    
    # 创建测试数据
    all_jobs, qualified_jobs = create_test_data()
    
    # 保存数据
    success = save_all_job_results(all_jobs, qualified_jobs, "data/test_job_results.json")
    
    if success:
        print("✅ 数据保存成功")
        
        # 加载数据
        print("\n📖 测试数据加载功能...")
        loaded_data = load_all_job_results("data/test_job_results.json")
        
        print(f"   - 加载的所有岗位: {len(loaded_data['all_jobs'])} 个")
        print(f"   - 加载的推荐岗位: {len(loaded_data['qualified_jobs'])} 个")
        
        # 显示所有岗位标题
        print("\n🔍 所有岗位列表:")
        for i, job in enumerate(loaded_data['all_jobs'], 1):
            score = job['analysis']['score']
            status = "✅" if score >= 7 else "❌"
            print(f"   {i}. {job['title']} - {job['company']} ({score}分) {status}")
        
        print("\n⭐ 推荐岗位列表:")
        for i, job in enumerate(loaded_data['qualified_jobs'], 1):
            print(f"   {i}. {job['title']} - {job['company']} ({job['analysis']['score']}分)")
        
        return True
    else:
        print("❌ 数据保存失败")
        return False


def test_frontend_behavior():
    """测试前端行为说明"""
    print("\n🖥️ 前端行为说明:")
    print("1. 点击'总搜索数'时:")
    print("   - 调用 showAllJobs() 函数")
    print("   - 从 allJobs 数组显示所有岗位")
    print("   - allJobs 来自后端返回的 data.all_jobs")
    
    print("\n2. 点击'合格岗位'时:")
    print("   - 调用 showQualifiedJobs() 函数")
    print("   - 从 qualifiedJobs 数组显示推荐岗位")
    print("   - qualifiedJobs 来自后端返回的 data.results")
    
    print("\n3. 数据流程:")
    print("   搜索 → 分析所有岗位 → 筛选高分岗位 → 保存两种数据 → 前端展示")


def main():
    """主函数"""
    print("🎯 测试所有岗位显示功能")
    print("=" * 60)
    
    # 测试保存和加载
    if test_save_and_load():
        print("\n✅ 数据保存和加载测试通过")
    else:
        print("\n❌ 数据保存和加载测试失败")
    
    # 说明前端行为
    test_frontend_behavior()
    
    print("\n💡 下一步:")
    print("1. 运行 python run_web.py")
    print("2. 搜索岗位")
    print("3. 点击'总搜索数'查看所有岗位（包括低分的）")
    print("4. 点击'合格岗位'查看推荐岗位（只有高分的）")


if __name__ == "__main__":
    main()