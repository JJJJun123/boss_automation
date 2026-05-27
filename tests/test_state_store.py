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

def test_set_task_status_updates_state(store):
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    task_id = store.create_task(user_id, keyword="x", city="shanghai")

    store.set_task_status(task_id, "running", progress=50)
    task = store.get_task(task_id, user_id=user_id)
    assert task["status"] == "running"
    assert task["progress"] == 50


def test_get_user_active_task_finds_running(store):
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    task_id = store.create_task(user_id, keyword="x", city="shanghai")
    store.set_task_status(task_id, "running")

    active = store.get_user_active_task(user_id)
    assert active is not None
    assert active["task_id"] == task_id


def test_get_user_active_task_ignores_finished(store):
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    task_id = store.create_task(user_id, keyword="x", city="shanghai")
    store.set_task_result(task_id, "success", '{}')

    active = store.get_user_active_task(user_id)
    assert active is None, "完成的任务不算 active"


def test_cancel_task_only_for_owner(store):
    code_a = store.create_invite()
    code_b = store.create_invite()
    user_a, _ = store.consume_invite(code_a)
    user_b, _ = store.consume_invite(code_b)
    task_id = store.create_task(user_a, keyword="x", city="shanghai")

    # B 不能取消 A 的
    assert store.cancel_task(task_id, user_id=user_b) is False

    # A 能取消
    assert store.cancel_task(task_id, user_id=user_a) is True
    task = store.get_task(task_id, user_id=user_a)
    assert task["status"] == "cancelled"


def test_cancel_finished_task_returns_false(store):
    """已完成/失败/已取消的任务不能再次取消（避免误状态流转）"""
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    task_id = store.create_task(user_id, keyword="x", city="shanghai")
    store.set_task_result(task_id, "success", '{}')
    assert store.cancel_task(task_id, user_id=user_id) is False


def test_list_user_tasks_sorted_desc(store):
    """连续创建任务前需先终结上一个（partial unique index 限制）"""
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    import time as _t
    tid1 = store.create_task(user_id, keyword="a", city="shanghai")
    store.set_task_result(tid1, "success", '{}')
    _t.sleep(0.01)
    tid2 = store.create_task(user_id, keyword="b", city="shanghai")

    tasks = store.list_user_tasks(user_id, limit=10)
    assert len(tasks) == 2
    assert tasks[0]["task_id"] == tid2  # 最新的在前


def test_list_user_tasks_isolated(store):
    code_a = store.create_invite()
    code_b = store.create_invite()
    user_a, _ = store.consume_invite(code_a)
    user_b, _ = store.consume_invite(code_b)
    store.create_task(user_a, keyword="x", city="shanghai")
    store.create_task(user_b, keyword="y", city="shanghai")

    a_tasks = store.list_user_tasks(user_a)
    assert len(a_tasks) == 1
    assert a_tasks[0]["keyword"] == "x"


def test_create_task_partial_unique_index_blocks_concurrent_active(store):
    """Codex P1-2：partial unique index 应阻止同用户两个 pending/running 任务"""
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    store.create_task(user_id, keyword="x", city="shanghai")
    import sqlite3 as _s
    with pytest.raises(_s.IntegrityError):
        store.create_task(user_id, keyword="y", city="shanghai")


def test_create_task_allowed_after_active_finished(store):
    """active 任务完成后允许再开新任务"""
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    tid1 = store.create_task(user_id, keyword="x", city="shanghai")
    store.set_task_result(tid1, "success", '{}')
    # 现在没有 active 任务，应该能创建新的
    tid2 = store.create_task(user_id, keyword="y", city="shanghai")
    assert tid2 != tid1


def test_set_task_status_rejected_after_cancel(store):
    """Codex P1-3：cancel 后 set_task_status 不应改回 running"""
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    task_id = store.create_task(user_id, keyword="x", city="shanghai")
    store.cancel_task(task_id, user_id=user_id)
    # worker 试图改回 running 应该失败
    result = store.set_task_status(task_id, "running", progress=50)
    assert result is False
    task = store.get_task(task_id, user_id=user_id)
    assert task["status"] == "cancelled"


def test_set_task_result_rejected_after_cancel(store):
    """Codex P1-3：cancel 后 set_task_result 不应覆盖成 success"""
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    task_id = store.create_task(user_id, keyword="x", city="shanghai")
    store.cancel_task(task_id, user_id=user_id)
    result = store.set_task_result(task_id, "success", '{"qualified_jobs": []}')
    assert result is False
    task = store.get_task(task_id, user_id=user_id)
    assert task["status"] == "cancelled"
    assert task["result_json"] is None


