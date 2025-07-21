#!/usr/bin/env python3
"""
Boss直聘自动化 - 登录演示
演示如何使用Playwright爬虫的登录功能
"""

import asyncio
import sys
import os
import logging

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from crawler.real_playwright_spider import search_with_real_playwright


def main():
    """主函数"""
    print("=" * 60)
    print("Boss直聘自动化 - 登录功能演示")
    print("=" * 60)
    print("\n登录说明:")
    print("1. 程序会自动打开Chrome浏览器")
    print("2. 如果是首次运行，需要手动登录:")
    print("   - 点击页面右上角的 '登录' 按钮")
    print("   - 推荐使用手机扫码登录（更快更安全）")
    print("   - 登录成功后，程序会自动继续")
    print("3. 登录成功后，cookies会自动保存")
    print("4. 下次运行时会自动使用保存的cookies，无需再次登录")
    print("=" * 60)
    
    input("\n按回车键开始...")
    
    # 搜索参数
    keyword = "数据分析"
    city = "shanghai"
    max_jobs = 10
    
    print(f"\n开始搜索: {keyword} | 城市: 上海 | 数量: {max_jobs}")
    
    # 执行搜索（会自动处理登录）
    jobs = search_with_real_playwright(keyword, city, max_jobs)
    
    # 显示结果
    print(f"\n搜索完成！找到 {len(jobs)} 个岗位:")
    print("-" * 60)
    
    for i, job in enumerate(jobs[:5], 1):  # 只显示前5个
        print(f"\n岗位 #{i}:")
        print(f"  职位: {job.get('title', '未知')}")
        print(f"  公司: {job.get('company', '未知')}")
        print(f"  薪资: {job.get('salary', '未知')}")
        print(f"  地点: {job.get('work_location', '未知')}")
        
        # 显示URL（截断显示）
        url = job.get('url', '')
        if url:
            print(f"  链接: {url[:80]}...")
    
    print("\n" + "-" * 60)
    print("✅ 搜索完成！")
    
    # 检查cookies是否已保存
    cookies_file = os.path.join(os.path.dirname(__file__), 'crawler', 'cookies', 'boss_cookies.json')
    if os.path.exists(cookies_file):
        print(f"\n✅ Cookies已保存，下次运行将自动登录")
        print(f"   文件位置: {cookies_file}")
    
    print("\n提示: 再次运行此脚本，将自动使用保存的登录状态，无需手动登录")


if __name__ == "__main__":
    main()