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


# ─── _extract_job_detail_page 详情面板提取（mock 版）───
# 列表卡片在反爬/未登录态下常拿不到薪资，统一兜底成 "薪资面议"。
# 修复：详情面板 .job-detail-box .salary 几乎总有真实薪资文本，应抓取并覆盖列表兜底值。
# 这里 mock _panel_text + page，避免拉真 Chrome；只验证编排逻辑：
#   1) 面板有薪资 → 返回 dict 含 'salary' 字段
#   2) 面板无薪资 → 返回 dict 不含 'salary' 字段（避免覆盖列表卡片真实薪资）

from unittest.mock import AsyncMock, MagicMock, patch


def _build_spider_with_mock_page():
    """构造 spider，把 self.page 替换为 MagicMock，使卡片点击与 wait_for_selector 通过"""
    spider = RealPlaywrightBossSpider()
    page = MagicMock()
    card_chain = MagicMock()
    card_chain.first = MagicMock()
    card_chain.first.click = AsyncMock()
    page.locator = MagicMock(return_value=card_chain)
    page.wait_for_selector = AsyncMock()
    spider.page = page
    return spider


def _run_detail_extract(spider, panel_map: dict) -> dict:
    """跑 _extract_job_detail_page，让 _panel_text 按 selector→文本映射返回"""
    spider._panel_text = AsyncMock(side_effect=lambda selector: panel_map.get(selector, ""))
    # asyncio.sleep(0.6) 真等会拖慢；mock 成立即返回
    with patch("crawler.real_playwright_spider.asyncio.sleep", new=AsyncMock()):
        return asyncio.run(spider._extract_job_detail_page(
            "https://www.zhipin.com/job_detail/abc123XYZ.html"
        ))


def test_detail_extraction_returns_salary_from_panel():
    """面板抓到薪资 → 返回 dict 含 salary 字段，调用方 {**job, **details} 会覆盖列表兜底值"""
    spider = _build_spider_with_mock_page()
    panel = {
        ".job-detail-box .desc": "搭建 LLM 应用，要求 Python、PyTorch、RAG。",
        ".job-detail-box .boss-info-attr": "某 AI 公司 · HR",
        ".job-detail-box .salary": "30-50K·14薪",
        ".job-detail-box .job-address-desc": "上海市浦东新区张江",
    }
    result = _run_detail_extract(spider, panel)
    assert result.get("salary") == "30-50K·14薪", \
        "面板抓到薪资必须放进结果 dict，否则 {**job, **details} 合并时不会覆盖列表兜底 '薪资面议'"
    assert result["detail_extraction_success"] is True


def test_detail_extraction_omits_salary_when_panel_empty():
    """面板没抓到薪资 → 不返回 salary 字段，保留列表卡片原值（避免误覆盖真实薪资）"""
    spider = _build_spider_with_mock_page()
    panel = {
        ".job-detail-box .desc": "JD 内容...",
        ".job-detail-box .boss-info-attr": "某公司 · HR",
        # 故意缺 .salary 与 .job-address-desc，模拟面板无该字段
    }
    result = _run_detail_extract(spider, panel)
    assert "salary" not in result, \
        "面板无薪资时不能塞空串/None 进结果 dict，否则 {**job, **details} 会把列表卡片的真实薪资覆盖掉"


def test_detail_extraction_rejects_invalid_salary_text():
    """面板节点存在但内容不是真实薪资（如说明文案）—— 不能采纳，避免覆盖列表卡片真实值

    Codex review 指出：原实现 `[class*="salary"]` 选择器太宽、可能命中 tip/wrapper 节点，
    然后把"薪资范围说明"这类非数字文本写进 result['salary'] 覆盖真实值。
    薪资写入前必须做格式校验：至少含数字 + (K|万|薪|元) 之一。
    """
    spider = _build_spider_with_mock_page()
    panel = {
        ".job-detail-box .desc": "JD",
        ".job-detail-box .boss-info-attr": "X · HR",
        ".job-detail-box .salary": "薪资范围说明",  # 非数字，明显不是真薪资
    }
    result = _run_detail_extract(spider, panel)
    assert "salary" not in result, \
        "panel 节点文本无数字+(K|万|薪|元)，不是真实薪资，应拒绝写入避免覆盖列表卡片"


def test_extract_panel_salary_validates_format():
    """直接测 _extract_panel_salary 的格式校验逻辑"""
    spider = _build_spider_with_mock_page()
    # 命中第一个选择器，但文本是垃圾 → 应继续找下一个
    spider._panel_text = AsyncMock(side_effect=lambda s: {
        ".job-detail-box .salary": "薪资说明 (备注)",   # 无数字+K/万 → 不算
    }.get(s, ""))
    result = asyncio.run(spider._extract_panel_salary())
    assert result == "", "无效薪资文本应被拒绝，返回空串让调用方保留列表卡片原值"


def test_extract_panel_salary_accepts_valid_formats():
    """各种真实薪资格式都应通过"""
    spider = _build_spider_with_mock_page()
    for valid_text in ["30-50K·14薪", "25-40K", "15K-30K", "30万-50万/年", "200元/天"]:
        spider._panel_text = AsyncMock(return_value=valid_text)
        result = asyncio.run(spider._extract_panel_salary())
        assert result == valid_text, f"真实薪资 '{valid_text}' 应通过校验"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
