#!/usr/bin/env python3
"""任务链路的缓存流转（spec 阶段 P3 任务链路 + 详情跳过接口）

- 首搜：岗位入 jobs 表、分析入 job_analyses
- 再搜同岗位：命中缓存的岗位不送 analyzer；结果含缓存岗位；cache_hits 正确
- 换简历：指纹变 → 缓存失效重新分析
- 爬虫收到 detail_cache_lookup 可调用（详情页跳过的查询通道）
"""

import json as _json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ORIGIN = {"Origin": "http://localhost:3001"}

JOB_URL = "https://www.zhipin.com/job_detail/cacheJob001.html"
CRAWLED_JOB = {"title": "风险经理", "company": "X公司", "salary": "20-35K",
               "url": JOB_URL, "job_description": "风险计量"}


@pytest.fixture(autouse=True)
def _reset_invite_limiter():
    from backend.rate_limiter import invite_limiter
    invite_limiter._failures.clear()
    invite_limiter._blacklist.clear()
    yield


@pytest.fixture
def store(tmp_path):
    from utils.state_store import StateStore
    s = StateStore(db_path=str(tmp_path / "cacheflow.db"))
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


def _wait(predicate, timeout=6.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _authed(app, store, resume_text="四年市场风险经验"):
    code = store.create_invite()
    uid, token = store.consume_invite(code)
    store.set_resume(uid, resume_text, filename="r.pdf")
    client = app.test_client()
    client.set_cookie("boss_session", token, domain="localhost")
    return client, uid


def _fake_search_returning(jobs, captured=None):
    async def _fake(keyword, city, max_jobs, **kwargs):
        if captured is not None:
            captured.update(kwargs)
        return [dict(j) for j in jobs]
    return _fake


def _fake_analyzer_cls(received_jobs_sink):
    class _FakeAnalyzer:
        def __init__(self, **kwargs):
            self.discarded_jobs = []

        def analyze_jobs(self, jobs, resume_text="", keyword="", **kw):
            received_jobs_sink.extend(jobs)
            out = []
            for j in jobs:
                jj = dict(j)
                jj.update({"score": 7, "final_decision": "apply",
                           "hard_stops": [], "soft_gaps": [],
                           "discard_reasons": [], "advertised_comp": j.get("salary", "")})
                out.append(jj)
            return out
    return _FakeAnalyzer


def _run_search(client, store, monkeypatch, jobs, received_sink, captured=None):
    monkeypatch.setattr("backend.app.unified_search_jobs",
                        _fake_search_returning(jobs, captured))
    monkeypatch.setattr("backend.app.EnhancedJobAnalyzer",
                        _fake_analyzer_cls(received_sink))
    r = client.post("/api/jobs/search", json={"keyword": "风险"}, headers=ORIGIN)
    assert r.status_code == 202
    task_id = r.get_json()["task_id"]
    ok = _wait(lambda: store._get_task_unscoped(task_id)["status"]
               not in ("pending", "running"))
    assert ok, "任务未完成"
    task = store._get_task_unscoped(task_id)
    assert task["status"] == "success", task["result_json"]
    return _json.loads(task["result_json"])


class TestCacheFlow:
    def test_first_search_persists_job_and_analysis(self, app, store, monkeypatch):
        client, uid = _authed(app, store)
        received = []
        _run_search(client, store, monkeypatch, [CRAWLED_JOB], received)

        # jobs 表有记录
        row = store.get_fresh_job("cacheJob001", max_age_seconds=3600)
        assert row is not None
        assert row["title"] == "风险经理"
        # 分析缓存有记录
        from utils.state_store import resume_fingerprint
        fp = resume_fingerprint("四年市场风险经验")
        cached = store.get_cached_analysis(uid, "cacheJob001", fp)
        assert cached is not None
        assert cached.get("score") == 7

    def test_second_search_uses_cache(self, app, store, monkeypatch):
        client, uid = _authed(app, store)
        received_first = []
        _run_search(client, store, monkeypatch, [CRAWLED_JOB], received_first)
        assert len(received_first) == 1, "首搜应送 analyzer"

        received_second = []
        result = _run_search(client, store, monkeypatch, [CRAWLED_JOB], received_second)
        assert received_second == [], "缓存命中的岗位不应再送 analyzer"
        titles = [j.get("title") for j in result["analyzed_jobs"]]
        assert "风险经理" in titles, "缓存岗位应出现在结果中"
        assert result.get("cache_hits") == 1

    def test_resume_change_invalidates_cache(self, app, store, monkeypatch):
        client, uid = _authed(app, store)
        received_first = []
        _run_search(client, store, monkeypatch, [CRAWLED_JOB], received_first)

        # 换简历
        store.set_resume(uid, "两年信用风险经验（全新简历）", filename="r2.pdf")
        received_second = []
        _run_search(client, store, monkeypatch, [CRAWLED_JOB], received_second)
        assert len(received_second) == 1, "换简历后缓存必须失效、重新分析"

    def test_crawler_receives_detail_cache_lookup(self, app, store, monkeypatch):
        client, uid = _authed(app, store)
        captured = {}
        received = []
        _run_search(client, store, monkeypatch, [CRAWLED_JOB], received,
                    captured=captured)
        lookup = captured.get("detail_cache_lookup")
        assert callable(lookup), "unified_search_jobs 未收到 detail_cache_lookup"
        # 已入库岗位可查到；未知岗位 None
        assert lookup("cacheJob001") is not None
        assert lookup("nonexistent") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
