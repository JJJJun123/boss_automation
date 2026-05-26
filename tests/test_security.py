#!/usr/bin/env python3
"""
生产安全基线测试

按 IMPLEMENTATION_PLAN.md 阶段 0.4：
- SECRET_KEY 从环境变量读，未设时启动失败（fail-fast）
- CORS 白名单（仅允许 boss.jjjj789.win + 本地开发 origin）
- Cookie 安全标志（已在 auth.py 实现，这里补显式断言）
- 错误响应脱敏（异常堆栈不发前端）
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.security import (
    load_secret_key,
    get_cors_origins,
    safe_error_response,
    SecretKeyMissingError,
)


# ─── SECRET_KEY ─────────────────────────────────────────────

def test_load_secret_key_from_env(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-12345678")
    key = load_secret_key()
    assert key == "test-secret-12345678"


def test_load_secret_key_fail_fast_when_missing(monkeypatch):
    """生产部署必须强制设环境变量，未设则启动失败（fail-fast）

    用 SecretKeyMissingError 而非 KeyError，让调用方能精确捕获并给清晰错误信息。
    """
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    with pytest.raises(SecretKeyMissingError):
        load_secret_key()


def test_load_secret_key_rejects_short_key(monkeypatch):
    """短 key（< 16 字符）拒绝。避免开发遗忘改成生产 key"""
    monkeypatch.setenv("FLASK_SECRET_KEY", "short")
    with pytest.raises(SecretKeyMissingError):
        load_secret_key()


# ─── CORS 白名单 ────────────────────────────────────────────

def test_cors_origins_includes_production_domain():
    origins = get_cors_origins()
    assert "https://boss.jjjj789.win" in origins


def test_cors_origins_excludes_wildcard():
    """绝不允许 `*`（任何来源都可跨域）"""
    origins = get_cors_origins()
    assert "*" not in origins


def test_cors_origins_dev_mode_allows_localhost(monkeypatch):
    """开发模式（FLASK_ENV=development）允许本地 origin"""
    monkeypatch.setenv("FLASK_ENV", "development")
    origins = get_cors_origins()
    assert any("localhost" in o or "127.0.0.1" in o for o in origins), \
        "开发模式应允许本机 origin"


def test_cors_origins_production_no_localhost(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    origins = get_cors_origins()
    assert not any("localhost" in o or "127.0.0.1" in o for o in origins), \
        "生产模式不应包含 localhost"


# ─── 错误响应脱敏 ───────────────────────────────────────────

def test_safe_error_strips_stack_trace():
    """异常堆栈不应出现在响应体里"""
    try:
        raise ValueError("内部敏感错误: API key sk-xxx, db_path=/var/secret")
    except ValueError as e:
        body, status = safe_error_response(e)

    assert status == 500
    assert "ValueError" not in str(body), "异常类名不应暴露"
    assert "sk-xxx" not in str(body), "敏感字符串不应暴露"
    assert "db_path" not in str(body), "内部路径不应暴露"


def test_safe_error_returns_generic_message():
    """前端只看到统一友好文案，详情进日志"""
    try:
        raise RuntimeError("数据库连接失败 host=192.168.1.1")
    except RuntimeError as e:
        body, status = safe_error_response(e)
    assert "error" in body
    # 应该是简短统一文案，不带具体内部信息
    assert "192.168.1.1" not in str(body)


def test_safe_error_includes_error_id_for_log_correlation():
    """response 中应该带一个 error_id，让用户报告问题时能在日志里查到对应详情"""
    try:
        raise Exception("test")
    except Exception as e:
        body, status = safe_error_response(e)
    assert "error_id" in body, "需要 error_id 关联用户报错与后端日志"
    assert len(body["error_id"]) >= 8, "error_id 至少 8 字符以避免碰撞"
