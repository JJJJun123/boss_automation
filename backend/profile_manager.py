#!/usr/bin/env python3
"""
Chrome profile 管理 + 并发互斥锁

按 IMPLEMENTATION_PLAN.md 阶段 1.2 + 1.3：
- 每 user_id → 服务端 UUID profile 目录，按 store.profiles 表映射
- per-profile threading.Lock：同 user_id 任务串行（Chrome 同 profile 不能并发持有）
- 全局 Semaphore：全局并发 Chrome 数限 N（VPS 内存上限保护）
- ProfileLockTimeout / ChromeSlotTimeout：拿不到时抛异常便于上层降级
"""

import logging
import os
import shutil
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator


logger = logging.getLogger(__name__)


class ProfileResourceBusy(Exception):
    """profile 资源竞争 / 资源忙 — 独立异常体系，**不继承** TimeoutError

    Codex P2-2：原继承 TimeoutError 会被 asyncio.TimeoutError 误捕
    （Python 3.11+ asyncio.TimeoutError is TimeoutError）。
    """


class ProfileLockTimeout(ProfileResourceBusy):
    """超时未拿到 per-profile 锁"""


class ChromeSlotTimeout(ProfileResourceBusy):
    """超时未拿到全局 Chrome 并发槽"""


class ProfileBusyError(ProfileResourceBusy):
    """用户有 active 任务时尝试删除 profile 等冲突场景"""


