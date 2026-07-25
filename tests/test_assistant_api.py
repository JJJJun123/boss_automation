#!/usr/bin/env python3
"""结果页 AI 助手（spec 阶段 C，纯问答）"""

import json as _json
import os
import sys
import time
from unittest.mock import MagicMock

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
    s = StateStore(db_path=str(tmp_path / "assistant.db"))
    s.init_schema()
    return s


@pytest.fixture
def app(store, monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-12345678-aaaaaaaa")
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    import importlib
    import backend.key_vault as kv
    importlib.reload(kv)
    from backend.app import create_app
    application = create_app(store=store)
    application.config["TESTING"] = True
    return application


def _authed(app, store, with_key=True):
    from backend.key_vault import encrypt_key
    from utils.state_store import resume_fingerprint
    code = store.create_invite()
    uid, token = store.consume_invite(code)
    store.set_resume(uid, "四年市场风险经验", filename="r.pdf")
    if with_key:
        store.set_user_api_key(uid, "deepseek", encrypt_key("sk-user-key"))
    profile = {"target_directions": ["市场风险管理"], "transition": None,
               "cities": ["shanghai"], "salary_floor": None,
               "hard_avoids": [], "seniority": None, "notes": ""}
    store.set_career_profile(uid, _json.dumps(profile, ensure_ascii=False),
                             resume_fingerprint("四年市场风险经验"))
    client = app.test_client()
    client.set_cookie("boss_session", token, domain="localhost")
    return client, uid


def _success_task(store, uid):
    task_id = store.create_task(uid, keyword="风控", city="shanghai")
    store.set_task_status(task_id, "running")
    payload = {"qualified_jobs": [], "analyzed_jobs": [
        {"title": "风险策略专家", "company": "金棠美家", "score": 8,
         "salary": "25-35K·13薪", "job_description": "负责风险策略"},
        {"title": "风险经理", "company": "X公司", "score": 5,
         "salary": "20-30K", "job_description": "负责风控"},
    ], "total": 2, "analyzed_count": 2, "qualified_count": 0}
    assert store.set_task_result(task_id, "success",
                                 _json.dumps(payload, ensure_ascii=False))
    return task_id


def _mock_ai(monkeypatch, answer="第一个岗位更适合你", raise_exc=None):
    fake = MagicMock()
    if raise_exc:
        fake.call_api_simple.side_effect = raise_exc
    else:
        fake.call_api_simple.return_value = answer
    factory = MagicMock(create_pure_client=MagicMock(return_value=fake))
    monkeypatch.setattr("backend.app.AIClientFactory", factory)
    return fake


class TestAssistantAuth:
    def test_unauthenticated_401(self, app):
        c = app.test_client()
        r = c.post("/api/assistant", json={"question": "q", "task_id": "t"},
                   headers=ORIGIN)
        assert r.status_code == 401

    def test_no_key_402(self, app, store, monkeypatch):
        client, uid = _authed(app, store, with_key=False)
        task_id = _success_task(store, uid)
        _mock_ai(monkeypatch)
        r = client.post("/api/assistant",
                        json={"question": "对比一下", "task_id": task_id},
                        headers=ORIGIN)
        assert r.status_code == 402
        assert r.get_json().get("code") == "byok_required"

    def test_other_users_task_404(self, app, store, monkeypatch):
        client_a, uid_a = _authed(app, store)
        _, uid_b = _authed(app, store)
        task_b = _success_task(store, uid_b)
        _mock_ai(monkeypatch)
        r = client_a.post("/api/assistant",
                          json={"question": "对比", "task_id": task_b},
                          headers=ORIGIN)
        assert r.status_code == 404, "IDOR：不能读他人任务"


class TestAssistantValidation:
    def test_question_too_long_400(self, app, store, monkeypatch):
        client, uid = _authed(app, store)
        task_id = _success_task(store, uid)
        _mock_ai(monkeypatch)
        r = client.post("/api/assistant",
                        json={"question": "问" * 501, "task_id": task_id},
                        headers=ORIGIN)
        assert r.status_code == 400

    def test_non_success_task_409(self, app, store, monkeypatch):
        client, uid = _authed(app, store)
        task_id = store.create_task(uid, keyword="风控", city="shanghai")
        _mock_ai(monkeypatch)
        r = client.post("/api/assistant",
                        json={"question": "对比", "task_id": task_id},
                        headers=ORIGIN)
        assert r.status_code == 409


class TestAssistantAnswer:
    def test_answer_with_context(self, app, store, monkeypatch):
        client, uid = _authed(app, store)
        task_id = _success_task(store, uid)
        fake = _mock_ai(monkeypatch, answer="推荐第一个：风险策略专家")
        r = client.post("/api/assistant",
                        json={"question": "哪个岗位更适合我？", "task_id": task_id},
                        headers=ORIGIN)
        assert r.status_code == 200
        assert r.get_json()["answer"] == "推荐第一个：风险策略专家"
        prompt = fake.call_api_simple.call_args.args[0]
        assert "风险策略专家" in prompt, "上下文应含岗位数据"
        assert "市场风险管理" in prompt, "上下文应含画像"
        assert "哪个岗位更适合我" in prompt

    def test_ai_failure_502_no_leak(self, app, store, monkeypatch):
        client, uid = _authed(app, store)
        task_id = _success_task(store, uid)
        _mock_ai(monkeypatch, raise_exc=Exception("secret internal detail"))
        r = client.post("/api/assistant",
                        json={"question": "对比", "task_id": task_id},
                        headers=ORIGIN)
        assert r.status_code == 502
        assert "secret internal detail" not in str(r.get_json())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
