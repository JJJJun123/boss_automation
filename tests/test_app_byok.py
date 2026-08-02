#!/usr/bin/env python3
"""BYOK API 层集成测试 — /api/settings/api-key + 搜索配额门

覆盖：
- Key 设置/查询/删除路由（验证调用 mock）
- 掩码回显不泄露全文
- 未登录 401 / provider 非法 400 / 验证失败 400
- 搜索配额门：3 次内放行、超限 402、有 Key 不受限
- 任务失败不消耗试用次数；成功且走站方 Key 才 +1
- 用户 Key 一路传到 EnhancedJobAnalyzer
"""

import os
import sys
import time
import pytest
import unittest.mock as _mock

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
    s = StateStore(db_path=str(tmp_path / "byok_app.db"))
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


@pytest.fixture
def authed(app, store):
    """返回 (client, user_id)"""
    code = store.create_invite()
    user_id_holder = {}
    c = app.test_client()
    resp = c.get(f"/login?invite={code}", headers=ORIGIN)
    assert resp.status_code in (200, 302)
    with store._connect() as conn:
        row = conn.execute(
            "SELECT user_id FROM users WHERE invite_code = ?", (code,)
        ).fetchone()
    user_id_holder["uid"] = row["user_id"]
    return c, user_id_holder["uid"]


# ─── /api/settings/api-key CRUD ─────────────────────────


class TestApiKeyRoutes:
    def test_post_valid_key_returns_masked(self, authed):
        client, _uid = authed
        with _mock.patch("backend.app.validate_api_key", return_value=True):
            r = client.post("/api/settings/api-key",
                            json={"provider": "deepseek",
                                  "api_key": "sk-abcdef1234567890ab12"},
                            headers=ORIGIN)
        assert r.status_code == 200
        body = r.get_json()
        assert body["provider"] == "deepseek"
        assert "sk-abcdef1234567890ab12" not in str(body)
        assert body["masked"].endswith("ab12")

    def test_post_invalid_key_rejected_not_stored(self, authed, store):
        client, uid = authed
        with _mock.patch("backend.app.validate_api_key", return_value=False):
            r = client.post("/api/settings/api-key",
                            json={"provider": "deepseek", "api_key": "sk-bad"},
                            headers=ORIGIN)
        assert r.status_code == 400
        assert store.get_user_api_key(uid) is None

    def test_post_validation_timeout_is_retryable(self, authed, store):
        client, uid = authed
        with _mock.patch(
            "backend.app.validate_api_key", side_effect=TimeoutError
        ):
            r = client.post(
                "/api/settings/api-key",
                json={"provider": "deepseek", "api_key": "sk-maybe-valid"},
                headers=ORIGIN,
            )
        assert r.status_code == 503
        assert r.get_json()["code"] == "key_validation_timeout"
        assert "超时" in r.get_json()["error"]
        assert store.get_user_api_key(uid) is None

    def test_post_unknown_provider_400(self, authed):
        client, _uid = authed
        r = client.post("/api/settings/api-key",
                        json={"provider": "gemini", "api_key": "sk-x"},
                        headers=ORIGIN)
        assert r.status_code == 400

    def test_post_missing_fields_400(self, authed):
        client, _uid = authed
        r = client.post("/api/settings/api-key",
                        json={"provider": "deepseek"}, headers=ORIGIN)
        assert r.status_code == 400

    def test_key_stored_encrypted_not_plaintext(self, authed, store):
        """落库必须是密文——DB 里翻不到明文 key"""
        client, uid = authed
        plain = "sk-abcdef1234567890ab12"
        with _mock.patch("backend.app.validate_api_key", return_value=True):
            client.post("/api/settings/api-key",
                        json={"provider": "deepseek", "api_key": plain},
                        headers=ORIGIN)
        row = store.get_user_api_key(uid)
        assert row is not None
        assert plain not in row["key_encrypted"]
        # 端到端证明：库里的密文能解回原文（不是简单混淆）
        from backend.key_vault import decrypt_key
        assert decrypt_key(row["key_encrypted"]) == plain

    def test_get_before_set_404(self, authed):
        client, _uid = authed
        r = client.get("/api/settings/api-key")
        assert r.status_code == 404

    def test_get_returns_masked_only(self, authed):
        client, _uid = authed
        plain = "sk-abcdef1234567890ab12"
        with _mock.patch("backend.app.validate_api_key", return_value=True):
            client.post("/api/settings/api-key",
                        json={"provider": "deepseek", "api_key": plain},
                        headers=ORIGIN)
        r = client.get("/api/settings/api-key")
        assert r.status_code == 200
        body = r.get_json()
        assert plain not in str(body)
        assert body["masked"].endswith("ab12")
        assert body["provider"] == "deepseek"

    def test_delete_then_get_404(self, authed):
        client, _uid = authed
        with _mock.patch("backend.app.validate_api_key", return_value=True):
            client.post("/api/settings/api-key",
                        json={"provider": "deepseek", "api_key": "sk-abcdef12345678"},
                        headers=ORIGIN)
        r = client.delete("/api/settings/api-key", headers=ORIGIN)
        assert r.status_code == 200
        assert client.get("/api/settings/api-key").status_code == 404

    def test_unauthenticated_401(self, app):
        c = app.test_client()
        r = c.post("/api/settings/api-key",
                   json={"provider": "deepseek", "api_key": "sk-x"},
                   headers=ORIGIN)
        assert r.status_code == 401


