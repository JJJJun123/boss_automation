#!/usr/bin/env python3
"""阶段 S-B：gunicorn 生产入口工厂

契约：backend.app.create_app_for_gunicorn(store=None)
- 返回 Flask WSGI app（gunicorn 直接 serve；绝不调用 socketio.run 阻塞）
- SocketIO 以 threading 模式挂载在 app 上（长轮询经标准 WSGI 走通）
- 复用 create_app 的全部初始化（含孤儿任务清理）
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def store(tmp_path):
    from utils.state_store import StateStore
    s = StateStore(db_path=str(tmp_path / "gunicorn.db"))
    s.init_schema()
    return s


@pytest.fixture
def _env(monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-12345678-aaaaaaaa")
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    import importlib
    import backend.key_vault as kv
    importlib.reload(kv)


class TestGunicornFactory:
    def test_factory_exists_and_returns_flask_app(self, _env, store):
        from flask import Flask
        from backend.app import create_app_for_gunicorn
        app = create_app_for_gunicorn(store=store)
        assert isinstance(app, Flask), "gunicorn 入口必须返回 Flask WSGI app"

    def test_factory_returns_without_blocking(self, _env, store):
        """能返回即证明没调 socketio.run（那会阻塞测试永不返回）"""
        from backend.app import create_app_for_gunicorn
        app = create_app_for_gunicorn(store=store)
        assert app is not None

    def test_socketio_attached_threading_mode(self, _env, store):
        from backend.app import create_app_for_gunicorn
        app = create_app_for_gunicorn(store=store)
        sio = app.extensions.get("socketio")
        assert sio is not None, "SocketIO 未挂载，长轮询通道会死"
        assert sio.async_mode == "threading", \
            f"必须 threading 模式（不能 eventlet），实际 {sio.async_mode}"

    def test_index_served(self, _env, store):
        from backend.app import create_app_for_gunicorn
        app = create_app_for_gunicorn(store=store)
        app.config["TESTING"] = True
        response = app.test_client().get("/")
        assert response.status_code == 200, "deploy 健康检查依赖 / 返回 200"

    def test_orphan_cleanup_runs(self, _env, store):
        """服务重启后 running 残留必须被清理（历史 bug 回归护栏）"""
        from backend.app import create_app_for_gunicorn
        code = store.create_invite()
        uid, _ = store.consume_invite(code)
        task_id = store.create_task(uid, keyword="风控", city="shanghai")
        store.set_task_status(task_id, "running")
        create_app_for_gunicorn(store=store)
        task = store.get_task(task_id, uid)
        assert task["status"] not in ("running", "pending"), \
            "工厂初始化未清理孤儿任务，重启后会永久 409"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
