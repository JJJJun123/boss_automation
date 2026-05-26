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
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


_INVITE_CODE_LEN = 8
_TASK_TTL_SECONDS = 24 * 3600  # 24h
_SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30 天
_BUSY_TIMEOUT_MS = 5000  # SQLite 锁等待时长


def _hash_token(token: str) -> str:
    """对 session token 做 hash，仅存 hash 不存原 token（防 db 泄漏后 cookie 直接复用）"""
    return hashlib.sha256(token.encode()).hexdigest()


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

    def consume_invite(self, code: str) -> Optional[Tuple[str, str]]:
        """消费邀请码 → 创建用户 + 签发 session token（一个事务原子完成）

        三个写入（UPDATE invites / INSERT users / INSERT sessions）必须在
        同一事务内提交或回滚，否则邀请码可能被 consume 但用户/session 未建。

        通过单条原子 UPDATE WHERE status='unused' + rowcount 检查保证并发安全：
        两个请求同时来，只有第一个 UPDATE 成功，第二个 rowcount=0 拒绝。

        user_id 与 session_token 都用 secrets 独立生成，**不再从邀请码派生**——
        即便邀请码泄露也无法反推 cookie。

        参数：
            code - 邀请码（8 字符）
        返回：
            (user_id, session_token) - 二元组；token 用于设 cookie
            None - 邀请码无效或已被消费
        """
        now = time.time()
        token = secrets.token_urlsafe(32)
        token_hash = _hash_token(token)

        # 单连接 + 显式事务，确保三个写入要么全成要么全回滚
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")

            # user_id 极小概率碰撞时重试（不用 INSERT OR IGNORE 掩盖问题）
            for attempt in range(5):
                user_id = secrets.token_urlsafe(12)  # 16 字符
                existing = conn.execute(
                    "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
                ).fetchone()
                if not existing:
                    break
            else:
                conn.execute("ROLLBACK")
                return None  # 极不可能发生（5 次 96-bit 全碰撞）

            cur = conn.execute(
                "UPDATE invites SET status = 'used', used_at = ?, user_id = ? "
                "WHERE code = ? AND status = 'unused'",
                (now, user_id, code),
            )
            if cur.rowcount == 0:
                conn.execute("ROLLBACK")
                return None

            conn.execute(
                "INSERT INTO users (user_id, invite_code, created_at, last_seen_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, code, now, now),
            )
            conn.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (token_hash, user_id, now, now + _SESSION_TTL_SECONDS),
            )
            conn.execute("COMMIT")
            return user_id, token
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()

    # ─── Session Token ────────────────────────────────────

    def create_session_token(self, user_id: str) -> str:
        """为 user_id 签发新 session token；返回原文 token（只此一次能看到，库里只存 hash）"""
        token = secrets.token_urlsafe(32)
        token_hash = _hash_token(token)
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (token_hash, user_id, now, now + _SESSION_TTL_SECONDS),
            )
            conn.commit()
        return token

    def get_user_by_session_token(self, token: str) -> Optional[str]:
        """通过 cookie 中的 token 反查 user_id；过期或不存在返回 None"""
        if not token:
            return None
        token_hash = _hash_token(token)
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, expires_at FROM sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
        if not row:
            return None
        if row["expires_at"] < now:
            return None
        return row["user_id"]

    def revoke_session_token(self, token: str) -> None:
        """删除指定 session token（登出场景）"""
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))
            conn.commit()

    def cleanup_expired_sessions(self) -> int:
        """删过期 session；返回删除条数"""
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            conn.commit()
            return cur.rowcount

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

    def get_task(self, task_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """取 task，强制按 user_id 校验归属（防 IDOR）

        参数：
            task_id - task 主键
            user_id - 必传；只有归属正确才返回
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ? AND user_id = ?",
                (task_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def _get_task_unscoped(self, task_id: str) -> Optional[Dict[str, Any]]:
        """内部用：跳过归属校验取 task。仅给 admin/cleanup/test 用，**不要给路由直调**"""
        with self._connect() as conn:
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
        """打开连接

        - row_factory = sqlite3.Row 让查询返回类 dict 行
        - busy_timeout 让并发写时短暂等待，避免立刻 "database is locked" 抛错
        - foreign_keys 启用级联删除（SQLite 默认关）
        - isolation_level=None 用 autocommit 模式；事务由调用方显式 commit/rollback
        """
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
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

CREATE TABLE IF NOT EXISTS sessions (
    token_hash   TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    created_at   REAL NOT NULL,
    expires_at   REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
"""
