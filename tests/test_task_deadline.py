#!/usr/bin/env python3
"""任务限时策略（阶段 P 事故修复）

事故：20 岗 + Claude 推理分析必超 300s 固定限时；更糟的是分析完成后的
超时检查点把已花钱拿到的结果整体作废（error=timeout, deadline_sec=300）。

契约：
- `_task_deadline_seconds(max_jobs) = _TASK_DEADLINE_SECONDS + 30 * max_jobs`
- 分析完成（结果在手）后的检查点只认用户取消，不再因超时作废结果
- 分析之前的超时保护维持（防挂死任务侵占资源）
"""

import json as _json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ORIGIN = {"Origin": "http://localhost:3001"}

CRAWLED_JOB = {"title": "风险经理", "company": "X公司", "salary": "20-35K",
               "url": "https://www.zhipin.com/job_detail/ddl001.html",
               "job_description": "风险计量"}


@pytest.fixture(autouse=True)
def _reset_invite_limiter():
    from backend.rate_limiter import invite_limiter
    invite_limiter._failures.clear()
    invite_limiter._blacklist.clear()
    yield


@pytest.fixture
def store(tmp_path):
    from utils.state_store import StateStore
    s = StateStore(db_path=str(tmp_path / "ddl.db"))
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


def _wait(predicate, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _authed(app, store):
    code = store.create_invite()
    uid, token = store.consume_invite(code)
    store.set_resume(uid, "四年市场风险经验", filename="r.pdf")
    client = app.test_client()
    client.set_cookie("boss_session", token, domain="localhost")
    return client, uid


class TestDeadlineFormula:
    def test_scales_with_max_jobs(self):
        from backend.app import _task_deadline_seconds, _TASK_DEADLINE_SECONDS
        assert _task_deadline_seconds(20) == _TASK_DEADLINE_SECONDS + 30 * 20
        assert _task_deadline_seconds(5) == _TASK_DEADLINE_SECONDS + 30 * 5

    def test_twenty_jobs_gets_at_least_15_minutes(self):
        from backend.app import _task_deadline_seconds
        assert _task_deadline_seconds(20) >= 900


class TestResultsSurviveDeadline:
    def test_slow_analysis_still_writes_results(self, app, store, monkeypatch):
        """限时在分析期间耗尽 → 结果仍必须落盘为 success（钱已花，不作废）"""
        client, uid = _authed(app, store)
        # 限时极小：分析前检查点来得及通过，分析中耗尽
        monkeypatch.setattr("backend.app._task_deadline_seconds", lambda n: 0.5)

        async def _fake_search(keyword, city, max_jobs, **kwargs):
            return [dict(CRAWLED_JOB)]

        class _SlowAnalyzer:
            def __init__(self, **kwargs):
                self.discarded_jobs = []

            def analyze_jobs(self, jobs, **kw):
                time.sleep(0.8)  # 超过 0.5s 限时
                return [dict(j, score=7, final_decision="apply") for j in jobs]

        monkeypatch.setattr("backend.app.unified_search_jobs", _fake_search)
        monkeypatch.setattr("backend.app.EnhancedJobAnalyzer", _SlowAnalyzer)

        r = client.post("/api/jobs/search", json={"keyword": "风险"}, headers=ORIGIN)
        assert r.status_code == 202
        task_id = r.get_json()["task_id"]
        assert _wait(lambda: store._get_task_unscoped(task_id)["status"]
                     not in ("pending", "running"))
        task = store._get_task_unscoped(task_id)
        assert task["status"] == "success", \
            f"分析已完成的任务被超时作废: {task['result_json'][:120]}"
        result = _json.loads(task["result_json"])
        assert result["analyzed_jobs"], "结果应完整落盘"

    def test_timeout_before_analysis_still_aborts(self, app, store, monkeypatch):
        """分析开始前就超时 → 仍应中止（保护资源，行为不回归）"""
        client, uid = _authed(app, store)
        monkeypatch.setattr("backend.app._task_deadline_seconds", lambda n: 0.2)

        async def _slow_search(keyword, city, max_jobs, **kwargs):
            import asyncio
            await asyncio.sleep(0.6)  # 爬取阶段就耗尽限时
            return [dict(CRAWLED_JOB)]

        called = {"analyze": False}

        class _Analyzer:
            def __init__(self, **kwargs):
                self.discarded_jobs = []

            def analyze_jobs(self, jobs, **kw):
                called["analyze"] = True
                return jobs

        monkeypatch.setattr("backend.app.unified_search_jobs", _slow_search)
        monkeypatch.setattr("backend.app.EnhancedJobAnalyzer", _Analyzer)

        r = client.post("/api/jobs/search", json={"keyword": "风险"}, headers=ORIGIN)
        assert r.status_code == 202
        task_id = r.get_json()["task_id"]
        assert _wait(lambda: store._get_task_unscoped(task_id)["status"]
                     not in ("pending", "running"))
        task = store._get_task_unscoped(task_id)
        assert task["status"] == "failed"
        assert "timeout" in (task["result_json"] or "")
        assert called["analyze"] is False, "超时后不应再进入分析（继续烧钱）"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
