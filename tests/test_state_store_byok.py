#!/usr/bin/env python3
"""StateStore BYOK 扩展测试 — user_api_keys 表 + 试用配额

覆盖：
- set/get/delete roundtrip、UPSERT 覆盖
- 外键级联删除
- trial_searches_used 计数与老库迁移
"""

import os
import sqlite3
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.state_store import StateStore


@pytest.fixture
def store(tmp_path):
    s = StateStore(db_path=str(tmp_path / "byok.db"))
    s.init_schema()
    return s


@pytest.fixture
def user_id(store):
    code = store.create_invite()
    uid, _token = store.consume_invite(code)
    return uid


# ─── user_api_keys CRUD ─────────────────────────────────


class TestUserApiKeys:
    def test_get_before_set_returns_none(self, store, user_id):
        assert store.get_user_api_key(user_id) is None

    def test_set_get_roundtrip(self, store, user_id):
        store.set_user_api_key(user_id, "deepseek", "encrypted-blob-1")
        row = store.get_user_api_key(user_id)
        assert row["provider"] == "deepseek"
        assert row["key_encrypted"] == "encrypted-blob-1"

    def test_upsert_overwrites_on_provider_switch(self, store, user_id):
        """换 provider 覆盖旧条目——一个用户只有一条"""
        store.set_user_api_key(user_id, "deepseek", "blob-ds")
        store.set_user_api_key(user_id, "claude", "blob-cl")
        row = store.get_user_api_key(user_id)
        assert row["provider"] == "claude"
        assert row["key_encrypted"] == "blob-cl"

    def test_delete(self, store, user_id):
        store.set_user_api_key(user_id, "deepseek", "blob")
        assert store.delete_user_api_key(user_id) is True
        assert store.get_user_api_key(user_id) is None

    def test_delete_nonexistent_returns_false(self, store, user_id):
        assert store.delete_user_api_key(user_id) is False

    def test_keys_isolated_between_users(self, store):
        c1, c2 = store.create_invite(), store.create_invite()
        u1, _ = store.consume_invite(c1)
        u2, _ = store.consume_invite(c2)
        store.set_user_api_key(u1, "deepseek", "blob-u1")
        assert store.get_user_api_key(u2) is None

    def test_cascade_delete_with_user(self, store, user_id):
        """删用户连带删 key（外键 ON DELETE CASCADE）"""
        store.set_user_api_key(user_id, "deepseek", "blob")
        with store._connect() as conn:
            conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()
        assert store.get_user_api_key(user_id) is None


# ─── 试用配额 ────────────────────────────────────────────


class TestTrialQuota:
    def test_initial_usage_zero(self, store, user_id):
        assert store.get_trial_usage(user_id) == 0

    def test_increment(self, store, user_id):
        store.increment_trial_usage(user_id)
        assert store.get_trial_usage(user_id) == 1
        store.increment_trial_usage(user_id)
        store.increment_trial_usage(user_id)
        assert store.get_trial_usage(user_id) == 3

    def test_increment_returns_new_value(self, store, user_id):
        assert store.increment_trial_usage(user_id) == 1
        assert store.increment_trial_usage(user_id) == 2

    def test_usage_isolated_between_users(self, store):
        c1, c2 = store.create_invite(), store.create_invite()
        u1, _ = store.consume_invite(c1)
        u2, _ = store.consume_invite(c2)
        store.increment_trial_usage(u1)
        assert store.get_trial_usage(u2) == 0

    def test_unknown_user_usage_zero(self, store):
        assert store.get_trial_usage("no-such-user") == 0


# ─── 老库迁移 ────────────────────────────────────────────


class TestOrphanTaskCleanup:
    """服务重启后孤儿任务清理：running/pending 任务的线程已死，
    必须在启动时标 failed，否则永久挡住该用户的新任务（409）"""

    def test_terminate_orphan_active_tasks(self, store, user_id):
        task_id = store.create_task(user_id, keyword="AI", city="shanghai")
        store.set_task_status(task_id, "running", progress=30)

        n = store.terminate_orphan_active_tasks()

        assert n == 1
        task = store._get_task_unscoped(task_id)
        assert task["status"] == "failed"
        # 解卡后能立刻建新任务（partial unique index 不再拦截）
        new_id = store.create_task(user_id, keyword="AI", city="shanghai")
        assert new_id

    def test_no_orphans_returns_zero(self, store, user_id):
        assert store.terminate_orphan_active_tasks() == 0

    def test_terminated_task_carries_restart_marker(self, store, user_id):
        import json
        task_id = store.create_task(user_id, keyword="AI", city="shanghai")
        store.set_task_status(task_id, "running")
        store.terminate_orphan_active_tasks()
        task = store._get_task_unscoped(task_id)
        result = json.loads(task["result_json"] or "{}")
        assert result.get("error") == "server_restarted"


class TestMigration:
    def test_old_db_without_trial_column_migrates(self, tmp_path):
        """已存在的老库（users 无 trial_searches_used 列）init_schema 后可用"""
        db = str(tmp_path / "old.db")
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE users (user_id TEXT PRIMARY KEY, invite_code TEXT NOT NULL, "
            "created_at REAL NOT NULL, last_seen_at REAL NOT NULL)"
        )
        conn.execute(
            "INSERT INTO users VALUES ('u-old', 'CODE1234', 1.0, 1.0)"
        )
        conn.commit()
        conn.close()

        s = StateStore(db_path=db)
        s.init_schema()
        assert s.get_trial_usage("u-old") == 0
        assert s.increment_trial_usage("u-old") == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