class ProfileManager:
    """管理用户 Chrome profile 目录 + 并发锁

    线程模型：
    - per-profile dict 用 _dict_lock 保护
    - 单个 profile lock 用 threading.Lock；acquire(timeout) 拿不到时抛 ProfileLockTimeout
    - 全局 chrome 并发用 threading.BoundedSemaphore；不可超额 release
    """

    # UUID 格式：32 个 hex（带或不带 dash 都接受）
    _UUID_PATTERN = __import__("re").compile(
        r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
    )

    def __init__(self, profile_root: str, store, max_concurrent_chromes: int = 2):
        """
        参数：
            profile_root - 所有用户 profile 的父目录（生产用 ~/Library/.../browser_profile）
            store - StateStore 实例，用于 user_id↔uuid 映射持久化
            max_concurrent_chromes - 全局并发上限（4GB VPS 实测 2 个安全；8GB 可 3-4）
        """
        # P2-3：根目录 resolve 后存，删除时校验路径 containment 防漏删
        self.profile_root = str(Path(profile_root).expanduser().resolve())
        self.store = store
        self.max_concurrent = max_concurrent_chromes

        # per-profile lock dict（懒创建）
        self._profile_locks: Dict[str, threading.Lock] = {}
        self._dict_lock = threading.Lock()

        # 全局 Chrome 并发 semaphore（bounded：防止误 release 超额）
        self._chrome_sem = threading.BoundedSemaphore(value=max_concurrent_chromes)

        Path(self.profile_root).mkdir(parents=True, exist_ok=True)

    # ─── Profile 目录 ──────────────────────────────────────

    def _resolve_profile_path(self, uuid: str) -> Path:
        """统一的 UUID 校验 + 路径 containment 检查（Codex P2-1）

        get_profile_dir 与 delete_profile 都用同一个 helper，确保任意时刻
        DB 污染都被同样防住。
        """
        if not self._UUID_PATTERN.match(uuid):
            raise ValueError(f"profile uuid 格式非法: {uuid!r}")
        path = (Path(self.profile_root) / uuid).resolve()
        try:
            path.relative_to(self.profile_root)
        except ValueError:
            raise ValueError(f"profile 路径越界: {path}")
        return path

    def get_profile_dir(self, user_id: str) -> str:
        """取该用户的 profile 目录绝对路径；不存在则创建

        UUID 由 store.get_or_create_profile 服务端生成；前端永远拿不到。
        校验路径 containment 防 DB 污染时越界创建。
        """
        uuid = self.store.get_or_create_profile(user_id)
        path = self._resolve_profile_path(uuid)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def delete_profile(self, user_id: str) -> None:
        """删用户的 profile 目录 + 解除 DB 映射

        Codex P1-1：先检查 active task；任务跑中不允许删（profile 被占用，
        删了会让运行中的 Chrome profile 损坏）。
        Codex P1-1：删 + 锁互斥（避免 worker 启动 chrome 时同时另一线程 rmtree）。
        Codex P2-3：路径 containment 校验，避免 DB 污染时 rmtree 失控目录。
        Codex P2-1：经 store.delete_profile_mapping API 不绕过持久化边界。
        """
        # 检查 active task — 任务跑中拒绝删除
        active = self.store.get_user_active_task(user_id)
        if active:
            raise ProfileBusyError(
                f"用户有正在运行的任务 task_id={active['task_id']}，不能删除 profile"
            )

        profile = self.store.get_profile_by_user(user_id)
        if not profile:
            return

        uuid = profile["uuid"]
        # 走统一 helper（同时做 UUID 格式 + 路径 containment 校验）
        resolved = self._resolve_profile_path(uuid)

        # 拿 profile 锁，等运行中的 chrome 退出
        with self.acquire_profile_lock(user_id, timeout=10):
            if resolved.is_dir():
                # Codex P2-2：rmtree 失败不静默；保留 DB mapping 让上层报错
                shutil.rmtree(resolved)  # 抛 OSError 时不进 delete_mapping
            self.store.delete_profile_mapping(user_id)

    # ─── per-profile 互斥锁 ────────────────────────────────

    def _get_profile_lock(self, user_id: str) -> threading.Lock:
        """懒创建 lock（同 user_id 每次返同一个 Lock 对象）"""
        with self._dict_lock:
            lock = self._profile_locks.get(user_id)
            if lock is None:
                lock = threading.Lock()
                self._profile_locks[user_id] = lock
            return lock

    @contextmanager
    def acquire_profile_lock(self, user_id: str, timeout: float = 30.0) -> Iterator[None]:
        """获取该用户的 profile 互斥锁。with 退出自动释放。

        超时未拿到 → ProfileLockTimeout。
        """
        lock = self._get_profile_lock(user_id)
        acquired = lock.acquire(timeout=timeout)
        if not acquired:
            raise ProfileLockTimeout(f"获取 profile 锁超时 user_id={user_id}")
        try:
            yield
        finally:
            lock.release()

    # ─── 全局 Chrome 并发 slot ─────────────────────────────

    @contextmanager
    def acquire_chrome_slot(self, timeout: float = 30.0) -> Iterator[None]:
        """获取一个全局 Chrome 并发槽。with 退出自动释放。

        超时未拿到 → ChromeSlotTimeout。
        """
        acquired = self._chrome_sem.acquire(timeout=timeout)
        if not acquired:
            raise ChromeSlotTimeout("获取 Chrome 并发槽超时")
        try:
            yield
        finally:
            self._chrome_sem.release()

    # ─── 组合：搜索任务用 ─────────────────────────────────

    @contextmanager
    def acquire_for_task(self, user_id: str, timeout: float = 30.0) -> Iterator[str]:
        """搜索任务前调：同时拿 chrome slot + profile 锁，返回 profile_dir

        资源回收顺序：profile 锁先释放，再释放 chrome slot（嵌套 with）。
        任一环节超时都会清理已拿的资源（避免泄漏）。

        参数：
            user_id - 当前用户
            timeout - 每个资源的等待上限（总等待最多 2× timeout）
        返回：str - profile 目录绝对路径
        """
        # 先拿 chrome slot（按全局可用判定快速失败）
        with self.acquire_chrome_slot(timeout=timeout):
            # 再拿 profile 锁；超时时退出 with 会自动 release chrome slot
            with self.acquire_profile_lock(user_id, timeout=timeout):
                yield self.get_profile_dir(user_id)
