#!/usr/bin/env python3
"""阶段 Q：QR 透传 — 后端桥接层测试（spec Q2/Q4/Q6）

被测契约：
- backend.app._make_qr_callback(socketio, user_id, task_id, deadline_anchor)
  返回可调用；调用时 emit("qr_update", {...event, task_id}, to=user_id)
- logged_in 事件 → deadline_anchor["started"] 重置为当前时刻（Q4 重计时）
- 任务链路：unified_search_jobs 收到 qr_callback kwarg
- login_timeout → 任务 failed + result_json.code == "login_timeout"，不扣试用
- image_b64 在 task_logger 中脱敏（Q6）
"""

import json as _json
import os
import sys
import time
import unittest.mock as _mock
from datetime import datetime, timedelta

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
    s = StateStore(db_path=str(tmp_path / "qr_app.db"))
    s.init_schema()
    return s


@pytest.fixture
def app(store, monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-12345678-aaaaaaaa")
    monkeypatch.setenv("FLASK_ENV", "development")
    from backend.app import create_app
    application = create_app(store=store)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def authed(app, store):
    code = store.create_invite()
    c = app.test_client()
    resp = c.get(f"/login?invite={code}", headers=ORIGIN)
    assert resp.status_code in (200, 302)
    with store._connect() as conn:
        row = conn.execute(
            "SELECT user_id FROM users WHERE invite_code = ?", (code,)
        ).fetchone()
    return c, row["user_id"]


def _wait(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


# ─── _make_qr_callback 单元 ──────────────────────────────


class TestMakeQrCallback:
    def _build(self):
        from backend.app import _make_qr_callback
        emits = []

        class _FakeSio:
            def emit(self, event, payload, to=None, **kwargs):
                emits.append({"event": event, "payload": payload, "to": to})

        anchor = {"started": datetime.now() - timedelta(seconds=100)}
        cb = _make_qr_callback(_FakeSio(), "user-1", "task-9", anchor)
        return cb, emits, anchor

    def test_emits_qr_update_to_user_room(self):
        cb, emits, _anchor = self._build()
        cb({"state": "qr_ready", "image_b64": "aW1n", "message": "扫码"})
        assert len(emits) == 1
        e = emits[0]
        assert e["event"] == "qr_update"
        assert e["to"] == "user-1", "必须只推本人房间"
        assert e["payload"]["task_id"] == "task-9"
        assert e["payload"]["state"] == "qr_ready"
        assert e["payload"]["image_b64"] == "aW1n"

    def test_logged_in_resets_deadline_anchor(self):
        """Q4：登录成功 → deadline 重计时（扫码耗时不吞爬取/分析预算）"""
        cb, _emits, anchor = self._build()
        old = anchor["started"]
        cb({"state": "logged_in", "image_b64": None, "message": "ok"})
        assert anchor["started"] > old, "logged_in 后 started 未重置"
        assert (datetime.now() - anchor["started"]).total_seconds() < 5

    def test_non_terminal_states_do_not_reset_anchor(self):
        cb, _emits, anchor = self._build()
        old = anchor["started"]
        cb({"state": "qr_ready", "image_b64": "aW1n", "message": "m"})
        cb({"state": "scanned", "image_b64": None, "message": "m"})
        assert anchor["started"] == old

    def test_emit_exception_swallowed(self):
        """emit 抛异常不能炸掉爬虫轮询循环"""
        from backend.app import _make_qr_callback

        class _BrokenSio:
            def emit(self, *a, **k):
                raise RuntimeError("socket down")

        cb = _make_qr_callback(_BrokenSio(), "u", "t",
                               {"started": datetime.now()})
        cb({"state": "qr_ready", "image_b64": "x", "message": "m"})  # 不抛即过


# ─── 任务链路透传 ────────────────────────────────────────


class TestTaskChainThreading:
    def test_qr_callback_passed_to_crawler(self, app, store, authed, monkeypatch):
        """unified_search_jobs 必须收到可调用的 qr_callback kwarg"""
        client, _uid = authed
        captured = {}

        async def _fake_search(keyword, city, max_jobs, **kwargs):
            captured["qr_callback"] = kwargs.get("qr_callback")
            return []

        monkeypatch.setattr("backend.app.unified_search_jobs", _fake_search)
        r = client.post("/api/jobs/search", json={"keyword": "AI"},
                        headers=ORIGIN)
        assert r.status_code == 202
        assert _wait(lambda: "qr_callback" in captured)
        assert callable(captured["qr_callback"]), "qr_callback 未透传或不可调用"

    def test_login_timeout_marks_task_failed_with_code(
            self, app, store, authed, monkeypatch):
        """爬虫登录超时（RuntimeError 会话过期语义）→ failed + login_timeout 标记"""
        client, uid = authed

        async def _timeout_search(keyword, city, max_jobs, **kwargs):
            cb = kwargs.get("qr_callback")
            if cb:
                cb({"state": "login_timeout", "image_b64": None,
                    "message": "扫码超时"})
            raise RuntimeError("登录超时：用户未在时限内扫码")

        monkeypatch.setattr("backend.app.unified_search_jobs", _timeout_search)
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
        assert result.get("code") == "login_timeout"
        # 登录都没成，不能扣试用次数
        assert store.get_trial_usage(uid) == 0


# ─── 日志脱敏 ────────────────────────────────────────────


class TestQrLogMasking:
    def test_image_b64_masked_in_task_logger(self):
        from backend.task_logger import mask_sensitive
        masked = mask_sensitive(
            {"state": "qr_ready", "image_b64": "iVBORw0KGgo...", "task_id": "t1"})
        assert masked["image_b64"] != "iVBORw0KGgo..."
        assert masked["state"] == "qr_ready"
        assert masked["task_id"] == "t1"

    def test_nested_image_b64_masked(self):
        from backend.task_logger import mask_sensitive
        masked = mask_sensitive({"event": {"image_b64": "AAAA"}})
        assert masked["event"]["image_b64"] != "AAAA"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
