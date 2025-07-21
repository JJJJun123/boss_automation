#!/usr/bin/env python3
"""
快速测试和验证当前修复效果
检查去重和字段提取问题
"""

import asyncio
import logging
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def quick_test():
    """快速测试修复效果"""
    try:
        from crawler.real_playwright_spider import RealPlaywrightBossSpider
        
        logger.info("🚀 快速测试修复效果...")
        
        spider = RealPlaywrightBossSpider(headless=False)
        
        if not await spider.start():
            logger.error("❌ 无法启动Playwright")
            return
        
        # 测试搜索
        keyword = "市场风险管理"
        city = "shanghai"
        
        logger.info(f"🔍 搜索: {keyword} 在 {city}")
        jobs = await spider.search_jobs(keyword, city, 3)  # 只测试3个岗位
        
        if jobs:
            logger.info(f"✅ 成功提取 {len(jobs)} 个岗位")
            
            # 检查重复问题
            unique_urls = set()
            duplicates = []
            
            for i, job in enumerate(jobs, 1):
                url = job.get('url', '')
                clean_url = url.split('?')[0] if '?' in url and url else url
                
                logger.info(f"\n📋 岗位 {i}:")
                logger.info(f"   标题: {job.get('title', 'N/A')}")
                logger.info(f"   公司: {job.get('company', 'N/A')}")
                logger.info(f"   地点: {job.get('work_location', 'N/A')}")
                logger.info(f"   URL: {clean_url}")
                
                # 检查重复
                if clean_url in unique_urls:
                    duplicates.append(i)
                    logger.warning(f"   ⚠️ 重复URL发现！")
                else:
                    unique_urls.add(clean_url)
                    logger.info(f"   ✅ 唯一岗位")
                
                # 检查岗位描述问题
                desc = job.get('job_description', '')
                req = job.get('job_requirements', '')
                
                if '具体职责请查看岗位详情' in desc:
                    logger.warning(f"   ⚠️ 岗位描述是模板文本")
                else:
                    logger.info(f"   ✅ 岗位描述: {desc[:50]}...")
                
                if '要求1-3年工作经验' in req or '要求工作经验' in req:
                    logger.warning(f"   ⚠️ 任职要求是模板文本")
                else:
                    logger.info(f"   ✅ 任职要求: {req[:50]}...")
            
            # 总结
            logger.info(f"\n📊 测试总结:")
            logger.info(f"   总岗位数: {len(jobs)}")
            logger.info(f"   唯一岗位数: {len(unique_urls)}")
            logger.info(f"   重复岗位数: {len(duplicates)}")
            
            success_metrics = {
                "去重效果": len(duplicates) == 0,
                "城市匹配": any("上海" in job.get('work_location', '') for job in jobs),
                "字段完整": all(job.get('title') and job.get('company') for job in jobs)
            }
            
            for metric, result in success_metrics.items():
                status = "✅" if result else "❌"
                logger.info(f"   {metric}: {status}")
            
            overall_success = sum(success_metrics.values()) >= 2
            
            if overall_success:
                logger.info("🎉 总体修复效果良好！")
            else:
                logger.warning("⚠️ 仍需进一步优化")
                
            return overall_success
            
        else:
            logger.warning("⚠️ 未提取到岗位")
            return False
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            await spider.close()
        except:
            pass


def main():
    """主函数"""
    print("⚡ Boss直聘快速修复测试")
    print("=" * 40)
    
    result = asyncio.run(quick_test())
    
    if result:
        print("\n✅ 快速测试通过")
        print("💡 可以运行完整应用: python run_web.py")
    else:
        print("\n❌ 快速测试未通过")
        print("💡 需要进一步调试和修复")


if __name__ == "__main__":
    main()