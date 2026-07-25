#!/usr/bin/env python3
"""多关键词搜索任务（spec 阶段 D4）"""

import json as _json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ORIGIN = {"Origin": "http://localhost:3001"}


@pytest.fixture(autouse=True)
def _reset_invite_limiter():
    from backend.rate_limiter import invite_limiter
    invite_limiter._failures.clear()
    invite_limiter._blacklist.clear()
    yield


@pytest.fixture
def store(tmp_path):
    from utils.state_store import StateStore
    s = StateStore(db_path=str(tmp_path / "multikw.db"))
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


def _job(jid, title, kw):
    return {"title": title, "company": f"{kw}公司", "salary": "20-30K",
            "url": f"https://www.zhipin.com/job_detail/{jid}.html",
            "job_description": f"{kw} 相关工作"}


def _passthrough_analyzer(monkeypatch):
    class _A:
        def __init__(self, **kwargs):
            self.discarded_jobs = []

        def analyze_jobs(self, jobs, **kw):
            return [dict(j, score=7, final_decision="apply") for j in jobs]
    monkeypatch.setattr("backend.app.EnhancedJobAnalyzer", _A)


def _run_task(client, store, payload):
    r = client.post("/api/jobs/search", json=payload, headers=ORIGIN)
    assert r.status_code == 202, r.get_json()
    task_id = r.get_json()["task_id"]
    assert _wait(lambda: store._get_task_unscoped(task_id)["status"]
                 not in ("pending", "running"))
    return store._get_task_unscoped(task_id)


class TestDeadlineFormulaMultiKw:
    def test_multi_keyword_adds_crawl_budget(self):
        from backend.app import _task_deadline_seconds, _TASK_DEADLINE_SECONDS
        single = _task_deadline_seconds(15)
        triple = _task_deadline_seconds(45, n_keywords=3)
        assert single == _TASK_DEADLINE_SECONDS + 30 * 15
        assert triple == _TASK_DEADLINE_SECONDS + 30 * 45 + 120 * 2

    def test_single_keyword_unchanged(self):
        from backend.app import _task_deadline_seconds, _TASK_DEADLINE_SECONDS
        assert _task_deadline_seconds(20) == _TASK_DEADLINE_SECONDS + 600


class TestRequestValidation:
    def test_legacy_single_keyword_still_works(self, app, store, monkeypatch):
        client, _ = _authed(app, store)
        _passthrough_analyzer(monkeypatch)

        async def _fake(keyword, city, max_jobs, **kw):
            return [_job("legacy1", "旧接口岗", keyword)]
        monkeypatch.setattr("backend.app.unified_search_jobs", _fake)
        task = _run_task(client, store, {"keyword": "风控", "max_jobs": 10})
        assert task["status"] == "success"

    def test_more_than_three_keywords_400(self, app, store):
        client, _ = _authed(app, store)
        r = client.post("/api/jobs/search",
                        json={"keywords": ["a", "b", "c", "d"]}, headers=ORIGIN)
        assert r.status_code == 400

    def test_per_keyword_clamped(self, app, store, monkeypatch):
        client, _ = _authed(app, store)
        _passthrough_analyzer(monkeypatch)
        captured = []

        async def _fake(keyword, city, max_jobs, **kw):
            captured.append(max_jobs)
            return [_job(f"c{keyword}", "岗", keyword)]
        monkeypatch.setattr("backend.app.unified_search_jobs", _fake)
        _run_task(client, store,
                  {"keywords": ["风控"], "per_keyword": 2})
        assert captured == [5], f"per_keyword 应裁到下限 5，实际 {captured}"
        captured.clear()
        _run_task(client, store,
                  {"keywords": ["风控"], "per_keyword": 999})
        assert captured == [30], f"per_keyword 应裁到上限 30，实际 {captured}"


class TestMultiKeywordExecution:
    def test_each_keyword_crawled_once(self, app, store, monkeypatch):
        client, _ = _authed(app, store)
        _passthrough_analyzer(monkeypatch)
        crawled = []

        async def _fake(keyword, city, max_jobs, **kw):
            crawled.append(keyword)
            return [_job(f"id-{keyword}", f"{keyword}岗", keyword)]
        monkeypatch.setattr("backend.app.unified_search_jobs", _fake)
        task = _run_task(client, store,
                         {"keywords": ["风控", "计量", "合规"], "per_keyword": 5})
        assert task["status"] == "success"
        assert task["keyword"] == "风控，计量，合规"
        assert sorted(crawled) == ["合规", "风控", "计量"] or \
               sorted(crawled) == sorted(["风控", "计量", "合规"])
        result = _json.loads(task["result_json"])
        assert result["analyzed_count"] == 3

    def test_duplicate_job_id_merged(self, app, store, monkeypatch):
        client, _ = _authed(app, store)
        _passthrough_analyzer(monkeypatch)

        async def _fake(keyword, city, max_jobs, **kw):
            # 两个词命中同一岗位 + 各自一个独有岗位
            return [_job("shared01", "共同岗位", keyword),
                    _job(f"uniq-{keyword}", f"{keyword}独有", keyword)]
        monkeypatch.setattr("backend.app.unified_search_jobs", _fake)
        task = _run_task(client, store,
                         {"keywords": ["风控", "计量"], "per_keyword": 5})
        result = _json.loads(task["result_json"])
        titles = [j["title"] for j in result["analyzed_jobs"]]
        assert titles.count("共同岗位") == 1, f"重复岗位未合并: {titles}"
        assert result["analyzed_count"] == 3

    def test_partial_keyword_failure_tolerated(self, app, store, monkeypatch):
        client, _ = _authed(app, store)
        _passthrough_analyzer(monkeypatch)

        async def _fake(keyword, city, max_jobs, **kw):
            if keyword == "坏词":
                raise RuntimeError("爬取失败")
            return [_job(f"ok-{keyword}", f"{keyword}岗", keyword)]
        monkeypatch.setattr("backend.app.unified_search_jobs", _fake)
        task = _run_task(client, store,
                         {"keywords": ["风控", "坏词"], "per_keyword": 5})
        assert task["status"] == "success", "单词失败不应倒任务"
        result = _json.loads(task["result_json"])
        assert result["analyzed_count"] == 1
        assert "坏词" in result.get("keyword_errors", {})

    def test_single_keyword_timeout_does_not_abort_others(
        self, app, store, monkeypatch
    ):
        client, _ = _authed(app, store)
        _passthrough_analyzer(monkeypatch)

        async def _fake(keyword, city, max_jobs, **kw):
            if keyword == "慢词":
                import asyncio
                raise asyncio.TimeoutError
            return [_job(f"ok-{keyword}", f"{keyword}岗", keyword)]

        monkeypatch.setattr("backend.app.unified_search_jobs", _fake)
        task = _run_task(
            client,
            store,
            {"keywords": ["慢词", "风控"], "per_keyword": 5},
        )
        assert task["status"] == "success"
        result = _json.loads(task["result_json"])
        assert result["keyword_errors"]["慢词"] == "爬取超时"
        assert result["analyzed_count"] == 1

    def test_all_keywords_fail_task_fails(self, app, store, monkeypatch):
        client, _ = _authed(app, store)
        _passthrough_analyzer(monkeypatch)

        async def _fake(keyword, city, max_jobs, **kw):
            raise RuntimeError("全挂")
        monkeypatch.setattr("backend.app.unified_search_jobs", _fake)
        task = _run_task(client, store,
                         {"keywords": ["风控", "计量"], "per_keyword": 5})
        assert task["status"] == "failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
