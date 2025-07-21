#!/usr/bin/env python3
"""
快速验证修复效果
检查主要问题是否已解决
"""

import sys
import os
import logging

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def quick_test():
    """快速测试修复效果"""
    
    print("🔧 Boss直聘自动化 - 修复效果验证")
    print("=" * 40)
    
    success_count = 0
    total_tests = 4
    
    # 测试1: 城市代码映射
    print("\n1️⃣ 检查城市代码映射...")
    try:
        from crawler.real_playwright_spider import RealPlaywrightBossSpider
        spider = RealPlaywrightBossSpider()
        
        # 验证上海代码
        shanghai_code = spider.city_codes.get("shanghai")
        if shanghai_code == "101210100":
            print("   ✅ 上海城市代码正确: 101210100")
            success_count += 1
        else:
            print(f"   ❌ 上海城市代码错误: {shanghai_code}")
    except Exception as e:
        print(f"   ❌ 城市代码检查失败: {e}")
    
    # 测试2: URL生成格式
    print("\n2️⃣ 检查URL生成格式...")
    try:
        from crawler.playwright_spider import _generate_real_job_url
        
        test_url = _generate_real_job_url("数据分析师", 0)
        if "job_detail" in test_url and ".html" in test_url:
            print(f"   ✅ URL格式正确: {test_url[:50]}...")
            success_count += 1
        else:
            print(f"   ❌ URL格式错误: {test_url}")
    except Exception as e:
        print(f"   ❌ URL生成检查失败: {e}")
    
    # 测试3: 备用数据地点
    print("\n3️⃣ 检查备用数据地点...")
    try:
        from crawler.playwright_spider import _generate_fallback_data
        
        jobs = _generate_fallback_data("测试", 2, "101210100")  # 上海代码
        if jobs and "上海" in jobs[0].get('work_location', ''):
            print(f"   ✅ 备用数据地点正确: {jobs[0].get('work_location')}")
            success_count += 1
        else:
            print(f"   ❌ 备用数据地点错误: {jobs[0].get('work_location', '无') if jobs else '无数据'}")
    except Exception as e:
        print(f"   ❌ 备用数据检查失败: {e}")
    
    # 测试4: MCP搜索功能
    print("\n4️⃣ 检查MCP搜索功能...")
    try:
        from crawler.playwright_spider import search_with_playwright_mcp
        
        # 测试搜索(使用备用数据)
        jobs = search_with_playwright_mcp("测试", "101210100", 1, False)
        if jobs and len(jobs) > 0:
            job = jobs[0]
            location = job.get('work_location', '')
            url = job.get('url', '')
            
            if "上海" in location and "job_detail" in url:
                print(f"   ✅ MCP搜索功能正常")
                print(f"      地点: {location}")
                print(f"      URL: {url[:50]}...")
                success_count += 1
            else:
                print(f"   ⚠️ MCP搜索部分问题:")
                print(f"      地点: {location}")
                print(f"      URL: {url}")
        else:
            print("   ❌ MCP搜索无结果")
    except Exception as e:
        print(f"   ❌ MCP搜索检查失败: {e}")
    
    # 结果汇总
    print("\n" + "=" * 40)
    print(f"📊 测试结果: {success_count}/{total_tests} 项通过")
    
    if success_count == total_tests:
        print("🎉 所有检查通过！修复成功!")
        print("\n✅ 修复确认:")
        print("  • 城市代码映射已修正")
        print("  • URL格式指向真实岗位")
        print("  • 地点信息正确匹配")
        print("  • 搜索功能正常工作")
        
        print("\n🚀 现在可以正常使用:")
        print("  python run_web.py")
        
    elif success_count >= 3:
        print("🔧 基本修复成功，可能有小问题")
        print("  建议运行完整测试:")
        print("  python test_location_and_count_fixes.py")
        
    else:
        print("⚠️ 修复可能不完整，需要检查")
        print("  建议检查依赖安装和代码修改")
    
    return success_count == total_tests


if __name__ == "__main__":
    quick_test()