class TestApiKeyProbeRoute:
    """未保存 Key 的连通性探测不能改动用户配置或泄露异常。"""

    def test_valid_pending_key_is_tested_without_storing(self, authed, store):
        client, uid = authed
        pending_key = "sk-pending-abcdef123456"
        with _mock.patch("backend.app.validate_api_key", return_value=True):
            response = client.post(
                "/api/user-key/test",
                json={"provider": "deepseek", "api_key": pending_key},
                headers=ORIGIN,
            )
        assert response.status_code == 200
        assert response.get_json() == {
            "success": True,
            "provider": "deepseek",
        }
        assert pending_key not in response.get_data(as_text=True)
        assert store.get_user_api_key(uid) is None

    def test_invalid_pending_key_returns_clear_safe_error(self, authed):
        client, _uid = authed
        pending_key = "sk-invalid-secret"
        with _mock.patch("backend.app.validate_api_key", return_value=False):
            response = client.post(
                "/api/user-key/test",
                json={"provider": "deepseek", "api_key": pending_key},
                headers=ORIGIN,
            )
        assert response.status_code == 400
        assert response.get_json()["code"] == "key_invalid"
        assert pending_key not in response.get_data(as_text=True)

    def test_pending_key_timeout_is_retryable(self, authed):
        client, _uid = authed
        with _mock.patch(
            "backend.app.validate_api_key", side_effect=TimeoutError
        ):
            response = client.post(
                "/api/user-key/test",
                json={"provider": "claude", "api_key": "sk-timeout"},
                headers=ORIGIN,
            )
        assert response.status_code == 503
        assert response.get_json()["code"] == "key_validation_timeout"

    def test_provider_exception_is_not_exposed(self, authed):
        client, _uid = authed
        with _mock.patch(
            "backend.app.validate_api_key",
            side_effect=RuntimeError("provider exploded with secret context"),
        ):
            response = client.post(
                "/api/user-key/test",
                json={"provider": "gpt", "api_key": "sk-private"},
                headers=ORIGIN,
            )
        assert response.status_code == 502
        assert response.get_json()["code"] == "key_test_unavailable"
        assert "provider exploded" not in response.get_data(as_text=True)

    def test_probe_requires_authentication(self, app):
        response = app.test_client().post(
            "/api/user-key/test",
            json={"provider": "deepseek", "api_key": "sk-private"},
            headers=ORIGIN,
        )
        assert response.status_code == 401


# ─── 搜索配额门 ──────────────────────────────────────────


class TestTrialQuotaGate:
    def _exhaust_trial(self, store, uid, n=3):
        for _ in range(n):
            store.increment_trial_usage(uid)

    def test_search_allowed_under_quota_without_key(self, authed):
        client, _uid = authed
        with _mock.patch("backend.app._run_job_search_task"):
            r = client.post("/api/jobs/search", json={"keyword": "AI"},
                            headers=ORIGIN)
        assert r.status_code == 202

    def test_search_402_when_quota_exhausted_without_key(self, authed, store):
        client, uid = authed
        self._exhaust_trial(store, uid)
        with _mock.patch("backend.app._run_job_search_task"):
            r = client.post("/api/jobs/search", json={"keyword": "AI"},
                            headers=ORIGIN)
        assert r.status_code == 402
        assert r.get_json().get("code") == "byok_required"

    def test_search_allowed_with_key_even_quota_exhausted(self, authed, store):
        client, uid = authed
        self._exhaust_trial(store, uid)
        from backend.key_vault import encrypt_key
        store.set_user_api_key(uid, "deepseek", encrypt_key("sk-user-key"))
        with _mock.patch("backend.app._run_job_search_task"):
            r = client.post("/api/jobs/search", json={"keyword": "AI"},
                            headers=ORIGIN)
        assert r.status_code == 202


class TestUserKeyErrorClassification:
    def test_boss_antibot_403_is_not_key_error(self):
        from backend.app import _is_user_key_auth_error
        assert _is_user_key_auth_error(
            RuntimeError("Boss security.html 403 anti-bot challenge")
        ) is False

    def test_ai_provider_403_is_key_error(self):
        from backend.app import _is_user_key_auth_error
        assert _is_user_key_auth_error(
            RuntimeError("DeepSeek API调用失败: 403 - forbidden")
        ) is True


# ─── 试用计数与 Key 透传（后台任务级） ────────────────────


def _fake_analyzer_factory(captured):
    """返回假 EnhancedJobAnalyzer 类，记录构造参数并回固定结果"""

    class _FakeAnalyzer:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def analyze_jobs(self, jobs, resume_text="", keyword=""):
            return [{"title": "岗位A", "score": 8}]

    return _FakeAnalyzer


