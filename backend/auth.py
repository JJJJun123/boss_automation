#!/usr/bin/env python3
"""
邀请码登录 + user_id 中间件

对应 IMPLEMENTATION_PLAN.md 阶段 0.2 + TD-1。

流程：
    URL `?invite=<code>` → state_store.consume_invite() → 派生 user_id
                                                       ↓
                                       Set-Cookie: user_id=<...>
                                                       ↓
    后续请求 Cookie → extract_user_id() → request.user_id
                                                       ↓
                              @require_user_id 装饰器校验通过

Cookie 安全标志（Secure / HttpOnly / SameSite）默认开启。本期单 worker
跑在 HTTPS 反代后；后续阶段 0.4 会做更细的安全基线。
"""

from functools import wraps
from typing import Optional

from flask import current_app, jsonify, request


COOKIE_NAME = "boss_user_id"
COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 天


def extract_user_id(req, store) -> Optional[str]:
    """从请求 cookie 提取 user_id 并校验该用户在 store 中存在

    参数：
        req   - Flask request 对象
        store - StateStore 实例
    返回：
        str  - 合法 user_id
        None - 无 cookie 或 cookie 中 user_id 在库中查不到（伪造/过期）
    """
    user_id = req.cookies.get(COOKIE_NAME)
    if not user_id:
        return None
    if store.get_user(user_id) is None:
        return None
    return user_id


def require_user_id(view_func):
    """路由装饰器：未登录返回 401，登录则把 user_id 挂到 request 上

    使用示例：
        @app.route('/protected')
        @require_user_id
        def protected():
            return jsonify(user_id=request.user_id)
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        store = current_app.config.get("STORE")
        if store is None:
            return jsonify({"error": "state store not initialized"}), 500

        user_id = extract_user_id(request, store)
        if not user_id:
            return jsonify({"error": "unauthorized", "hint": "invite required"}), 401

        # 挂载到 request 供视图使用
        request.user_id = user_id
        return view_func(*args, **kwargs)

    return wrapper


def set_user_cookie(response, user_id: str) -> None:
    """把 user_id 写入响应的 Set-Cookie

    安全标志：
        - HttpOnly：JS 拿不到 cookie，防 XSS 偷
        - Secure：仅 HTTPS 传输（生产环境必须 True；本地开发可临时关）
        - SameSite=Lax：跨站请求不带，防 CSRF；表单 GET/POST 同源仍带
    """
    # secure 在生产 HTTPS 部署下必须 True；本地 HTTP 测试时 Flask test_client
    # 仍会写入，浏览器不传——这是开发期可接受的。生产由 nginx HTTPS 保证。
    response.set_cookie(
        COOKIE_NAME,
        user_id,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="Lax",
    )
