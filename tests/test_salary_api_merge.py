#!/usr/bin/env python3
"""薪资来源切换：DOM 字体反爬 → 搜索 API 明文（2026-07 Boss 改版事故）

实测：列表卡片 .job-salary 渲染为 "-K·薪"（数字用自定义字体私有码位，
innerText 提不出）；但页面自身调用的 /wapi/zpgeek/search/joblist.json
返回明文 salaryDesc。爬虫监听该响应建 job_id → 数据映射，合并进提取结果。

契约：
- `RealPlaywrightBossSpider._ingest_joblist_payload(payload: dict) -> int`
  解析 API 响应体，写入 `self._api_job_map`（key=encryptJobId），返回新增条数
- `RealPlaywrightBossSpider._merge_api_job_data(jobs: list) -> list`
  按 URL 中的 job_id 匹配映射：API 薪资通过格式校验则覆盖 DOM 薪资
  （DOM 值已知不可信）；无匹配保持原值；同时补空缺的 title/company
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawler.real_playwright_spider import RealPlaywrightBossSpider

PAYLOAD = {
    "code": 0,
    "zpData": {
        "jobList": [
            {"encryptJobId": "abc123", "jobName": "风险策略专家",
             "salaryDesc": "25-35K·13薪", "brandName": "金棠美家"},
            {"encryptJobId": "def456", "jobName": "风险总监",
             "salaryDesc": "65-75K", "brandName": "某上市公司"},
            {"encryptJobId": "bad789", "jobName": "无效薪资岗",
             "salaryDesc": "", "brandName": "X"},
        ]
    },
}


def _spider():
    return RealPlaywrightBossSpider()


class TestIngestPayload:
    def test_populates_map(self):
        s = _spider()
        n = s._ingest_joblist_payload(PAYLOAD)
        assert n == 3
        assert s._api_job_map["abc123"]["salary"] == "25-35K·13薪"
        assert s._api_job_map["def456"]["title"] == "风险总监"

    def test_accumulates_across_pages(self):
        """滚动翻页会多次触发接口——映射应累积而非覆盖"""
        s = _spider()
        s._ingest_joblist_payload(PAYLOAD)
        page2 = {"zpData": {"jobList": [
            {"encryptJobId": "ggg000", "jobName": "岗位4",
             "salaryDesc": "10-15K", "brandName": "Y"}]}}
        s._ingest_joblist_payload(page2)
        assert "abc123" in s._api_job_map and "ggg000" in s._api_job_map

    def test_malformed_payload_safe(self):
        s = _spider()
        assert s._ingest_joblist_payload({}) == 0
        assert s._ingest_joblist_payload({"zpData": None}) == 0
        assert s._ingest_joblist_payload({"zpData": {"jobList": "不是列表"}}) == 0


class TestMergeApiData:
    def _jobs(self):
        return [
            {"title": "风险策略专家（消费分期）", "salary": "-K·薪",
             "company": "金棠美家",
             "url": "https://www.zhipin.com/job_detail/abc123.html"},
            {"title": "无API匹配岗", "salary": "薪资面议", "company": "Z",
             "url": "https://www.zhipin.com/job_detail/nomatch.html"},
        ]

    def test_broken_dom_salary_replaced(self):
        s = _spider()
        s._ingest_joblist_payload(PAYLOAD)
        merged = s._merge_api_job_data(self._jobs())
        assert merged[0]["salary"] == "25-35K·13薪"

    def test_unmatched_job_untouched(self):
        s = _spider()
        s._ingest_joblist_payload(PAYLOAD)
        merged = s._merge_api_job_data(self._jobs())
        assert merged[1]["salary"] == "薪资面议"

    def test_invalid_api_salary_not_applied(self):
        """API 薪资为空/不合格式 → 不覆盖（保持现值）"""
        s = _spider()
        s._ingest_joblist_payload(PAYLOAD)
        jobs = [{"title": "无效薪资岗", "salary": "薪资面议", "company": "X",
                 "url": "https://www.zhipin.com/job_detail/bad789.html"}]
        merged = s._merge_api_job_data(jobs)
        assert merged[0]["salary"] == "薪资面议"

    def test_fills_missing_company(self):
        s = _spider()
        s._ingest_joblist_payload(PAYLOAD)
        jobs = [{"title": "风险总监", "salary": "-K·薪", "company": "",
                 "url": "https://www.zhipin.com/job_detail/def456.html"}]
        merged = s._merge_api_job_data(jobs)
        assert merged[0]["company"] == "某上市公司"
        assert merged[0]["salary"] == "65-75K"

    def test_no_url_job_safe(self):
        s = _spider()
        s._ingest_joblist_payload(PAYLOAD)
        merged = s._merge_api_job_data([{"title": "无URL", "salary": "薪资面议"}])
        assert merged[0]["salary"] == "薪资面议"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
