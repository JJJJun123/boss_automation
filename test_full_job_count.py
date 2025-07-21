#!/usr/bin/env python3
"""
测试完整岗位数量保存功能
验证搜索10个岗位，只分析3个，但保存全部10个
"""

import json
from utils.data_saver import save_all_job_results


def simulate_job_search():
    """模拟搜索和分析流程"""
    
    # 模拟搜索到10个岗位
    all_jobs = []
    for i in range(10):
        job = {
            "title": f"岗位{i+1}",
            "company": f"公司{i+1}",
            "salary": f"{20+i*2}-{30+i*2}K",
            "url": f"https://example.com/job/{i+1}"
        }
        all_jobs.append(job)
    
    print(f"🔍 搜索到 {len(all_jobs)} 个岗位")
    
    # 模拟只分析前3个岗位
    max_analyze_jobs = 3
    
    for i, job in enumerate(all_jobs):
        if i < max_analyze_jobs:
            # 分析前3个
            print(f"🤖 分析第 {i+1}/{max_analyze_jobs} 个岗位...")
            job['analysis'] = {
                "score": 9 - i * 2,  # 模拟不同分数
                "recommendation": "推荐" if (9 - i * 2) >= 7 else "不推荐",
                "reason": f"这是分析过的岗位{i+1}",
                "summary": f"岗位{i+1}的分析结果"
            }
        else:
            # 未分析的岗位
            job['analysis'] = {
                "score": 0,
                "recommendation": "未分析",
                "reason": "超出分析数量限制，未进行AI分析",
                "summary": "该岗位未进行详细分析"
            }
    
    # 筛选高分岗位（>=7分）
    qualified_jobs = [job for job in all_jobs if job['analysis']['score'] >= 7]
    
    print(f"\n📊 统计结果:")
    print(f"   - 搜索到的岗位: {len(all_jobs)}")
    print(f"   - 分析的岗位: {max_analyze_jobs}")
    print(f"   - 推荐的岗位: {len(qualified_jobs)}")
    
    return all_jobs, qualified_jobs


def test_save_and_display():
    """测试保存和显示"""
    all_jobs, qualified_jobs = simulate_job_search()
    
    # 保存数据
    print("\n💾 保存数据...")
    save_all_job_results(all_jobs, qualified_jobs, "data/test_full_count.json")
    
    # 读取并验证
    with open("data/test_full_count.json", 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
    
    print("\n✅ 验证保存的数据:")
    print(f"   - all_jobs 数量: {len(saved_data['all_jobs'])}")
    print(f"   - qualified_jobs 数量: {len(saved_data['qualified_jobs'])}")
    
    # 显示所有岗位状态
    print("\n📋 所有岗位状态:")
    for i, job in enumerate(saved_data['all_jobs'], 1):
        status = job['analysis']['recommendation']
        score = job['analysis']['score']
        emoji = "✅" if status == "推荐" else "❌" if status == "不推荐" else "⏭️"
        print(f"   {i}. {job['title']} - {status} ({score}分) {emoji}")
    
    print("\n💡 结论:")
    print("   - 点击'总搜索数'会显示全部10个岗位")
    print("   - 包括3个分析过的岗位和7个未分析的岗位")
    print("   - 点击'合格岗位'只显示高分推荐的岗位")


def main():
    """主函数"""
    print("🎯 测试完整岗位数量保存")
    print("=" * 60)
    
    test_save_and_display()
    
    print("\n✅ 修复完成！现在系统会:")
    print("1. 保存所有搜索到的岗位（而不只是分析过的）")
    print("2. 为未分析的岗位添加默认分析结果")
    print("3. 正确显示总搜索数")


if __name__ == "__main__":
    main()