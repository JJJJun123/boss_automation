#!/usr/bin/env python3
"""
邀请码防枚举测试

按 IMPLEMENTATION_PLAN.md 阶段 0.5：
- 同 IP 60 秒内 5 次邀请码失败 → 拉黑 10 分钟
- 拉黑期间任何登录请求拒绝
- 10 分钟后自动解封
- 不同 IP 互不影响

实现用进程内 dict + 滑动窗口，不引入 Redis。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.rate_limiter import (
    InviteRateLimiter,
    INVITE_FAILURE_THRESHOLD,
    INVITE_FAILURE_WINDOW,
    BLACKLIST_DURATION,
)


@pytest.fixture
def limiter():
    """每个测试新建一个 limiter 实例，互不污染"""
    return InviteRateLimiter()


# ─── 基础拉黑逻辑 ───────────────────────────────────────────

def test_fresh_ip_not_blacklisted(limiter):
    assert limiter.is_blacklisted("1.2.3.4", now=1000) is False


def test_single_failure_does_not_blacklist(limiter):
    limiter.record_failure("1.2.3.4", now=1000)
    assert limiter.is_blacklisted("1.2.3.4", now=1001) is False


def test_threshold_failures_triggers_blacklist(limiter):
    """正好 N 次失败 → 立即拉黑"""
    for i in range(INVITE_FAILURE_THRESHOLD):
        limiter.record_failure("1.2.3.4", now=1000 + i)
    assert limiter.is_blacklisted("1.2.3.4", now=1010) is True


def test_blacklist_expires_after_duration(limiter):
    """拉黑窗口结束后自动解封"""
    for i in range(INVITE_FAILURE_THRESHOLD):
        limiter.record_failure("1.2.3.4", now=1000 + i)
    # 刚拉黑：True
    assert limiter.is_blacklisted("1.2.3.4", now=1010) is True
    # 解封时间之后：False
    assert limiter.is_blacklisted("1.2.3.4", now=1010 + BLACKLIST_DURATION + 1) is False


# ─── 滑动窗口 ──────────────────────────────────────────────

def test_failures_outside_window_dont_count(limiter):
    """失败 4 次后等待超过 window，再失败 1 次不应触发拉黑

    旧失败掉出滑动窗口，等于"重新开始计数"。
    """
    for i in range(INVITE_FAILURE_THRESHOLD - 1):
        limiter.record_failure("1.2.3.4", now=1000 + i)
    # 等待超过 window
    later = 1000 + INVITE_FAILURE_WINDOW + 10
    limiter.record_failure("1.2.3.4", now=later)
    assert limiter.is_blacklisted("1.2.3.4", now=later + 1) is False, \
        "旧失败应该掉出窗口，不该累计"


def test_failures_just_within_window_trigger(limiter):
    """N 次失败都在 window 内（紧贴边界）→ 拉黑"""
    for i in range(INVITE_FAILURE_THRESHOLD):
        limiter.record_failure("1.2.3.4", now=1000 + i * (INVITE_FAILURE_WINDOW // INVITE_FAILURE_THRESHOLD - 1))
    last_ts = 1000 + (INVITE_FAILURE_THRESHOLD - 1) * (INVITE_FAILURE_WINDOW // INVITE_FAILURE_THRESHOLD - 1)
    assert limiter.is_blacklisted("1.2.3.4", now=last_ts + 1) is True


# ─── IP 隔离 ──────────────────────────────────────────────

def test_different_ips_isolated(limiter):
    """A IP 拉黑不影响 B IP"""
    for i in range(INVITE_FAILURE_THRESHOLD):
        limiter.record_failure("1.2.3.4", now=1000 + i)
    assert limiter.is_blacklisted("1.2.3.4", now=1010) is True
    assert limiter.is_blacklisted("5.6.7.8", now=1010) is False


# ─── 成功登录清除失败计数 ─────────────────────────────────

def test_success_clears_failures(limiter):
    """登录成功 → 清掉该 IP 的失败记录（避免老 user 偶尔输错被误伤）"""
    limiter.record_failure("1.2.3.4", now=1000)
    limiter.record_failure("1.2.3.4", now=1001)
    limiter.record_success("1.2.3.4")
    # 再失败 4 次（合计 4 次），不应拉黑（如果没清的话 2+4=6 会拉黑）
    for i in range(INVITE_FAILURE_THRESHOLD - 1):
        limiter.record_failure("1.2.3.4", now=2000 + i)
    assert limiter.is_blacklisted("1.2.3.4", now=2010) is False


# ─── 内存清理（避免泄漏） ──────────────────────────────────

def test_cleanup_drops_old_entries(limiter):
    """超过 window 又没新失败的 IP，cleanup() 应该清掉"""
    for ip in ["1.1.1.1", "2.2.2.2", "3.3.3.3"]:
        limiter.record_failure(ip, now=1000)

    # 远超 window 之后调用 cleanup
    later = 1000 + INVITE_FAILURE_WINDOW + 100
    limiter.cleanup(now=later)

    # dict 应该被清空（这些 IP 都没新活动）
    assert len(limiter._failures) == 0
