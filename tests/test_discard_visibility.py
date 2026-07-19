#!/usr/bin/env python3
"""Discard 可见化（spec 阶段 P1）

被阶段 0（hard_filter）/ 阶段 1（类型二分类）踢掉的岗位必须可见：
analyzer.discarded_jobs 属性 + 任务 result_payload 带 discarded 列表。
"""

import json as _json
import os
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ORIGIN = {"Origin": "http://localhost:3001"}


def _make_analyzer(screening_mode=True):
    from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer
    analyzer = EnhancedJobAnalyzer(
        extraction_provider="deepseek", analysis_provider="deepseek",
        extraction_model_name="deepseek-v4-flash", screening_mode=screening_mode)
    return analyzer


def _fake_ai(analyzer, screening_answer: str, match_json: dict):
    """把两阶段 AI 都换成假件：阶段一回 screening_answer，阶段二回 match_json"""
    fake = MagicMock()

    def _dispatch(prompt, **kwargs):
        # 粗筛 prompt 短、带"是/否"语义；匹配 prompt 带简历。粗暴按 max_tokens 区分：
        if kwargs.get("max_tokens", 0) <= 200:
            return screening_answer
        return _json.dumps(match_json, ensure_ascii=False)

    fake.call_api_simple.side_effect = _dispatch
    analyzer.job_analyzer.ai_client = fake
    analyzer.extraction_service = fake
    return fake


JOB_OK = {"title": "市场风险经理", "company": "好公司",
          "job_description": "负责风险计量", "salary": "20-30K"}
JOB_BAD = {"title": "AI课程销售", "company": "培训机构",
           "job_description": "卖课", "salary": "5-8K"}


class TestAnalyzerDiscards:
    def test_screening_reject_recorded(self):
        analyzer = _make_analyzer(screening_mode=True)
        _fake_ai(analyzer, screening_answer="否",
                 match_json={"score": 7, "reason": "ok", "final_decision": "apply"})
        out = analyzer.analyze_jobs([dict(JOB_BAD)], resume_text="简历", keyword="风险")
        assert out == [] or all(j.get("title") != "AI课程销售" for j in out)
        assert hasattr(analyzer, "discarded_jobs"), "缺少 discarded_jobs 属性"
        assert len(analyzer.discarded_jobs) == 1
        entry = analyzer.discarded_jobs[0]
        assert entry["title"] == "AI课程销售"
        assert entry["company"] == "培训机构"
        assert entry["stage"] == "screening"
        assert entry["reason"], "reason 不能为空"

    def test_hard_filter_reject_recorded(self):
        analyzer = _make_analyzer(screening_mode=False)
        _fake_ai(analyzer, screening_answer="是",
                 match_json={"score": 7, "reason": "ok", "final_decision": "apply"})
        # 硬过滤：排除关键词命中标题
        analyzer.analyze_jobs(
            [dict(JOB_BAD)], resume_text="简历", keyword="风险",
            hard_filters={"exclude_keywords": ["销售"]})
        assert any(e["stage"] == "hard_filter" for e in analyzer.discarded_jobs), \
            f"hard_filter 弃用未记录: {analyzer.discarded_jobs}"
        entry = [e for e in analyzer.discarded_jobs if e["stage"] == "hard_filter"][0]
        assert entry["reason"]

    def test_discards_reset_between_runs(self):
        analyzer = _make_analyzer(screening_mode=True)
        _fake_ai(analyzer, screening_answer="否",
                 match_json={"score": 7, "reason": "ok"})
        analyzer.analyze_jobs([dict(JOB_BAD)], resume_text="简历", keyword="风险")
        first = len(analyzer.discarded_jobs)
        assert first == 1
        # 第二轮全过（阶段一回"是"）
        _fake_ai(analyzer, screening_answer="是",
                 match_json={"score": 7, "reason": "ok", "final_decision": "apply"})
        analyzer.analyze_jobs([dict(JOB_OK)], resume_text="简历", keyword="风险")
        assert analyzer.discarded_jobs == [], "discarded_jobs 未在新一轮重置"

    def test_passed_jobs_not_in_discards(self):
        analyzer = _make_analyzer(screening_mode=True)
        _fake_ai(analyzer, screening_answer="是",
                 match_json={"score": 7, "reason": "ok", "final_decision": "apply"})
        analyzer.analyze_jobs([dict(JOB_OK)], resume_text="简历", keyword="风险")
        assert analyzer.discarded_jobs == []


# ─── app 层：result_payload 带 discarded ─────────────────


@pytest.fixture(autouse=True)
def _reset_invite_limiter():
    from backend.rate_limiter import invite_limiter
    invite_limiter._failures.clear()
    invite_limiter._blacklist.clear()
    yield


@pytest.fixture
def store(tmp_path):
    from utils.state_store import StateStore
    s = StateStore(db_path=str(tmp_path / "discard.db"))
    s.init_schema()
    return s


@pytest.fixture
def app(store, monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-12345678-aaaaaaaa")
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from backend.app import create_app
    application = create_app(store=store)
    application.config["TESTING"] = True
    return application


def _wait(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


class TestResultPayloadDiscards:
    def test_result_json_contains_discarded(self, app, store, monkeypatch):
        code = store.create_invite()
        uid, token = store.consume_invite(code)
        store.set_resume(uid, "四年风险经验", filename="r.pdf")

        async def _fake_search(keyword, city, max_jobs, **kwargs):
            return [dict(JOB_OK), dict(JOB_BAD)]

        class _FakeAnalyzer:
            def __init__(self, **kwargs):
                self.discarded_jobs = [{"title": "AI课程销售", "company": "培训机构",
                                        "stage": "screening", "reason": "类型不符"}]

            def analyze_jobs(self, jobs, resume_text="", keyword="", **kw):
                return [{"title": "市场风险经理", "company": "好公司", "score": 7}]

        monkeypatch.setattr("backend.app.unified_search_jobs", _fake_search)
        monkeypatch.setattr("backend.app.EnhancedJobAnalyzer", _FakeAnalyzer)

        client = app.test_client()
        client.set_cookie("boss_session", token, domain="localhost")
        r = client.post("/api/jobs/search", json={"keyword": "风险"}, headers=ORIGIN)
        assert r.status_code == 202
        task_id = r.get_json()["task_id"]
        ok = _wait(lambda: store._get_task_unscoped(task_id)["status"]
                   not in ("pending", "running"))
        assert ok
        task = store._get_task_unscoped(task_id)
        assert task["status"] == "success"
        result = _json.loads(task["result_json"])
        assert result.get("discarded_count") == 1
        assert result["discarded"][0]["title"] == "AI课程销售"
        assert result["discarded"][0]["reason"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