def _wait(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


class TestTrialAccountingAndKeyThreading:
    def _run_search_to_completion(self, app, store, monkeypatch, uid, client):
        captured = {}

        async def _fake_search(keyword, city, max_jobs, **kwargs):
            return [{"title": "岗位A", "company": "X", "url": "http://j/1"}]

        monkeypatch.setattr("backend.app.unified_search_jobs", _fake_search)
        monkeypatch.setattr("backend.app.EnhancedJobAnalyzer",
                            _fake_analyzer_factory(captured))
        store.set_resume(uid, "本人简历全文", filename="r.pdf")

        r = client.post("/api/jobs/search", json={"keyword": "AI"},
                        headers=ORIGIN)
        assert r.status_code == 202
        task_id = r.get_json()["task_id"]
        ok = _wait(lambda: store._get_task_unscoped(task_id)["status"]
                   not in ("pending", "running"))
        assert ok, "任务未在超时内完成"
        return task_id, captured

    def test_station_key_success_increments_trial(self, app, store, monkeypatch, authed):
        client, uid = authed
        task_id, _cap = self._run_search_to_completion(
            app, store, monkeypatch, uid, client)
        assert store._get_task_unscoped(task_id)["status"] == "success"
        assert store.get_trial_usage(uid) == 1

    def test_user_key_success_does_not_increment(self, app, store, monkeypatch, authed):
        client, uid = authed
        from backend.key_vault import encrypt_key
        store.set_user_api_key(uid, "deepseek", encrypt_key("sk-user-key"))
        task_id, captured = self._run_search_to_completion(
            app, store, monkeypatch, uid, client)
        assert store._get_task_unscoped(task_id)["status"] == "success"
        assert store.get_trial_usage(uid) == 0
        # Key 必须透传到 analyzer
        assert captured.get("api_key") == "sk-user-key"

    def test_failed_task_does_not_increment(self, app, store, monkeypatch, authed):
        """爬虫返回空 → 任务失败 → 不扣试用次数"""
        client, uid = authed

        async def _empty_search(keyword, city, max_jobs, **kwargs):
            return []

        monkeypatch.setattr("backend.app.unified_search_jobs", _empty_search)
        store.set_resume(uid, "本人简历全文", filename="r.pdf")
        r = client.post("/api/jobs/search", json={"keyword": "AI"},
                        headers=ORIGIN)
        assert r.status_code == 202
        task_id = r.get_json()["task_id"]
        ok = _wait(lambda: store._get_task_unscoped(task_id)["status"]
                   not in ("pending", "running"))
        assert ok
        assert store._get_task_unscoped(task_id)["status"] != "success"
        assert store.get_trial_usage(uid) == 0

    def test_user_key_auth_failure_marks_task_with_code(
            self, app, store, monkeypatch, authed):
        """用户 Key 失效（AI 调用抛认证错）→ 任务 failed + user_key_invalid 标记，
        不扣试用次数"""
        import json as _json
        client, uid = authed
        from backend.key_vault import encrypt_key
        store.set_user_api_key(uid, "deepseek", encrypt_key("sk-revoked"))

        async def _fake_search(keyword, city, max_jobs, **kwargs):
            return [{"title": "岗位A", "company": "X", "url": "http://j/1"}]

        class _AuthFailAnalyzer:
            def __init__(self, **kwargs):
                pass

            def analyze_jobs(self, jobs, resume_text="", keyword=""):
                raise PermissionError("401 authentication_error: invalid api key")

        monkeypatch.setattr("backend.app.unified_search_jobs", _fake_search)
        monkeypatch.setattr("backend.app.EnhancedJobAnalyzer", _AuthFailAnalyzer)
        store.set_resume(uid, "本人简历全文", filename="r.pdf")

        r = client.post("/api/jobs/search", json={"keyword": "AI"},
                        headers=ORIGIN)
        assert r.status_code == 202
        task_id = r.get_json()["task_id"]
        ok = _wait(lambda: store._get_task_unscoped(task_id)["status"]
                   not in ("pending", "running"))
        assert ok
        task = store._get_task_unscoped(task_id)
        assert task["status"] == "failed"
        result = _json.loads(task["result_json"] or "{}")
        assert result.get("code") == "user_key_invalid"
        assert store.get_trial_usage(uid) == 0

    def test_undecryptable_key_treated_as_no_key(
            self, app, store, monkeypatch, authed):
        """APP_ENCRYPTION_KEY 轮换后旧密文解不开 → 视为无 Key 走配额门（402），
        不能 500"""
        client, uid = authed
        # 直接塞一段解不开的假密文
        store.set_user_api_key(uid, "deepseek", "gAAAAA-not-decryptable-blob")
        for _ in range(3):
            store.increment_trial_usage(uid)
        with _mock.patch("backend.app._run_job_search_task"):
            r = client.post("/api/jobs/search", json={"keyword": "AI"},
                            headers=ORIGIN)
        assert r.status_code == 402
        assert r.get_json().get("code") == "byok_required"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
