#!/usr/bin/env python3
"""
本地集成测试：验证 Boss 直聘爬虫全流程
运行方式：python tests/integration_test_crawl.py

会打开浏览器 → 检测登录（未登录则等你手动扫码）→ 搜索 → 提取岗位 → 打印结果
"""

import asyncio
import logging
import sys
import os
import time

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.real_playwright_spider import RealPlaywrightBossSpider

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("integration_test")

# ─── 测试参数 ───
KEYWORD = "数据分析"
CITY = "shanghai"
MAX_JOBS = 5  # 少量即可验证


async def run_test():
    spider = RealPlaywrightBossSpider(headless=False)
    start = time.time()

    try:
        # Step 1: 启动浏览器
        logger.info("=" * 60)
        logger.info("Step 1: 启动浏览器")
        logger.info("=" * 60)
        ok = await spider.start()
        assert ok, "浏览器启动失败"
        logger.info("✅ 浏览器启动成功")

        # Step 2: 搜索岗位
        logger.info("=" * 60)
        logger.info(f"Step 2: 搜索岗位 keyword={KEYWORD} city={CITY} max={MAX_JOBS}")
        logger.info("=" * 60)
        jobs = await spider.search_jobs(keyword=KEYWORD, city=CITY, max_jobs=MAX_JOBS)

        # Step 3: 验证结果
        logger.info("=" * 60)
        logger.info("Step 3: 验证结果")
        logger.info("=" * 60)

        if not jobs:
            logger.error("❌ 未获取到任何岗位！全流程失败。")
            logger.error("可能原因：登录失败 / 反爬拦截 / 页面结构变更")
            return False

        logger.info(f"✅ 获取到 {len(jobs)} 个岗位")

        # 检查每个岗位的必要字段
        required_fields = ['title', 'company', 'salary']
        for i, job in enumerate(jobs):
            missing = [f for f in required_fields if not job.get(f)]
            status = "✅" if not missing else "⚠️"
            logger.info(
                f"  {status} [{i+1}] {job.get('title', '???')} | "
                f"{job.get('company', '???')} | {job.get('salary', '???')}"
            )
            if missing:
                logger.warning(f"      缺少字段: {missing}")

        # 打印第一个岗位的完整数据
        logger.info("-" * 40)
        logger.info("第一个岗位完整数据：")
        for k, v in jobs[0].items():
            val_str = str(v)[:100]
            logger.info(f"  {k}: {val_str}")

        elapsed = time.time() - start
        logger.info("=" * 60)
        logger.info(f"✅ 全流程通过！耗时 {elapsed:.1f}s，获取 {len(jobs)} 个岗位")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"❌ 测试异常: {e}", exc_info=True)
        return False

    finally:
        await spider.close()


if __name__ == "__main__":
    success = asyncio.run(run_test())
    sys.exit(0 if success else 1)
