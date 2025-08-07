#!/usr/bin/env python3
"""
测试Real Playwright Spider
验证原有的爬虫是否能正常工作
"""

import asyncio
import logging
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crawler.real_playwright_spider import RealPlaywrightBossSpider
from config.config_manager import ConfigManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_real_spider():
    """测试Real Playwright Spider"""
    print("🧪 测试 Real Playwright Spider")
    print("="*60)
    
    # 初始化配置
    config_manager = ConfigManager()
    
    # 创建爬虫实例（有头模式）
    spider = RealPlaywrightBossSpider(headless=False)
    
    try:
        # 启动爬虫
        print("\n🚀 启动爬虫...")
        success = await spider.start()
        if not success:
            print("❌ 爬虫启动失败")
            return False
        
        print("✅ 爬虫启动成功")
        
        # 测试搜索
        test_params = {
            "keyword": "Python",
            "city": "shanghai",
            "max_jobs": 3
        }
        
        print(f"\n🔍 搜索参数:")
        for key, value in test_params.items():
            print(f"   {key}: {value}")
        
        print("\n⏳ 开始搜索...")
        jobs = await spider.search_jobs(
            keyword=test_params["keyword"],
            city=test_params["city"],
            max_jobs=test_params["max_jobs"]
        )
        
        print(f"\n✅ 搜索完成! 找到 {len(jobs)} 个岗位")
        
        # 显示结果
        if jobs:
            print("\n📊 岗位列表:")
            for i, job in enumerate(jobs[:3], 1):
                print(f"\n【岗位 {i}】")
                print(f"  职位: {job.get('title', 'N/A')}")
                print(f"  公司: {job.get('company', 'N/A')}")
                print(f"  薪资: {job.get('salary', 'N/A')}")
                print(f"  地区: {job.get('location', 'N/A')}")
                if 'url' in job:
                    print(f"  链接: {job['url']}")
        else:
            print("\n⚠️ 未找到岗位")
        
        return len(jobs) > 0
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        return False
        
    finally:
        # 关闭爬虫
        await spider.close()
        print("\n🔒 爬虫已关闭")


async def main():
    """主函数"""
    print("🚀 Boss直聘爬虫测试")
    print("="*60)
    
    success = await test_real_spider()
    
    if success:
        print("\n✅ 测试成功！Real Playwright Spider 可以正常工作")
        print("\n💡 建议:")
        print("1. 可以基于 Real Playwright Spider 改进统一爬虫")
        print("2. 复制其反爬虫处理逻辑")
        print("3. 保留其会话管理机制")
    else:
        print("\n❌ 测试失败")
        print("\n⚠️ 可能的问题:")
        print("1. 网络连接问题")
        print("2. Boss直聘反爬虫升级")
        print("3. 需要更新爬虫策略")


if __name__ == "__main__":
    asyncio.run(main())