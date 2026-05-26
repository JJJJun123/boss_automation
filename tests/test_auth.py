#!/usr/bin/env python3
"""
邀请码登录 + user_id 中间件测试

按 IMPLEMENTATION_PLAN.md 阶段 0.2：
- URL `?invite=<code>` → state_store.consume_invite → 派生 user_id → 写 cookie
- 后续请求 cookie 携带 user_id → request 上挂载 user_id
- require_user_id 装饰器：未登录返回 401

不测试 Cookie 安全标志（Secure/HttpOnly/SameSite）—— 那是阶段 0.4。
"""

import os
import sys

import pytest
from flask import Flask, jsonify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.auth import extract_user_id, require_user_id, set_user_cookie, COOKIE_NAME
from utils.state_store import StateStore


@pytest.fixture
def store(tmp_path):
    s = StateStore(db_path=str(tmp_path / "auth_test.db"))
    s.init_schema()
    return s


@pytest.fixture
def app_with_store(store):
    """构造一个最小 Flask app，注入 store 到 app.config['STORE']"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["STORE"] = store
    app.secret_key = "test"

    @app.route("/protected")
    @require_user_id
    def protected():
        from flask import request
        return jsonify({"user_id": request.user_id})

    @app.route("/login")
    def login():
        from flask import request, make_response
        # 模拟入口：?invite=xxx → 消费 + 设 cookie
        invite = request.args.get("invite")
        store = app.config["STORE"]
        if not invite:
            return jsonify({"error": "no invite"}), 400
        user_id = store.consume_invite(invite)
        if not user_id:
            return jsonify({"error": "invalid"}), 401
        resp = make_response(jsonify({"user_id": user_id}))
        set_user_cookie(resp, user_id)
        return resp

    return app


# ─── extract_user_id ───────────────────────────────────────

def test_extract_returns_none_without_cookie(app_with_store):
    """无 cookie 无 invite → None"""
    with app_with_store.test_request_context("/protected"):
        from flask import request
        assert extract_user_id(request, app_with_store.config["STORE"]) is None


def test_extract_reads_cookie(app_with_store, store):
    """cookie 里有合法 user_id → 提取并校验存在"""
    code = store.create_invite()
    user_id = store.consume_invite(code)
    with app_with_store.test_request_context("/protected", headers={
        "Cookie": f"{COOKIE_NAME}={user_id}"
    }):
        from flask import request
        assert extract_user_id(request, app_with_store.config["STORE"]) == user_id


def test_extract_rejects_unknown_cookie_user(app_with_store, store):
    """cookie 里 user_id 库里查不到 → 拒绝"""
    with app_with_store.test_request_context("/protected", headers={
        "Cookie": f"{COOKIE_NAME}=fakeUserId00000"
    }):
        from flask import request
        assert extract_user_id(request, app_with_store.config["STORE"]) is None


# ─── require_user_id 装饰器 ────────────────────────────────

def test_protected_route_401_without_credentials(app_with_store):
    client = app_with_store.test_client()
    resp = client.get("/protected")
    assert resp.status_code == 401


def test_protected_route_200_with_valid_cookie(app_with_store, store):
    code = store.create_invite()
    user_id = store.consume_invite(code)
    client = app_with_store.test_client()
    client.set_cookie(COOKIE_NAME, user_id, domain="localhost")
    resp = client.get("/protected")
    assert resp.status_code == 200
    assert resp.get_json()["user_id"] == user_id


# ─── 邀请码登录端到端流程 ──────────────────────────────────

def test_invite_login_sets_cookie(app_with_store, store):
    code = store.create_invite()
    client = app_with_store.test_client()
    resp = client.get(f"/login?invite={code}")
    assert resp.status_code == 200

    # response 应该 Set-Cookie
    set_cookie_header = resp.headers.get("Set-Cookie", "")
    assert COOKIE_NAME in set_cookie_header, "登录成功必须 Set-Cookie"


def test_invite_login_persists_user(app_with_store, store):
    """登录后用 cookie 访问受保护路由应通过"""
    code = store.create_invite()
    client = app_with_store.test_client()
    login_resp = client.get(f"/login?invite={code}")
    user_id = login_resp.get_json()["user_id"]

    # 用同一个 client 后续请求自动带 cookie
    resp = client.get("/protected")
    assert resp.status_code == 200
    assert resp.get_json()["user_id"] == user_id


def test_invite_login_invalid_code_returns_401(app_with_store):
    client = app_with_store.test_client()
    resp = client.get("/login?invite=badcode1")
    assert resp.status_code == 401


def test_invite_login_used_code_returns_401(app_with_store, store):
    """已用过的邀请码不能再用"""
    code = store.create_invite()
    client = app_with_store.test_client()
    client.get(f"/login?invite={code}")  # 第一次用掉
    resp = client.get(f"/login?invite={code}")  # 第二次
    assert resp.status_code == 401


def test_invite_login_missing_invite_returns_400(app_with_store):
    client = app_with_store.test_client()
    resp = client.get("/login")
    assert resp.status_code == 400
