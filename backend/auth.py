#!/usr/bin/env python3
"""
邀请码登录 + session token 中间件

对应 IMPLEMENTATION_PLAN.md 阶段 0.2 + TD-1（按 Codex P1 反馈修订）。

流程：
    URL `?invite=<code>` → state_store.consume_invite() → (user_id, session_token)
                                                       ↓
                                  Set-Cookie: boss_session=<token>
                                                       ↓
    后续请求 Cookie token → store.get_user_by_session_token() → request.user_id
                                                       ↓
                              @require_user_id 装饰器校验通过

安全模型：
- Cookie 存的是 **session_token**（独立随机 32 字节 base64），不是 user_id 派生
- 数据库只存 token 的 SHA256 hash；明文 token 仅在签发瞬间返回一次
- 即便邀请码泄露，攻击者拿不到 cookie token = 无法伪造登录
- session 30 天过期；revoke_session_token 支持登出立即失效
"""

from functools import wraps
from typing import Optional

from flask import current_app, jsonify, request


COOKIE_NAME = "boss_session"
COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 天


def extract_user_id(req, store) -> Optional[str]:
    """从请求 cookie 中读 session token，反查 user_id

    参数：
        req   - Flask request 对象
        store - StateStore 实例
    返回：
        str  - 合法 user_id
        None - 无 cookie / token 不存在 / token 已过期
    """
    token = req.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return store.get_user_by_session_token(token)


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


def set_session_cookie(response, session_token: str) -> None:
    """把 session token 写入响应的 Set-Cookie

    安全标志：
        - HttpOnly：JS 拿不到 cookie，防 XSS 偷
        - Secure：仅 HTTPS 传输（生产环境必须 True；本地开发可临时关）
        - SameSite=Lax：跨站请求不带，防 CSRF；表单 GET/POST 同源仍带
    """
    response.set_cookie(
        COOKIE_NAME,
        session_token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="Lax",
    )


# 向后兼容旧名（避免下游导入立刻断；后续阶段集成完毕可删）
set_user_cookie = set_session_cookie
