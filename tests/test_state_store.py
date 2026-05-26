#!/usr/bin/env python3
"""
SQLite 状态层测试

覆盖：
- 数据库初始化（schema 创建、WAL 模式、幂等性）
- 6 张表的基础 CRUD：users / profiles / tasks / rate_limits / quotas / invites
- TTL 清理（过期数据自动删）

按 design.md 与 IMPLEMENTATION_PLAN.md TD-2 的要求。
"""

import os
import sys
import threading
import time
import sqlite3
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.state_store import StateStore


@pytest.fixture
def store(tmp_path):
    """每个测试用独立的临时 db，避免污染"""
    db_path = tmp_path / "test_state.db"
    s = StateStore(db_path=str(db_path))
    s.init_schema()
    return s


# ─── 初始化 ─────────────────────────────────────────────────

def test_init_creates_db_file(tmp_path):
    db_path = tmp_path / "fresh.db"
    s = StateStore(db_path=str(db_path))
    s.init_schema()
    assert db_path.exists()


def test_init_creates_all_tables(store):
    """7 张表 + 索引都创建（含 sessions）"""
    expected = {"users", "profiles", "tasks", "rate_limits", "quotas", "invites", "sessions"}
    with sqlite3.connect(store.db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    tables = {r[0] for r in rows}
    assert expected.issubset(tables), f"缺表: {expected - tables}"


def test_init_is_idempotent(tmp_path):
    """init 跑两次不该报错（schema 已存在用 IF NOT EXISTS）"""
    db_path = tmp_path / "idem.db"
    s = StateStore(db_path=str(db_path))
    s.init_schema()
    s.init_schema()  # 不应抛异常


def test_wal_mode_enabled(store):
    """WAL 模式让并发读不阻塞写（关键性能优化）"""
    with sqlite3.connect(store.db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal", f"WAL 未启用，当前: {mode}"


# ─── 邀请码 + 用户 ─────────────────────────────────────────

def test_create_invite_and_consume(store):
    """创建邀请码 → 消费 → 返回 (user_id, session_token)"""
    code = store.create_invite()
    assert len(code) == 8

    result = store.consume_invite(code)
    assert result is not None
    user_id, token = result
    assert user_id and len(user_id) >= 12
    assert token and len(token) >= 32, "session token 必须长（>= 32 字符）以避免暴力枚举"


def test_consume_invalid_invite_returns_none(store):
    assert store.consume_invite("invalidd") is None


def test_consume_used_invite_returns_none(store):
    """同一邀请码不能被复用"""
    code = store.create_invite()
    store.consume_invite(code)
    assert store.consume_invite(code) is None, "已使用的邀请码必须拒绝"


def test_get_user_after_consume(store):
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    user = store.get_user(user_id)
    assert user is not None
    assert user["user_id"] == user_id


def test_user_id_is_independent_of_invite_code(store):
    """user_id 不应该从邀请码确定性派生（防邀请码泄露=伪造登录）

    Codex P1-1：原实现 user_id = sha256(code)[:16]，任何人拿到 code 就能算出 cookie 值。
    """
    import hashlib
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    forbidden = hashlib.sha256(code.encode()).hexdigest()[:16]
    assert user_id != forbidden, "user_id 必须用 secrets 独立生成，不能从邀请码派生"


def test_concurrent_invite_consume_only_one_wins(store):
    """并发两个请求消费同一邀请码 → 只有一个成功（Codex P1-2 防竞态）"""
    code = store.create_invite()
    results = []
    lock = threading.Lock()

    def consume():
        r = store.consume_invite(code)
        with lock:
            results.append(r)

    threads = [threading.Thread(target=consume) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = [r for r in results if r is not None]
    assert len(successes) == 1, f"10 并发消费同码必须只有 1 个成功，实际 {len(successes)}"


# ─── Profile 映射 ──────────────────────────────────────────

def test_create_and_get_profile(store):
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    uuid = store.create_profile(user_id)
    assert uuid is not None
    assert len(uuid) > 0

    profile = store.get_profile_by_user(user_id)
    assert profile["uuid"] == uuid


def test_same_user_returns_same_profile(store):
    """同一用户多次取 profile 返回同一个 UUID（不重复创建）"""
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    uuid1 = store.get_or_create_profile(user_id)
    uuid2 = store.get_or_create_profile(user_id)
    assert uuid1 == uuid2


def test_different_users_have_different_profiles(store):
    """两个用户必须拿不同 UUID（隔离）"""
    code_a = store.create_invite()
    code_b = store.create_invite()
    user_a, _ = store.consume_invite(code_a)
    user_b, _ = store.consume_invite(code_b)
    uuid_a = store.get_or_create_profile(user_a)
    uuid_b = store.get_or_create_profile(user_b)
    assert uuid_a != uuid_b


def test_touch_profile_updates_last_access(store):
    """每次访问 profile 应该更新 last_access 时间戳，用于 30 天过期判定"""
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    store.get_or_create_profile(user_id)
    before = store.get_profile_by_user(user_id)["last_access_at"]
    time.sleep(0.01)
    store.touch_profile(user_id)
    after = store.get_profile_by_user(user_id)["last_access_at"]
    assert after > before


# ─── Task 记录 ────────────────────────────────────────────

def test_create_task_and_set_result(store):
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    task_id = store.create_task(user_id, keyword="AI算法工程师", city="shanghai")
    assert task_id is not None

    store.set_task_result(task_id, status="success", result_json='{"jobs": []}')
    task = store.get_task(task_id, user_id=user_id)
    assert task["status"] == "success"
    assert task["result_json"] == '{"jobs": []}'


def test_task_belongs_to_correct_user(store):
    """伪造 task_id 跨用户访问应该返回 None（IDOR 防护）"""
    code_a = store.create_invite()
    code_b = store.create_invite()
    user_a, _ = store.consume_invite(code_a)
    user_b, _ = store.consume_invite(code_b)
    task_id = store.create_task(user_a, keyword="x", city="shanghai")

    # 用 user_b 取 user_a 的 task → 应该拒绝
    assert store.get_task(task_id, user_id=user_b) is None
    assert store.get_task(task_id, user_id=user_a) is not None


def test_get_task_requires_user_id_arg(store):
    """get_task 必须强制传 user_id（Codex P2 防 IDOR 误用）"""
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    task_id = store.create_task(user_id, keyword="x", city="shanghai")

    # 不传 user_id 应抛 TypeError
    with pytest.raises(TypeError):
        store.get_task(task_id)


# ─── 限流 rate_limits ─────────────────────────────────────

def test_rate_limit_increments(store):
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    month = "2026-05"

    assert store.get_search_count(user_id, month) == 0
    store.increment_search_count(user_id, month)
    assert store.get_search_count(user_id, month) == 1
    store.increment_search_count(user_id, month)
    assert store.get_search_count(user_id, month) == 2


def test_rate_limit_isolated_per_user(store):
    code_a = store.create_invite()
    code_b = store.create_invite()
    user_a, _ = store.consume_invite(code_a)
    user_b, _ = store.consume_invite(code_b)
    month = "2026-05"

    store.increment_search_count(user_a, month)
    store.increment_search_count(user_a, month)
    store.increment_search_count(user_b, month)

    assert store.get_search_count(user_a, month) == 2
    assert store.get_search_count(user_b, month) == 1


# ─── Quotas API 成本 ──────────────────────────────────────

def test_quota_accumulates(store):
    date = "2026-05-26"
    assert store.get_daily_cost(date) == 0.0

    store.add_api_usage(date, tokens=1000, cost_cny=0.5)
    store.add_api_usage(date, tokens=2000, cost_cny=1.0)

    assert store.get_daily_tokens(date) == 3000
    assert store.get_daily_cost(date) == 1.5


# ─── TTL 清理 ─────────────────────────────────────────────

def test_cleanup_expired_tasks(store):
    """24h 过期 task 应该被清"""
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    task_id = store.create_task(user_id, keyword="x", city="shanghai")

    # 手动改 expires_at 到过去
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("UPDATE tasks SET expires_at = ? WHERE task_id = ?", (time.time() - 60, task_id))
        conn.commit()

    deleted = store.cleanup_expired_tasks()
    assert deleted == 1
    # 用 _get_task_unscoped 验证真删（不带 user_id 检查归属）
    assert store._get_task_unscoped(task_id) is None


# ─── Session Token ────────────────────────────────────────

def test_session_token_lookup(store):
    """consume_invite 签发的 token 能反查到对应 user_id"""
    code = store.create_invite()
    user_id, token = store.consume_invite(code)
    assert store.get_user_by_session_token(token) == user_id


def test_session_token_independent_of_invite(store):
    """token 不能从邀请码或 user_id 反推（必须随机）"""
    code = store.create_invite()
    user_id, token = store.consume_invite(code)
    import hashlib
    assert hashlib.sha256(code.encode()).hexdigest() not in token
    assert user_id not in token


def test_unknown_token_returns_none(store):
    assert store.get_user_by_session_token("fake-token-not-issued") is None


def test_empty_token_returns_none(store):
    assert store.get_user_by_session_token("") is None
    assert store.get_user_by_session_token(None) is None


def test_revoked_token_returns_none(store):
    """revoke 后 token 立即失效（登出）"""
    code = store.create_invite()
    _, token = store.consume_invite(code)
    store.revoke_session_token(token)
    assert store.get_user_by_session_token(token) is None


def test_expired_token_returns_none(store):
    """过期 session 不应认证"""
    code = store.create_invite()
    user_id, token = store.consume_invite(code)
    # 手动改 expires_at 到过去
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("UPDATE sessions SET expires_at = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
    assert store.get_user_by_session_token(token) is None


def test_only_hash_in_db_not_token(store):
    """数据库只存 token hash，不存原文"""
    code = store.create_invite()
    _, token = store.consume_invite(code)
    with sqlite3.connect(store.db_path) as conn:
        rows = conn.execute("SELECT * FROM sessions").fetchall()
    db_content = str(rows)
    assert token not in db_content, "明文 token 绝不能进数据库"


def test_cleanup_expired_sessions(store):
    """cleanup_expired_sessions 清掉过期 session"""
    code = store.create_invite()
    user_id, token = store.consume_invite(code)
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("UPDATE sessions SET expires_at = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
    assert store.cleanup_expired_sessions() == 1


def test_cleanup_old_rate_limits(store):
    """非当前月的 rate_limits 应该被清"""
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    store.increment_search_count(user_id, "2025-01")  # 历史月
    store.increment_search_count(user_id, "2026-05")  # 当前月

    deleted = store.cleanup_old_rate_limits(current_month="2026-05")
    assert deleted == 1
    assert store.get_search_count(user_id, "2025-01") == 0
    assert store.get_search_count(user_id, "2026-05") == 1
