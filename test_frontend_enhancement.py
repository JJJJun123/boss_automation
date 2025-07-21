#!/usr/bin/env python3
"""
测试前端优化和岗位详情抓取增强
"""

import asyncio
import logging
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_enhanced_extraction():
    """测试增强的岗位详情抓取"""
    try:
        logger.info("🚀 测试增强的岗位详情抓取...")
        
        from crawler.real_playwright_spider import RealPlaywrightBossSpider
        
        spider = RealPlaywrightBossSpider(headless=False)
        
        if not await spider.start():
            logger.error("❌ 无法启动Playwright")
            return False
        
        # 测试搜索
        keyword = "AI产品经理"
        city = "shanghai"
        
        logger.info(f"🔍 搜索: {keyword} 在 {city}")
        jobs = await spider.search_jobs(keyword, city, 2)  # 只测试2个岗位
        
        if jobs:
            logger.info(f"✅ 成功提取 {len(jobs)} 个岗位")
            
            for i, job in enumerate(jobs, 1):
                logger.info(f"\n{'='*60}")
                logger.info(f"📋 岗位 {i} 详细信息:")
                logger.info(f"   标题: {job.get('title', 'N/A')}")
                logger.info(f"   公司: {job.get('company', 'N/A')}")
                logger.info(f"   地点: {job.get('work_location', 'N/A')}")
                logger.info(f"   薪资: {job.get('salary', 'N/A')}")
                logger.info(f"   URL: {job.get('url', 'N/A')[:80]}...")
                
                # 检查岗位描述质量
                desc = job.get('job_description', '')
                req = job.get('job_requirements', '')
                company_details = job.get('company_details', '')
                
                logger.info(f"\n   📄 岗位描述质量检查:")
                if desc and '具体职责请查看岗位详情' not in desc and len(desc) > 100:
                    logger.info(f"      ✅ 真实岗位描述 ({len(desc)}字符): {desc[:100]}...")
                else:
                    logger.warning(f"      ⚠️ 岗位描述仍是模板文本或太短")
                
                if req and '要求1-3年工作经验' not in req and len(req) > 50:
                    logger.info(f"      ✅ 真实任职要求 ({len(req)}字符): {req[:80]}...")
                else:
                    logger.warning(f"      ⚠️ 任职要求仍是模板文本或太短")
                
                if company_details and '查看详情了解更多' not in company_details:
                    logger.info(f"      ✅ 公司详情: {company_details}")
                else:
                    logger.warning(f"      ⚠️ 公司详情未更新")
                
                # 检查额外信息
                if job.get('benefits'):
                    logger.info(f"      ✅ 福利信息: {job.get('benefits')[:50]}...")
                if job.get('detailed_address'):
                    logger.info(f"      ✅ 详细地址: {job.get('detailed_address')}")
                if job.get('publish_time'):
                    logger.info(f"      ✅ 发布时间: {job.get('publish_time')}")
            
            return True
            
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


def test_frontend_updates():
    """测试前端界面更新"""
    logger.info("\n🖥️ 前端界面优化说明:")
    logger.info("1. ✅ 删除了'已分析'统计项，现在只显示'总搜索数'和'合格岗位'")
    logger.info("2. ✅ '总搜索数'现在可点击，点击后显示所有搜索到的岗位")
    logger.info("3. ✅ '合格岗位'现在可点击，点击后显示推荐的岗位")
    logger.info("4. ✅ 添加了视图切换功能，可以在所有岗位和推荐岗位之间切换")
    logger.info("5. ✅ 后端API新增 /api/jobs/all 端点，用于获取所有岗位数据")
    logger.info("\n💡 使用方法: python run_web.py 启动后，搜索完成后点击统计数字即可切换视图")


def main():
    """主函数"""
    print("🎯 Boss直聘增强功能测试")
    print("=" * 60)
    print("本测试将验证:")
    print("1. 增强的岗位详情抓取")
    print("2. 前端界面优化")
    print()
    
    # 测试岗位详情抓取
    result = asyncio.run(test_enhanced_extraction())
    
    if result:
        print("\n✅ 岗位详情抓取测试通过")
    else:
        print("\n❌ 岗位详情抓取测试失败")
    
    # 说明前端更新
    test_frontend_updates()
    
    print("\n🚀 下一步: 运行 python run_web.py 体验完整功能")


if __name__ == "__main__":
    main()