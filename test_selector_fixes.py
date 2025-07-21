#!/usr/bin/env python3
"""
测试选择器修复效果
验证新的选择器和过滤逻辑是否能正确提取岗位信息
"""

import asyncio
import logging
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_selector_fixes():
    """测试修复后的选择器效果"""
    try:
        from crawler.real_playwright_spider import RealPlaywrightBossSpider
        
        logger.info("🔍 测试修复后的选择器效果...")
        
        # 创建爬虫实例（可见模式，便于观察）
        spider = RealPlaywrightBossSpider(headless=False)
        
        if not await spider.start():
            logger.error("❌ 无法启动Playwright")
            return False
        
        # 测试搜索 - 使用修正后的城市代码
        keyword = "风险管理"
        city = "shanghai"  # 现在应该正确映射到上海
        
        logger.info(f"🔍 搜索测试: {keyword} 在 {city}")
        logger.info(f"📍 城市代码: {spider.city_codes[city]}")
        
        # 执行搜索
        jobs = await spider.search_jobs(keyword, city, 5)
        
        if jobs:
            logger.info(f"✅ 成功提取到 {len(jobs)} 个岗位")
            
            # 分析提取的岗位质量
            for i, job in enumerate(jobs, 1):
                logger.info(f"\n{'='*40}")
                logger.info(f"📋 岗位 {i} 详细信息:")
                logger.info(f"   标题: {job.get('title', 'N/A')}")
                logger.info(f"   公司: {job.get('company', 'N/A')}")
                logger.info(f"   地点: {job.get('work_location', 'N/A')}")
                logger.info(f"   薪资: {job.get('salary', 'N/A')}")
                logger.info(f"   链接: {job.get('url', 'N/A')[:60]}...")
                
                # 验证数据质量
                quality_checks = []
                if job.get('title') and job.get('title') != '未知':
                    quality_checks.append("✅ 标题有效")
                else:
                    quality_checks.append("❌ 标题缺失")
                    
                if job.get('company') and job.get('company') not in ['未知公司', '未知']:
                    quality_checks.append("✅ 公司有效")
                else:
                    quality_checks.append("❌ 公司缺失")
                    
                if job.get('work_location') and job.get('work_location') not in ['未知地点', '未知']:
                    quality_checks.append("✅ 地点有效")
                else:
                    quality_checks.append("❌ 地点缺失")
                    
                if job.get('salary') and job.get('salary') != '面议':
                    quality_checks.append("✅ 薪资有效")
                else:
                    quality_checks.append("⚠️ 薪资待议")
                    
                if job.get('url') and job.get('url').startswith('http'):
                    quality_checks.append("✅ 链接有效")
                else:
                    quality_checks.append("❌ 链接缺失")
                
                logger.info(f"   质量评估: {' | '.join(quality_checks)}")
            
            # 整体评估
            valid_jobs = sum(1 for job in jobs if 
                           job.get('company') not in ['未知公司', '未知', None] and
                           job.get('work_location') not in ['未知地点', '未知', None])
            
            success_rate = valid_jobs / len(jobs) * 100 if jobs else 0
            
            logger.info(f"\n📊 整体评估:")
            logger.info(f"   总岗位数: {len(jobs)}")
            logger.info(f"   有效岗位: {valid_jobs}")
            logger.info(f"   成功率: {success_rate:.1f}%")
            
            if success_rate >= 80:
                logger.info("🎉 修复效果优秀！")
            elif success_rate >= 60:
                logger.info("✅ 修复效果良好，有所改善")
            else:
                logger.warning("⚠️ 修复效果有限，仍需进一步优化")
            
            # 测试城市匹配
            shanghai_jobs = sum(1 for job in jobs if 
                              job.get('work_location') and '上海' in job.get('work_location'))
            
            if shanghai_jobs > 0:
                logger.info(f"✅ 城市代码修复成功：{shanghai_jobs}/{len(jobs)} 个岗位在上海")
            else:
                logger.warning("⚠️ 城市代码可能仍有问题：未找到上海岗位")
                
        else:
            logger.warning("⚠️ 未提取到任何岗位")
            success_rate = 0
        
        await spider.close()
        return success_rate >= 60
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("🧪 Boss直聘选择器修复测试")
    print("=" * 50)
    print("本测试将验证以下修复:")
    print("1. ✅ 城市代码修正（上海、杭州）")
    print("2. 🔍 精确的岗位选择器")
    print("3. 🏢 优化的公司名称提取")
    print("4. 💰 改进的薪资信息处理")
    print("5. 📍 智能的地点信息提取")
    print("6. 🚫 无效元素过滤")
    print()
    
    success = asyncio.run(test_selector_fixes())
    
    if success:
        print("\n🎉 测试通过！选择器修复效果良好")
        print("💡 建议现在运行完整应用进行验证: python run_web.py")
    else:
        print("\n❌ 测试未通过，可能需要进一步调试")
        print("💡 请查看日志信息分析具体问题")


if __name__ == "__main__":
    main()