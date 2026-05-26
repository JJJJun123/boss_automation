import inspect
import logging
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer


SAMPLE_JOBS = [
    {
        "title": "数据分析师",
        "company": "测试公司",
        "salary": "15-25K",
        "job_description": "负责数据分析和报表制作，要求熟悉Python、SQL",
    }
]
SAMPLE_RESUME = "拥有3年数据分析经验，熟悉Python和SQL"


def test_analyze_jobs_accepts_resume_text():
    analyzer = EnhancedJobAnalyzer()
    sig = inspect.signature(analyzer.analyze_jobs)
    assert "resume_text" in sig.parameters


def test_analyze_jobs_returns_score_and_match_info():
    screen_resp = '{"relevant": true, "reason": "类型匹配"}'
    match_resp = '{"score": 8, "match_highlights": ["Python经验匹配"], "gaps": ["缺乏大数据经验"], "summary": "整体匹配度较高"}'

    analyzer = EnhancedJobAnalyzer()
    with patch.object(analyzer, "_call_ai_for_screening", return_value=screen_resp), patch.object(
        analyzer, "_call_ai_for_matching", return_value=match_resp
    ):
        results = analyzer.analyze_jobs(SAMPLE_JOBS, resume_text=SAMPLE_RESUME)

    assert len(results) == 1
    assert results[0]["score"] == 8
    assert "match_highlights" in results[0]
    assert "gaps" in results[0]
    assert "summary" in results[0]


def test_analyze_jobs_filters_irrelevant():
    screen_resp = '{"relevant": false, "reason": "不相关"}'
    analyzer = EnhancedJobAnalyzer()

    with patch.object(analyzer, "_call_ai_for_screening", return_value=screen_resp):
        results = analyzer.analyze_jobs(SAMPLE_JOBS, resume_text=SAMPLE_RESUME)

    assert len(results) == 0


# ─── Stage 2 token 配额 + 解析失败诊断 ───
# Bug: 用户实测 3/3 jobs 全 "解析失败 + 0/10"。根因：thinking 模式下 reasoning + content
# 共占 max_tokens，但 _call_ai_for_matching 没显式传 max_tokens 用默认 1000，
# reasoning 吃光后 content 输出 JSON 被截断 → 正则匹配失败 → 兜底"解析失败"。

def test_call_ai_for_matching_passes_large_max_tokens():
    """匹配阶段必须显式传足够大的 max_tokens（>=4000）

    thinking 模式 reasoning + content 共占 max_tokens；默认 1000 会被 reasoning
    吃光导致 JSON content 截断。回归测试：确保 max_tokens 显式传值且足够大。
    """
    analyzer = EnhancedJobAnalyzer()
    fake_client = MagicMock()
    fake_client.call_api_simple = MagicMock(return_value='{"score": 7}')
    analyzer.job_analyzer = MagicMock()
    analyzer.job_analyzer.ai_client = fake_client

    job = {"title": "X", "company": "Y", "job_description": "JD", "job_requirements": "REQ"}
    analyzer._call_ai_for_matching(job, "resume text")

    args, kwargs = fake_client.call_api_simple.call_args
    assert kwargs.get('thinking') is True, "Stage 2 必须开 thinking"
    max_tokens = kwargs.get('max_tokens')
    assert max_tokens is not None, "必须显式传 max_tokens，不能依赖 client 默认 1000（thinking 模式下不够）"
    assert max_tokens >= 4000, f"max_tokens 至少 4000 才能容纳 thinking + content，当前 {max_tokens}"


def test_parse_match_result_logs_raw_response_on_failure(caplog):
    """解析失败时必须把 raw response 前缀写入日志，便于诊断截断/格式问题

    现状只返回兜底 dict 没留任何痕迹，重新跑搜索才能复现，效率低。
    """
    analyzer = EnhancedJobAnalyzer()
    # 模拟 thinking 截断后的非 JSON 文本（reasoning 写完但 content 未输出 JSON）
    truncated_response = "好的，我来分析一下这份简历和岗位的匹配度。首先看简历，候选人有数据分析背景..."

    with caplog.at_level(logging.WARNING):
        result = analyzer._parse_match_result(truncated_response)

    assert result["summary"] == "解析失败", "兜底结果不变"
    assert result["score"] == 0
    # 日志中必须含 raw 响应片段，便于诊断
    assert any(
        "raw" in record.message.lower() or "好的" in record.message
        for record in caplog.records
    ), "解析失败必须把 raw response 片段写入日志，否则无法诊断"


def test_parse_match_result_logs_on_invalid_json(caplog):
    """JSON 块存在但内容非法（典型截断症状）也要落日志

    注：正则 `\{.*\}` 找不到闭合 `}`，所以走"未找到 JSON 块"分支（warning），
    不是"json.loads 抛异常"分支（error）。两条路径都该记录 raw 文本。
    """
    analyzer = EnhancedJobAnalyzer()
    # 截断的 JSON：开头有 {，中间断（典型 token 用尽症状）
    bad_json = '{"score": 8, "match_highlights": ["技能匹配", "经验相'

    with caplog.at_level(logging.WARNING):
        result = analyzer._parse_match_result(bad_json)

    assert result["summary"] == "解析失败"
    assert any("raw" in record.message.lower() or "match_highlights" in record.message
               for record in caplog.records), "JSON 截断应记录 raw 文本到日志"


def test_analyze_jobs_sorted_by_score_descending():
    jobs = [
        {"title": "岗位A", "company": "A", "salary": "10K", "job_description": "A"},
        {"title": "岗位B", "company": "B", "salary": "20K", "job_description": "B"},
    ]
    screen_resp = '{"relevant": true, "reason": "相关"}'
    match_resps = iter(
        [
            '{"score": 5, "match_highlights": [], "gaps": [], "summary": "一般"}',
            '{"score": 9, "match_highlights": [], "gaps": [], "summary": "优秀"}',
        ]
    )

    analyzer = EnhancedJobAnalyzer()
    with patch.object(analyzer, "_call_ai_for_screening", return_value=screen_resp), patch.object(
        analyzer, "_call_ai_for_matching", side_effect=lambda job, resume_text: next(match_resps)
    ):
        results = analyzer.analyze_jobs(jobs, resume_text=SAMPLE_RESUME)

    assert len(results) == 2
    assert results[0]["score"] >= results[1]["score"]

