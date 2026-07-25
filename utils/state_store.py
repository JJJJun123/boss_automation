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
import json
import logging
import os
import secrets
import sqlite3
import time
import uuid

logger = logging.getLogger(__name__)
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


def resume_fingerprint(text: str) -> str:
    """生成只由简历正文决定的稳定 SHA-256 指纹。"""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


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
        """创建所有表 + 索引 + migration。多次调用幂等。"""
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")

            # Step 1: 主 schema（partial unique index 在最后）
            # 拆出 partial unique index 创建到 migration 之后，避免重复 active 阻塞
            schema_without_unique_index = _SCHEMA_SQL.replace(
                _PARTIAL_UNIQUE_INDEX_SQL, ""
            )
            conn.executescript(schema_without_unique_index)

            # Step 2: 旧 db 加 progress 列（如缺）
            self._migrate_tasks_table(conn)

            # Step 2.1: BYOK 老库迁移（users 补试用次数字段）
            self._migrate_users_table(conn)

            # Step 3: Codex round 2 P1-1：旧 db 若有重复 active task，先终结再建唯一索引
            # 同一用户多个 pending/running 状态 → 只保留最新一个，其余标 failed
            self._cleanup_duplicate_active_tasks(conn)

            # Step 4: 创建 partial unique index（此时无重复 → 不会失败）
            conn.executescript(_PARTIAL_UNIQUE_INDEX_SQL)
            conn.commit()

    def _migrate_tasks_table(self, conn) -> None:
        """老 db 不含 progress 列时补上；不抛错（已有列 ALTER 失败由 try 吞掉）"""
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
        if "progress" not in existing_cols:
            try:
                conn.execute("ALTER TABLE tasks ADD COLUMN progress INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # 并发 init 时其它进程已 ALTER 过

    def _migrate_users_table(self, conn) -> None:
        """老库 users 表补 trial_searches_used；并发初始化时保持幂等。"""
        existing_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "trial_searches_used" not in existing_cols:
            try:
                conn.execute(
                    "ALTER TABLE users ADD COLUMN trial_searches_used "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass

    def _cleanup_duplicate_active_tasks(self, conn) -> int:
        """Codex round 2 P1-1：旧 db 同一用户多个 pending/running 时先清理

        每用户保留最新的 active task，其余强制标记 failed（带迁移标记），
        让后续 partial unique index 创建不失败。返回清理条数。
        """
        rows = conn.execute(
            "SELECT user_id, task_id, created_at FROM tasks "
            "WHERE status IN ('pending', 'running') "
            "ORDER BY user_id, created_at DESC"
        ).fetchall()

        seen_users = set()
        stale_task_ids = []
        for row in rows:
            user_id = row["user_id"]
            if user_id in seen_users:
                stale_task_ids.append(row["task_id"])
            else:
                seen_users.add(user_id)

        if stale_task_ids:
            placeholders = ",".join("?" * len(stale_task_ids))
            conn.execute(
                f"UPDATE tasks SET status = 'failed', "
                f"result_json = '{{\"error\": \"abandoned_by_migration\"}}', "
                f"finished_at = ? WHERE task_id IN ({placeholders})",
                (time.time(), *stale_task_ids),
            )
        return len(stale_task_ids)

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

    # ─── 简历存储（按 user_id 隔离 + TTL 24h） ────────────

    def set_resume(self, user_id: str, resume_text: str, filename: str = "",
                   intentions: Optional[list] = None) -> None:
        """保存/更新用户简历文本 + 元数据。TTL 24h。

        简历正文绝不落日志（design.md F1）；这里只在 sqlite 里。
        每个 user_id 同时只能有一份简历，新上传覆盖旧的。
        """
        import json as _json
        now = time.time()
        intentions_json = _json.dumps(intentions or [], ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO resumes (user_id, resume_text, filename, intentions, "
                "created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "resume_text = excluded.resume_text, filename = excluded.filename, "
                "intentions = excluded.intentions, created_at = excluded.created_at, "
                "expires_at = excluded.expires_at",
                (user_id, resume_text, filename, intentions_json,
                 now, now + _TASK_TTL_SECONDS),
            )
            conn.commit()

    def get_resume(self, user_id: str) -> Optional[Dict[str, Any]]:
        """取该用户的简历；过期或不存在返回 None"""
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM resumes WHERE user_id = ?", (user_id,)
            ).fetchone()
        if not row or row["expires_at"] < now:
            return None
        import json as _json
        return {
            "resume_text": row["resume_text"],
            "filename": row["filename"],
            "intentions": _json.loads(row["intentions"] or "[]"),
            "created_at": row["created_at"],
        }

    def delete_resume(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM resumes WHERE user_id = ?", (user_id,))
            conn.commit()

    def update_resume_intentions(self, user_id: str, intentions: list) -> bool:
        """更新求职意向；user_id 简历不存在返回 False"""
        import json as _json
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE resumes SET intentions = ? WHERE user_id = ?",
                (_json.dumps(intentions, ensure_ascii=False), user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def cleanup_expired_resumes(self) -> int:
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM resumes WHERE expires_at < ?", (now,))
            conn.commit()
            return cur.rowcount

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

    # ─── 求职画像 ──────────────────────────────────────────

    def set_career_profile(self, user_id: str, profile_json: str,
                           resume_hash: str) -> None:
        """保存用户最新画像；更新时保留首次创建时间。"""
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO career_profiles "
                "(user_id, profile_json, resume_hash, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "profile_json = excluded.profile_json, "
                "resume_hash = excluded.resume_hash, "
                "updated_at = excluded.updated_at",
                (user_id, profile_json, resume_hash, now, now),
            )
            conn.commit()

    def get_career_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """读取解析后的最新画像；不存在或历史坏数据返回 None。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT profile_json, resume_hash, updated_at "
                "FROM career_profiles WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        try:
            profile = json.loads(row["profile_json"])
        except (TypeError, json.JSONDecodeError):
            logger.warning("忽略无法解析的求职画像：user_id=%s", user_id)
            return None
        if not isinstance(profile, dict):
            return None
        return {
            "profile": profile,
            "resume_hash": row["resume_hash"],
            "updated_at": row["updated_at"],
        }

    # ─── 岗位事实与分析缓存 ────────────────────────────────

    def upsert_job(self, job: Dict[str, Any]) -> None:
        """写入最新岗位事实；无 job_id 的列表噪声直接跳过。"""
        job_id = (job or {}).get("job_id")
        if not job_id:
            return

        now = time.time()
        jd = job.get("jd")
        if jd is None:
            jd = job.get("job_description", "")
        city = job.get("city")
        if city is None:
            city = job.get("location", "")

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs "
                "(job_id, title, company, salary, city, url, jd, first_seen, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(job_id) DO UPDATE SET "
                "title = excluded.title, company = excluded.company, "
                "salary = excluded.salary, city = excluded.city, "
                "url = excluded.url, jd = excluded.jd, last_seen = excluded.last_seen",
                (str(job_id), job.get("title", ""), job.get("company", ""),
                 job.get("salary", ""), city or "", job.get("url", ""),
                 jd or "", now, now),
            )
            conn.commit()

    def get_fresh_job(self, job_id: str,
                      max_age_seconds: float) -> Optional[Dict[str, Any]]:
        """返回仍在新鲜期内的岗位事实，过期或未知岗位返回 None。"""
        if not job_id:
            return None
        cutoff = time.time() - max(0, float(max_age_seconds))
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ? AND last_seen >= ?",
                (job_id, cutoff),
            ).fetchone()
        return dict(row) if row else None

    def set_cached_analysis(self, user_id: str, job_id: str,
                            resume_hash: str, analysis_json: Any) -> None:
        """按用户、岗位、简历版本保存完整分析结果。"""
        if isinstance(analysis_json, str):
            payload = analysis_json
        else:
            payload = json.dumps(analysis_json, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO job_analyses "
                "(user_id, job_id, resume_hash, analysis_json, created_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, job_id, resume_hash) DO UPDATE SET "
                "analysis_json = excluded.analysis_json, "
                "created_at = excluded.created_at",
                (user_id, job_id, resume_hash, payload, time.time()),
            )
            conn.commit()

    def get_cached_analysis(self, user_id: str, job_id: str,
                            resume_hash: str) -> Optional[Dict[str, Any]]:
        """读取完整分析 JSON；键不匹配或历史坏数据都视为缓存未命中。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT analysis_json FROM job_analyses "
                "WHERE user_id = ? AND job_id = ? AND resume_hash = ?",
                (user_id, job_id, resume_hash),
            ).fetchone()
        if not row:
            return None
        try:
            parsed = json.loads(row["analysis_json"])
            return parsed if isinstance(parsed, dict) else None
        except (TypeError, json.JSONDecodeError):
            logger.warning("忽略无法解析的岗位分析缓存：job_id=%s", job_id)
            return None

    # ─── BYOK API Key + 试用配额 ───────────────────────────

    def set_user_api_key(self, user_id: str, provider: str,
                         key_encrypted: str) -> None:
        """保存用户唯一的加密 API Key；更换 provider 时覆盖旧记录。"""
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO user_api_keys "
                "(user_id, provider, key_encrypted, created_at, last_verified_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "provider = excluded.provider, "
                "key_encrypted = excluded.key_encrypted, "
                "created_at = excluded.created_at, "
                "last_verified_at = excluded.last_verified_at",
                (user_id, provider, key_encrypted, now, now),
            )
            conn.commit()

    def get_user_api_key(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT provider, key_encrypted, created_at, last_verified_at "
                "FROM user_api_keys WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def delete_user_api_key(self, user_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM user_api_keys WHERE user_id = ?", (user_id,)
            )
            conn.commit()
            return cur.rowcount > 0

    def get_trial_usage(self, user_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT trial_searches_used FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row["trial_searches_used"]) if row else 0

    def increment_trial_usage(self, user_id: str) -> int:
        """成功的站方 Key 任务计数 +1，并返回最新值。"""
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET trial_searches_used = trial_searches_used + 1 "
                "WHERE user_id = ?",
                (user_id,),
            )
            row = conn.execute(
                "SELECT trial_searches_used FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            conn.commit()
        return int(row["trial_searches_used"]) if row else 0

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

    def delete_profile_mapping(self, user_id: str) -> None:
        """删除 user_id 的 profile 映射记录（不删盘上文件）"""
        with self._connect() as conn:
            conn.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
            conn.commit()

    def touch_profile(self, user_id: str) -> None:
        """更新 last_access_at，用于 30 天 inactive 自动清理判定"""
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "UPDATE profiles SET last_access_at = ? WHERE user_id = ?", (now, user_id)
            )
            conn.commit()

    # ─── Task 记录 ────────────────────────────────────────

    def terminate_orphan_active_tasks(self) -> int:
        """服务启动时清理孤儿任务：把所有 pending/running 标为 failed

        服务重启后任务线程全部死亡，但 DB 状态残留 running，会被
        partial unique index 永久拦住该用户的新任务（前端表现为
        "已有任务正在运行中" 409）。应在 create_app 启动时调用一次。

        返回：int - 清理的任务数
        """
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = 'failed', "
                "result_json = '{\"error\": \"server_restarted\"}', "
                "finished_at = ? WHERE status IN ('pending', 'running')",
                (now,),
            )
            conn.commit()
            if cur.rowcount:
                logger.warning(f"启动清理：{cur.rowcount} 个孤儿任务标为 failed")
            return cur.rowcount

    def create_task(self, user_id: str, keyword: str, city: str) -> str:
        """创建一个 task 记录

        受 partial unique index `idx_tasks_one_active_per_user` 保护：
        每用户同时只能有一个 pending/running 任务，并发 INSERT 第二个
        会抛 IntegrityError。调用方应捕获并返 409。

        返回：str - task_id
        异常：sqlite3.IntegrityError - 用户已有 active 任务
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

    def set_task_status(self, task_id: str, status: str,
                        progress: Optional[int] = None) -> bool:
        """更新任务状态（不带结果 JSON）

        Codex P1-3：仅当当前状态是 pending/running 才能改，防止
        用户已 cancel 后被 worker 改回 running 或 success（状态覆盖竞态）。
        返回：bool - True=更新成功，False=已是终态被拒绝
        """
        with self._connect() as conn:
            if progress is not None:
                cur = conn.execute(
                    "UPDATE tasks SET status = ?, progress = ? "
                    "WHERE task_id = ? AND status IN ('pending', 'running')",
                    (status, progress, task_id),
                )
            else:
                cur = conn.execute(
                    "UPDATE tasks SET status = ? "
                    "WHERE task_id = ? AND status IN ('pending', 'running')",
                    (status, task_id),
                )
            conn.commit()
            return cur.rowcount > 0

    def get_user_active_task(self, user_id: str) -> Optional[Dict[str, Any]]:
        """取该用户当前 pending/running 任务（最多 1 个，用于并发互斥）"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? "
                "AND status IN ('pending', 'running') "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_user_tasks(self, user_id: str, limit: int = 10) -> list:
        """取该用户最近 N 个任务（按 created_at 倒序）"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_completed_task(self, user_id: str) -> Optional[Dict[str, Any]]:
        """取该用户最近一个有结果的任务（success / requires_resume）

        Codex P2-2：fallback "取最新任务" 会被 cancelled / failed 遮住更早成功。
        前端不传 task_id 时该方法只返回真正有 result_json 的。
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? "
                "AND status IN ('success', 'requires_resume') "
                "AND result_json IS NOT NULL "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def cancel_task(self, task_id: str, user_id: str) -> bool:
        """用户主动取消任务；只 pending/running 状态可取消

        返回：bool - True=已取消，False=任务不存在或终态
        """
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = 'cancelled', finished_at = ? "
                "WHERE task_id = ? AND user_id = ? "
                "AND status IN ('pending', 'running')",
                (time.time(), task_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def set_task_result(self, task_id: str, status: str, result_json: str) -> bool:
        """写入终态 + 结果

        Codex P1-3：仅当 pending/running 状态才能写入终态，防止覆盖
        cancelled。Codex P2-1：写终态时 progress=100 统一。

        返回：bool - True=写入成功，False=已是终态被拒绝
        """
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status = ?, result_json = ?, finished_at = ?, progress = 100 "
                "WHERE task_id = ? AND status IN ('pending', 'running')",
                (status, result_json, now, task_id),
            )
            conn.commit()
            return cur.rowcount > 0

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
    last_seen_at REAL NOT NULL,
    trial_searches_used INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_api_keys (
    user_id          TEXT PRIMARY KEY,
    provider         TEXT NOT NULL,
    key_encrypted    TEXT NOT NULL,
    created_at       REAL NOT NULL,
    last_verified_at REAL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
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
    progress     INTEGER DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS resumes (
    user_id      TEXT PRIMARY KEY,
    resume_text  TEXT NOT NULL,
    filename     TEXT,
    intentions   TEXT,
    created_at   REAL NOT NULL,
    expires_at   REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_resumes_expires ON resumes(expires_at);

CREATE TABLE IF NOT EXISTS career_profiles (
    user_id      TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL,
    resume_hash  TEXT,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id     TEXT PRIMARY KEY,
    title      TEXT,
    company    TEXT,
    salary     TEXT,
    city       TEXT,
    url        TEXT,
    jd         TEXT,
    first_seen REAL NOT NULL,
    last_seen  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen);

CREATE TABLE IF NOT EXISTS job_analyses (
    user_id      TEXT NOT NULL,
    job_id       TEXT NOT NULL,
    resume_hash  TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    created_at   REAL NOT NULL,
    PRIMARY KEY (user_id, job_id, resume_hash)
);
CREATE INDEX IF NOT EXISTS idx_job_analyses_created ON job_analyses(created_at);
"""

# Codex P1-2：partial unique index 保证每用户最多 1 个 active task
# 拆出来在 _cleanup_duplicate_active_tasks 之后才创建，避免旧 db 重复 active 阻塞迁移
_PARTIAL_UNIQUE_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_one_active_per_user
    ON tasks(user_id) WHERE status IN ('pending', 'running');
"""
