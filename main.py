#!/usr/bin/env python3
"""
Boss直聘自动化求职系统 - Web版本
支持灵活的配置管理和Web界面
"""

import os
import sys
import logging
import json
from datetime import datetime
from crawler.boss_spider import BossSpider
from analyzer.job_analyzer import JobAnalyzer
from config.config_manager import ConfigManager


def print_header():
    """打印程序头部信息"""
    print("=" * 60)
    print("🤖 Boss直聘自动化求职系统 - MVP版本")
    print("=" * 60)
    print(f"⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


def print_job_analysis(job, index):
    """打印单个岗位分析结果 - 增强版本"""
    analysis = job.get('analysis', {})
    score = analysis.get('score', 0)
    
    print(f"\n📋 岗位 #{index}")
    print(f"🏢 公司: {job.get('company', '未知')}")
    print(f"💼 职位: {job.get('title', '未知')}")
    print(f"💰 薪资: {job.get('salary', '未知')}")
    print(f"🏷️  标签: {', '.join(job.get('tags', []))}")
    print(f"📍 链接: {job.get('url', '未知')}")
    
    # 显示详细信息（如果有）
    if job.get('work_location'):
        print(f"🌍 工作地点: {job.get('work_location')}")
    if job.get('benefits'):
        print(f"🎁 福利待遇: {job.get('benefits')}")
    if job.get('experience_required'):
        print(f"📊 经验要求: {job.get('experience_required')}")
    
    # AI分析结果
    print(f"⭐ AI评分: {score}/10 ({analysis.get('recommendation', '未知')})")
    print(f"💡 分析: {analysis.get('summary', '无分析结果')}")
    reason = analysis.get('reason', '无详细理由')
    print(f"📝 理由: {reason[:100]}..." if len(reason) > 100 else f"📝 理由: {reason}")
    
    # 显示职位描述片段（如果有）
    if job.get('job_description'):
        desc = job.get('job_description', '')
        if len(desc) > 150:
            print(f"📄 职位描述: {desc[:150]}...")
        else:
            print(f"📄 职位描述: {desc}")
    
    print("-" * 50)


def save_results_to_file(jobs, filename="data/job_results.txt"):
    """保存结果到文件"""
    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Boss直聘岗位分析结果\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"共找到 {len(jobs)} 个合适岗位\n")
            f.write("=" * 80 + "\n\n")
            
            for i, job in enumerate(jobs, 1):
                analysis = job.get('analysis', {})
                f.write(f"岗位 #{i}\n")
                f.write(f"公司: {job.get('company', '未知')}\n")
                f.write(f"职位: {job.get('title', '未知')}\n")
                f.write(f"薪资: {job.get('salary', '未知')}\n")
                f.write(f"标签: {', '.join(job.get('tags', []))}\n")
                f.write(f"公司信息: {job.get('company_info', '未知')}\n")
                f.write(f"链接: {job.get('url', '未知')}\n")
                
                # 详细信息（如果有）
                if job.get('work_location'):
                    f.write(f"工作地点: {job.get('work_location')}\n")
                if job.get('benefits'):
                    f.write(f"福利待遇: {job.get('benefits')}\n")
                if job.get('experience_required'):
                    f.write(f"经验要求: {job.get('experience_required')}\n")
                if job.get('company_details'):
                    f.write(f"公司详情: {job.get('company_details')}\n")
                if job.get('job_requirements'):
                    f.write(f"岗位要求: {job.get('job_requirements')}\n")
                
                # AI分析结果
                f.write(f"AI评分: {analysis.get('score', 0)}/10\n")
                f.write(f"推荐状态: {analysis.get('recommendation', '未知')}\n")
                f.write(f"分析摘要: {analysis.get('summary', '无摘要')}\n")
                f.write(f"详细理由: {analysis.get('reason', '无详细理由')}\n")
                
                # 完整职位描述
                if job.get('job_description'):
                    f.write(f"\n职位描述:\n{job.get('job_description')}\n")
                
                f.write("-" * 80 + "\n\n")
        
        print(f"✅ 结果已保存到: {filename}")
        return True
        
    except Exception as e:
        print(f"❌ 保存结果失败: {e}")
        return False


