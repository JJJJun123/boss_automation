#!/usr/bin/env python3
"""
详情页提取相关单元测试

详情提取改为"点击列表卡片→读右侧面板(.job-detail-box)"，绕开直接 goto
/job_detail/ 被反爬弹回的问题。这里测可纯函数化的辅助（从 URL 提取岗位 id、
清洗公司名）；点击/面板提取的真实行为由集成测试覆盖。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.real_playwright_spider import RealPlaywrightBossSpider


def test_job_id_from_absolute_url():
    """绝对 URL 提取岗位 id"""
    spider = RealPlaywrightBossSpider()
    url = "https://www.zhipin.com/job_detail/ca356e9f5913ae6203F82964GFZR.html"
    assert spider._job_id_from_url(url) == "ca356e9f5913ae6203F82964GFZR"


def test_job_id_from_relative_url():
    """相对 URL 也能提取岗位 id（卡片 href 是相对路径）"""
    spider = RealPlaywrightBossSpider()
    assert spider._job_id_from_url("/job_detail/649ccc31ea51cad6031-3Nm9ElFR.html") == "649ccc31ea51cad6031-3Nm9ElFR"


def test_job_id_from_url_with_query():
    """带查询参数的 URL 也能提取干净 id"""
    spider = RealPlaywrightBossSpider()
    url = "https://www.zhipin.com/job_detail/abc123.html?ka=search_list_1"
    assert spider._job_id_from_url(url) == "abc123"


def test_company_from_boss_attr():
    """从 '公司 · 角色' 文本提取公司名（修复公司字段误取职位名的 bug）"""
    spider = RealPlaywrightBossSpider()
    assert spider._company_from_boss_attr("大神网络科技 · 人事") == "大神网络科技"
    assert spider._company_from_boss_attr("徐州大神网络科技有限公司·HR") == "徐州大神网络科技有限公司"
    assert spider._company_from_boss_attr("") == ""


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
