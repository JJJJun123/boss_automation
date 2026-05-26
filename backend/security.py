#!/usr/bin/env python3
"""
生产安全基线工具

对应 IMPLEMENTATION_PLAN.md 阶段 0.4。

集中放：
- SECRET_KEY 加载（fail-fast）
- CORS 白名单
- 错误响应脱敏

调用方（backend/app.py）应该在初始化时：
    app.secret_key = load_secret_key()
    CORS(app, origins=get_cors_origins())
    @app.errorhandler(Exception)
    def _on_error(e):
        body, status = safe_error_response(e)
        return jsonify(body), status
"""

import logging
import os
import secrets
import traceback
from typing import List, Tuple

logger = logging.getLogger(__name__)


class SecretKeyMissingError(RuntimeError):
    """SECRET_KEY 未配置或过短时抛出，让启动 fail-fast"""


_MIN_SECRET_KEY_LEN = 16


def load_secret_key() -> str:
    """从环境变量 FLASK_SECRET_KEY 加载 Flask secret key

    生产部署 systemd unit 应在 EnvironmentFile 里设这个变量。

    异常：SecretKeyMissingError - 未设或太短
    """
    key = os.environ.get("FLASK_SECRET_KEY", "").strip()
    if not key:
        raise SecretKeyMissingError(
            "FLASK_SECRET_KEY 环境变量未设置。生产部署必须配置此变量；"
            "本地开发可以临时 `export FLASK_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')`"
        )
    if len(key) < _MIN_SECRET_KEY_LEN:
        raise SecretKeyMissingError(
            f"FLASK_SECRET_KEY 长度 {len(key)} 太短，至少需要 {_MIN_SECRET_KEY_LEN} 字符。"
            "避免开发用的临时短 key 不小心带到生产。"
        )
    return key


_PRODUCTION_ORIGINS = ["https://boss.jjjj789.win"]
_DEV_EXTRA_ORIGINS = ["http://localhost:3001", "http://127.0.0.1:3001"]


def get_cors_origins() -> List[str]:
    """返回允许跨域的 origin 白名单

    生产环境只允许公网域名；开发模式追加 localhost。
    绝不返回 `*`（避免任意 origin 跨域）。
    """
    origins = list(_PRODUCTION_ORIGINS)
    if os.environ.get("FLASK_ENV", "production").lower() == "development":
        origins.extend(_DEV_EXTRA_ORIGINS)
    return origins


def safe_error_response(exc: Exception) -> Tuple[dict, int]:
    """把异常包装成用户态响应 + 内部日志

    前端只看到：
        - 友好错误文案
        - error_id（让用户报错时能在日志里查具体堆栈）

    详细堆栈、内部路径、敏感字段都只写后端日志，不出现在响应里。

    参数：
        exc - 捕获的异常实例
    返回：
        (body_dict, status_code) - jsonify 用
    """
    error_id = secrets.token_urlsafe(6)  # 8 字符 url-safe（足够碰撞概率忽略）

    # 详细堆栈进日志
    logger.error(
        "请求处理异常 error_id=%s type=%s",
        error_id,
        type(exc).__name__,
        exc_info=True,
    )

    # 前端只见友好文案
    return (
        {
            "error": "服务异常，请稍后重试",
            "error_id": error_id,
        },
        500,
    )
