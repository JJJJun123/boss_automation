import inspect
import os
import sys
from unittest.mock import patch

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

