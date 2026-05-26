#!/usr/bin/env python3
"""
SQLite 状态层

集中管理云端多用户 SaaS 的所有持久化状态：
- users / profiles / tasks / rate_limits / quotas / invites

设计要点（详见 docs/IMPLEMENTATION_PLAN.md TD-2）：
- 单文件 SQLite，WAL 模式（并发读不阻塞写）
- 所有 schema 用 `IF NOT EXISTS` 创建，init 幂等
- TTL 字段（expires_at）配合 cleanup_* 方法定期清理
- 时间戳统一用 Unix 浮点秒（time.time()）便于跨语言/工具处理

线程安全：sqlite3.connect 在每个调用内打开/关闭，依赖 SQLite 自身的串行化。
高并发场景下可考虑改用连接池，但本期单 worker Flask 用不到。
"""

import hashlib
import os
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


_USER_ID_LEN = 16  # sha256[:16]
_INVITE_CODE_LEN = 8
_TASK_TTL_SECONDS = 24 * 3600  # 24h


class StateStore:
    """SQLite 状态层包装"""

    def __init__(self, db_path: str = "data/state.db"):
        """
        参数：
            db_path - SQLite 文件路径。父目录会自动创建。
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # ─── 初始化 ─────────────────────────────────────────────

    def init_schema(self) -> None:
        """创建所有表 + 索引。多次调用幂等。"""
        with self._connect() as conn:
            # WAL 模式：让读不阻塞写，提升 Flask + 后台 worker 并发性能
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA_SQL)
            conn.commit()

    # ─── 邀请码 ─────────────────────────────────────────────

    def create_invite(self) -> str:
        """生成 8 字符随机邀请码并存库

        返回：str - 邀请码
        """
        code = secrets.token_urlsafe(_INVITE_CODE_LEN)[:_INVITE_CODE_LEN]
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO invites (code, status, created_at) VALUES (?, 'unused', ?)",
                (code, now),
            )
            conn.commit()
        return code

    def consume_invite(self, code: str) -> Optional[str]:
        """消费邀请码 → 创建/返回对应 user_id

        参数：
            code - 邀请码（8 字符）
        返回：
            str - 派生出的 user_id（sha256[:16]）；无效或已用返回 None
        """
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM invites WHERE code = ?", (code,)
            ).fetchone()
            if not row or row["status"] != "unused":
                return None

            user_id = hashlib.sha256(code.encode()).hexdigest()[:_USER_ID_LEN]
            conn.execute(
                "UPDATE invites SET status = 'used', used_at = ?, user_id = ? WHERE code = ?",
                (now, user_id, code),
            )
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, invite_code, created_at, last_seen_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, code, now, now),
            )
            conn.commit()
            return user_id

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    # ─── Profile 映射 ──────────────────────────────────────

    def create_profile(self, user_id: str) -> str:
        """为 user_id 创建一个新 UUID profile（强制新建）

        返回：str - UUID
        """
        new_uuid = str(uuid.uuid4())
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO profiles (user_id, uuid, created_at, last_access_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, new_uuid, now, now),
            )
            conn.commit()
        return new_uuid

    def get_or_create_profile(self, user_id: str) -> str:
        """取该用户的 profile UUID，没有就创建（推荐用这个，幂等）

        返回：str - UUID
        """
        existing = self.get_profile_by_user(user_id)
        if existing:
            return existing["uuid"]
        return self.create_profile(user_id)

    def get_profile_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM profiles WHERE user_id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def touch_profile(self, user_id: str) -> None:
        """更新 last_access_at，用于 30 天 inactive 自动清理判定"""
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "UPDATE profiles SET last_access_at = ? WHERE user_id = ?", (now, user_id)
            )
            conn.commit()

    # ─── Task 记录 ────────────────────────────────────────

    def create_task(self, user_id: str, keyword: str, city: str) -> str:
        """创建一个 task 记录

        返回：str - task_id
        """
        task_id = str(uuid.uuid4())
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tasks (task_id, user_id, status, keyword, city, "
                "created_at, expires_at) VALUES (?, ?, 'pending', ?, ?, ?, ?)",
                (task_id, user_id, keyword, city, now, now + _TASK_TTL_SECONDS),
            )
            conn.commit()
        return task_id

    def get_task(self, task_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """取 task；若传 user_id，校验归属（防伪造 task_id 攻击）

        参数：
            task_id - task 主键
            user_id - 可选；指定时只有归属正确才返回
        """
        with self._connect() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ? AND user_id = ?",
                    (task_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
        return dict(row) if row else None

    def set_task_result(self, task_id: str, status: str, result_json: str) -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, result_json = ?, finished_at = ? "
                "WHERE task_id = ?",
                (status, result_json, now, task_id),
            )
            conn.commit()

    # ─── 限流 rate_limits ─────────────────────────────────

    def get_search_count(self, user_id: str, month: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT count FROM rate_limits WHERE user_id = ? AND month = ?",
                (user_id, month),
            ).fetchone()
        return row["count"] if row else 0

    def increment_search_count(self, user_id: str, month: str) -> int:
        """+1 并返回新值。原子操作（用 INSERT...ON CONFLICT）"""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO rate_limits (user_id, month, count) VALUES (?, ?, 1) "
                "ON CONFLICT(user_id, month) DO UPDATE SET count = count + 1",
                (user_id, month),
            )
            row = conn.execute(
                "SELECT count FROM rate_limits WHERE user_id = ? AND month = ?",
                (user_id, month),
            ).fetchone()
            conn.commit()
        return row["count"]

    # ─── Quotas API 成本 ──────────────────────────────────

    def add_api_usage(self, date: str, tokens: int, cost_cny: float) -> None:
        """累加当日 token + 成本（YYYY-MM-DD）"""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO quotas (date, tokens_used, cost_cny) VALUES (?, ?, ?) "
                "ON CONFLICT(date) DO UPDATE SET "
                "tokens_used = tokens_used + ?, cost_cny = cost_cny + ?",
                (date, tokens, cost_cny, tokens, cost_cny),
            )
            conn.commit()

    def get_daily_tokens(self, date: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT tokens_used FROM quotas WHERE date = ?", (date,)
            ).fetchone()
        return row["tokens_used"] if row else 0

    def get_daily_cost(self, date: str) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cost_cny FROM quotas WHERE date = ?", (date,)
            ).fetchone()
        return row["cost_cny"] if row else 0.0

    # ─── TTL 清理 ─────────────────────────────────────────

    def cleanup_expired_tasks(self) -> int:
        """删过期 task；返回删除条数"""
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE expires_at < ?", (now,))
            conn.commit()
            return cur.rowcount

    def cleanup_old_rate_limits(self, current_month: str) -> int:
        """清非当前月的 rate_limits；返回删除条数"""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM rate_limits WHERE month != ?", (current_month,)
            )
            conn.commit()
            return cur.rowcount

    # ─── 内部 ─────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        """打开连接，设置 row_factory 让查询返回类 dict 行"""
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


# ─── Schema 定义 ────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id      TEXT PRIMARY KEY,
    invite_code  TEXT NOT NULL,
    created_at   REAL NOT NULL,
    last_seen_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id        TEXT PRIMARY KEY,
    uuid           TEXT NOT NULL UNIQUE,
    created_at     REAL NOT NULL,
    last_access_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_profiles_last_access ON profiles(last_access_at);

CREATE TABLE IF NOT EXISTS tasks (
    task_id      TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    status       TEXT NOT NULL,
    keyword      TEXT,
    city         TEXT,
    result_json  TEXT,
    created_at   REAL NOT NULL,
    finished_at  REAL,
    expires_at   REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_expires ON tasks(expires_at);

CREATE TABLE IF NOT EXISTS rate_limits (
    user_id TEXT NOT NULL,
    month   TEXT NOT NULL,
    count   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, month),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS quotas (
    date         TEXT PRIMARY KEY,
    tokens_used  INTEGER NOT NULL DEFAULT 0,
    cost_cny     REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS invites (
    code         TEXT PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'unused',
    user_id      TEXT,
    created_at   REAL NOT NULL,
    used_at      REAL
);
"""
