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
    """6 张表 + 索引都创建"""
    expected = {"users", "profiles", "tasks", "rate_limits", "quotas", "invites"}
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
    """创建邀请码 → 消费 → 派生 user_id"""
    code = store.create_invite()
    assert len(code) == 8

    user_id = store.consume_invite(code)
    assert user_id is not None
    assert len(user_id) == 16  # sha256[:16]


def test_consume_invalid_invite_returns_none(store):
    assert store.consume_invite("invalidd") is None


def test_consume_used_invite_returns_none(store):
    """同一邀请码不能被复用"""
    code = store.create_invite()
    store.consume_invite(code)
    assert store.consume_invite(code) is None, "已使用的邀请码必须拒绝"


def test_get_user_after_consume(store):
    code = store.create_invite()
    user_id = store.consume_invite(code)
    user = store.get_user(user_id)
    assert user is not None
    assert user["user_id"] == user_id


# ─── Profile 映射 ──────────────────────────────────────────

def test_create_and_get_profile(store):
    code = store.create_invite()
    user_id = store.consume_invite(code)
    uuid = store.create_profile(user_id)
    assert uuid is not None
    assert len(uuid) > 0

    profile = store.get_profile_by_user(user_id)
    assert profile["uuid"] == uuid


def test_same_user_returns_same_profile(store):
    """同一用户多次取 profile 返回同一个 UUID（不重复创建）"""
    code = store.create_invite()
    user_id = store.consume_invite(code)
    uuid1 = store.get_or_create_profile(user_id)
    uuid2 = store.get_or_create_profile(user_id)
    assert uuid1 == uuid2


def test_different_users_have_different_profiles(store):
    """两个用户必须拿不同 UUID（隔离）"""
    code_a = store.create_invite()
    code_b = store.create_invite()
    user_a = store.consume_invite(code_a)
    user_b = store.consume_invite(code_b)
    uuid_a = store.get_or_create_profile(user_a)
    uuid_b = store.get_or_create_profile(user_b)
    assert uuid_a != uuid_b


def test_touch_profile_updates_last_access(store):
    """每次访问 profile 应该更新 last_access 时间戳，用于 30 天过期判定"""
    code = store.create_invite()
    user_id = store.consume_invite(code)
    store.get_or_create_profile(user_id)
    before = store.get_profile_by_user(user_id)["last_access_at"]
    time.sleep(0.01)
    store.touch_profile(user_id)
    after = store.get_profile_by_user(user_id)["last_access_at"]
    assert after > before


# ─── Task 记录 ────────────────────────────────────────────

def test_create_task_and_set_result(store):
    code = store.create_invite()
    user_id = store.consume_invite(code)
    task_id = store.create_task(user_id, keyword="AI算法工程师", city="shanghai")
    assert task_id is not None

    store.set_task_result(task_id, status="success", result_json='{"jobs": []}')
    task = store.get_task(task_id)
    assert task["status"] == "success"
    assert task["result_json"] == '{"jobs": []}'


def test_task_belongs_to_correct_user(store):
    """伪造 task_id 跨用户访问应该返回 None"""
    code_a = store.create_invite()
    code_b = store.create_invite()
    user_a = store.consume_invite(code_a)
    user_b = store.consume_invite(code_b)
    task_id = store.create_task(user_a, keyword="x", city="shanghai")

    # 用 user_b 取 user_a 的 task → 应该拒绝
    assert store.get_task(task_id, user_id=user_b) is None
    assert store.get_task(task_id, user_id=user_a) is not None


# ─── 限流 rate_limits ─────────────────────────────────────

def test_rate_limit_increments(store):
    code = store.create_invite()
    user_id = store.consume_invite(code)
    month = "2026-05"

    assert store.get_search_count(user_id, month) == 0
    store.increment_search_count(user_id, month)
    assert store.get_search_count(user_id, month) == 1
    store.increment_search_count(user_id, month)
    assert store.get_search_count(user_id, month) == 2


def test_rate_limit_isolated_per_user(store):
    code_a = store.create_invite()
    code_b = store.create_invite()
    user_a = store.consume_invite(code_a)
    user_b = store.consume_invite(code_b)
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
    user_id = store.consume_invite(code)
    task_id = store.create_task(user_id, keyword="x", city="shanghai")

    # 手动改 expires_at 到过去
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("UPDATE tasks SET expires_at = ? WHERE task_id = ?", (time.time() - 60, task_id))
        conn.commit()

    deleted = store.cleanup_expired_tasks()
    assert deleted == 1
    assert store.get_task(task_id) is None


def test_cleanup_old_rate_limits(store):
    """非当前月的 rate_limits 应该被清"""
    code = store.create_invite()
    user_id = store.consume_invite(code)
    store.increment_search_count(user_id, "2025-01")  # 历史月
    store.increment_search_count(user_id, "2026-05")  # 当前月

    deleted = store.cleanup_old_rate_limits(current_month="2026-05")
    assert deleted == 1
    assert store.get_search_count(user_id, "2025-01") == 0
    assert store.get_search_count(user_id, "2026-05") == 1