def test_set_task_result_sets_progress_100(store):
    """Codex P2-1：终态应统一 progress=100"""
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    task_id = store.create_task(user_id, keyword="x", city="shanghai")
    store.set_task_status(task_id, "running", progress=60)
    store.set_task_result(task_id, "success", '{}')
    task = store.get_task(task_id, user_id=user_id)
    assert task["progress"] == 100


def test_get_latest_completed_skips_failed_and_cancelled(store):
    """Codex P2-2：fallback 取最新有结果的，跳过 failed/cancelled"""
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)

    import time as _t
    tid1 = store.create_task(user_id, keyword="ok", city="shanghai")
    store.set_task_result(tid1, "success", '{"qualified_jobs": [1, 2]}')

    _t.sleep(0.01)
    tid2 = store.create_task(user_id, keyword="bad", city="shanghai")
    store.set_task_result(tid2, "failed", '{"error": "x"}')

    _t.sleep(0.01)
    tid3 = store.create_task(user_id, keyword="abandoned", city="shanghai")
    store.cancel_task(tid3, user_id=user_id)

    latest = store.get_latest_completed_task(user_id)
    assert latest is not None
    assert latest["task_id"] == tid1, "应跳过 failed/cancelled，返回最新成功的"


def test_init_schema_migrates_old_db_with_duplicate_active_tasks(tmp_path):
    """Codex round 2 P1-1：旧 db 有同用户多个 active task 时迁移应主动清理

    不能让 CREATE UNIQUE INDEX 直接失败把 app 卡死启动。
    """
    import sqlite3 as _s
    import time as _t
    db_path = tmp_path / "old.db"
    with _s.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE users (user_id TEXT PRIMARY KEY, invite_code TEXT NOT NULL,
                                created_at REAL NOT NULL, last_seen_at REAL NOT NULL);
            CREATE TABLE tasks (
                task_id TEXT PRIMARY KEY, user_id TEXT, status TEXT,
                keyword TEXT, city TEXT, result_json TEXT,
                created_at REAL, finished_at REAL, expires_at REAL
            );
        """)
        # 模拟同用户两个 pending task（旧 db 历史脏数据）
        now = _t.time()
        conn.execute("INSERT INTO users VALUES ('u1', 'code1', ?, ?)", (now, now))
        conn.execute("INSERT INTO tasks (task_id, user_id, status, created_at, expires_at) "
                     "VALUES ('t1', 'u1', 'pending', ?, ?)", (now - 100, now + 1000))
        conn.execute("INSERT INTO tasks (task_id, user_id, status, created_at, expires_at) "
                     "VALUES ('t2', 'u1', 'running', ?, ?)", (now - 50, now + 1000))
        conn.commit()

    from utils.state_store import StateStore
    s = StateStore(db_path=str(db_path))
    # 不应抛 IntegrityError 等启动错误
    s.init_schema()

    # t2 是更新的 → 保留为 active；t1 应被标记 failed
    with _s.connect(db_path) as conn:
        conn.row_factory = _s.Row
        rows = conn.execute("SELECT task_id, status FROM tasks ORDER BY task_id").fetchall()
    statuses = {r["task_id"]: r["status"] for r in rows}
    # 应该一个 active 一个 failed
    assert sorted(statuses.values()) in (
        ["failed", "pending"],
        ["failed", "running"],
    ), f"统一只保留 1 个 active，实际 {statuses}"


def test_init_schema_migrates_old_db_missing_progress(tmp_path):
    """Codex P1-1：老 db 没有 progress 列时 init_schema 自动 ALTER"""
    import sqlite3 as _s
    db_path = tmp_path / "old.db"
    # 模拟老 db：手动建无 progress 列的 tasks 表
    with _s.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE users (user_id TEXT PRIMARY KEY, invite_code TEXT NOT NULL,
                                created_at REAL NOT NULL, last_seen_at REAL NOT NULL);
            CREATE TABLE tasks (
                task_id TEXT PRIMARY KEY, user_id TEXT, status TEXT,
                keyword TEXT, city TEXT, result_json TEXT,
                created_at REAL, finished_at REAL, expires_at REAL
            );
        """)
        conn.commit()

    # init_schema 应该 ALTER 进 progress 列
    from utils.state_store import StateStore
    s = StateStore(db_path=str(db_path))
    s.init_schema()

    with _s.connect(db_path) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    assert "progress" in cols, "init_schema 应该 ALTER 加 progress 列"


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
