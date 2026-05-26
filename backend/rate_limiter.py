#!/usr/bin/env python3
"""
邀请码防枚举 — IP 滑动窗口拉黑

按 IMPLEMENTATION_PLAN.md 阶段 0.5：
- 同 IP 60 秒内 5 次邀请码失败 → 拉黑 10 分钟
- 拉黑期间任何登录请求拒绝
- 滑动窗口（不是固定窗口）：失败时间戳列表 + 每次访问清理 60 秒前的

实现选择（详见 docs/IMPLEMENTATION_PLAN.md TD-未编号）：
- 进程内 dict + 滑动窗口（不引入 Redis）
- 单 worker Flask 够用；重启清空可接受（攻击者重启窗口最多得到 5 次额度）
- 所有 now 参数允许注入便于测试

线程安全：用 threading.Lock 保护 _failures / _blacklist 字典写入。
Flask + SocketIO 在多线程环境下并发请求会触发竞态。
"""

import threading
import time
from collections import deque
from typing import Dict, Deque, Optional


INVITE_FAILURE_THRESHOLD = 5      # 触发拉黑的失败次数
INVITE_FAILURE_WINDOW = 60        # 滑动窗口大小（秒）
BLACKLIST_DURATION = 600          # 拉黑时长（秒）= 10 分钟


class InviteRateLimiter:
    """邀请码失败次数 IP 维度限速

    用法：
        limiter = InviteRateLimiter()

        # 检查
        if limiter.is_blacklisted(ip):
            return 403, "IP 暂时被锁，请稍后再试"

        # 失败时
        if not store.consume_invite(code):
            limiter.record_failure(ip)
            return 401

        # 成功时
        limiter.record_success(ip)
        return 200
    """

    def __init__(self):
        # {ip: deque[失败时间戳]}，deque 自动按时间序
        self._failures: Dict[str, Deque[float]] = {}
        # {ip: 解封时间戳}
        self._blacklist: Dict[str, float] = {}
        self._lock = threading.Lock()

    # ─── 公开 API ────────────────────────────────────────

    def is_blacklisted(self, ip: str, now: Optional[float] = None) -> bool:
        """该 IP 是否在拉黑期内

        参数：
            ip  - 客户端 IP
            now - 当前时间戳（测试可注入；生产传 None 用 time.time()）
        返回：bool
        """
        now = now if now is not None else time.time()
        with self._lock:
            unblock_at = self._blacklist.get(ip)
            if unblock_at is None:
                return False
            if now >= unblock_at:
                # 解封时间到，自动清掉
                del self._blacklist[ip]
                return False
            return True

    def record_failure(self, ip: str, now: Optional[float] = None) -> None:
        """记录一次邀请码失败；累计达阈值自动拉黑"""
        now = now if now is not None else time.time()
        with self._lock:
            dq = self._failures.setdefault(ip, deque())
            # 清掉窗口外的旧时间戳（滑动窗口核心）
            cutoff = now - INVITE_FAILURE_WINDOW
            while dq and dq[0] < cutoff:
                dq.popleft()
            dq.append(now)

            if len(dq) >= INVITE_FAILURE_THRESHOLD:
                # 拉黑：解封时间 = 现在 + 10 分钟
                self._blacklist[ip] = now + BLACKLIST_DURATION
                # 拉黑后清失败记录，避免 deque 无限增长
                del self._failures[ip]

    def record_success(self, ip: str) -> None:
        """登录成功 → 清掉该 IP 的失败记录

        避免老用户偶尔输错几次邀请码被误伤拉黑。
        """
        with self._lock:
            self._failures.pop(ip, None)

    def cleanup(self, now: Optional[float] = None) -> int:
        """清理超过 window 且无新活动的 IP 失败记录 + 已解封的黑名单

        建议每分钟跑一次（在 backend/app.py 的后台 worker 里）。
        返回：清理的条目总数（含 _failures 和 _blacklist）
        """
        now = now if now is not None else time.time()
        cutoff = now - INVITE_FAILURE_WINDOW
        cleaned = 0
        with self._lock:
            # 清掉所有失败队列里旧时间戳；空 deque 删 key
            stale_ips = []
            for ip, dq in self._failures.items():
                while dq and dq[0] < cutoff:
                    dq.popleft()
                if not dq:
                    stale_ips.append(ip)
            for ip in stale_ips:
                del self._failures[ip]
                cleaned += 1

            # 清掉过期黑名单
            expired = [ip for ip, unblock_at in self._blacklist.items() if now >= unblock_at]
            for ip in expired:
                del self._blacklist[ip]
                cleaned += 1
        return cleaned


# 全局单例（供 backend/app.py 复用）
invite_limiter = InviteRateLimiter()