def save_results_to_json(jobs, filename="data/job_results.json"):
    """保存结果到JSON文件"""
    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # 构建JSON数据结构
        json_data = {
            "metadata": {
                "generated_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_jobs": len(jobs),
                "version": "1.0.0"
            },
            "jobs": jobs
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ JSON结果已保存到: {filename}")
        return True
        
    except Exception as e:
        print(f"❌ 保存JSON结果失败: {e}")
        return False


def main():
    """主函数"""
    print_header()
    
    # 初始化配置管理器
    try:
        config_manager = ConfigManager()
        
        # 验证配置
        if not config_manager.validate_config():
            print("❌ 配置验证失败，请检查配置文件")
            print("📝 请确保正确设置了API密钥和基本配置")
            return
        
        # 获取搜索配置
        search_config = config_manager.get_search_config()
        ai_config = config_manager.get_ai_config()
        
        # 获取第一个城市的代码（简化处理）
        selected_cities = search_config['cities']
        city_codes = search_config['city_codes']
        
        if not selected_cities:
            print("❌ 未选择任何城市")
            return
        
        # 获取第一个城市的代码
        first_city = selected_cities[0]
        city_code = city_codes.get(first_city, {}).get('code', '101210100')
        city_name = city_codes.get(first_city, {}).get('name', '未知城市')
        
        # 显示配置信息
        print(f"🔍 搜索关键词: {search_config['keyword']}")
        print(f"📍 搜索城市: {city_name} ({city_code})")
        print(f"📊 最大搜索岗位数: {search_config['max_jobs']}")
        print(f"🤖 AI分析岗位数: {search_config['max_analyze_jobs']}")
        print(f"⭐ 最低评分: {ai_config['min_score']}/10")
        print(f"🤖 AI模型: {ai_config['provider'].upper()}")
        print(f"📄 获取详细信息: {'是' if search_config['fetch_details'] else '否'}")
        print()
        
    except Exception as e:
        print(f"❌ 配置初始化失败: {e}")
        logging.error(f"配置初始化失败: {e}")
        return
    
    spider = None
    try:
        # 1. 启动爬虫
        print("🚀 第一步: 启动爬虫...")
        spider = BossSpider()
        if not spider.start():
            print("❌ 爬虫启动失败")
            return
        
        # 2. 登录
        print("\n🔐 第二步: 处理登录...")
        if not spider.login_with_manual_help():
            print("❌ 登录失败")
            return
        
        # 3. 搜索岗位
        print(f"\n🔍 第三步: 搜索岗位...")
        jobs = spider.search_jobs(search_config['keyword'], city_code, search_config['max_jobs'], search_config['fetch_details'])
        
        if not jobs:
            print("❌ 未找到任何岗位")
            return
        
        # 4. AI分析
        print(f"\n🤖 第四步: AI智能分析...")
        analyzer = JobAnalyzer(ai_config['provider'])
        
        # 只分析前max_analyze_jobs个岗位
        jobs_to_analyze = jobs[:search_config['max_analyze_jobs']]
        print(f"准备分析前 {len(jobs_to_analyze)} 个岗位 (共找到 {len(jobs)} 个)")
        
        analyzed_jobs = analyzer.analyze_jobs(jobs_to_analyze)
        
        # 5. 过滤和排序
        print(f"\n🎯 第五步: 过滤和排序...")
        filtered_jobs = analyzer.filter_and_sort_jobs(analyzed_jobs, ai_config['min_score'])
        
        # 6. 输出结果
        print(f"\n📊 第六步: 输出结果...")
        if filtered_jobs:
            print(f"\n🎉 找到 {len(filtered_jobs)} 个匹配的岗位:")
            
            for i, job in enumerate(filtered_jobs, 1):
                print_job_analysis(job, i)
            
            # 保存到文件
            save_results_to_file(filtered_jobs)
            save_results_to_json(filtered_jobs)
            
        else:
            print("😔 很遗憾，没有找到符合要求的岗位")
            print("💡 建议:")
            print("   - 降低最低评分标准")
            print("   - 尝试其他搜索关键词")
            print("   - 检查用户要求设置")
        
        print(f"\n✅ 任务完成! 用时: {datetime.now()}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理资源
        if spider:
            print("\n🧹 清理资源...")
            spider.close()
        print("👋 程序结束")


if __name__ == "__main__":
    main()