#!/usr/bin/env python3
"""
Profile 管理 + 并发锁测试

按 IMPLEMENTATION_PLAN.md 阶段 1.2 + 1.3：
- 每 user_id 对应一个 UUID profile 目录
- per-profile threading.Lock：同 profile 同时只能 1 个 Chrome 持有
- 全局 Semaphore：全局最多 N 个 Chrome 并发
"""

import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def store(tmp_path):
    from utils.state_store import StateStore
    s = StateStore(db_path=str(tmp_path / "pm.db"))
    s.init_schema()
    return s


@pytest.fixture
def manager(tmp_path, store):
    from backend.profile_manager import ProfileManager
    return ProfileManager(
        profile_root=str(tmp_path / "profiles"),
        store=store,
        max_concurrent_chromes=2,  # 测试用小值
    )


def _make_user(store) -> str:
    code = store.create_invite()
    user_id, _ = store.consume_invite(code)
    return user_id


# ─── Profile 目录 ───────────────────────────────────────────

def test_get_profile_dir_returns_uuid_path(manager, store):
    user_id = _make_user(store)
    path = manager.get_profile_dir(user_id)
    assert path.startswith(manager.profile_root)
    # uuid 路径应包含合法 uuid 字符
    base = os.path.basename(path)
    assert len(base) >= 32, f"profile 目录名应是 UUID，实际 {base!r}"


def test_get_profile_dir_idempotent(manager, store):
    """同 user 多次取 profile 应返回同一目录"""
    user_id = _make_user(store)
    p1 = manager.get_profile_dir(user_id)
    p2 = manager.get_profile_dir(user_id)
    assert p1 == p2


def test_get_profile_dir_isolated_per_user(manager, store):
    """两个用户的 profile 目录必须不同"""
    user_a = _make_user(store)
    user_b = _make_user(store)
    assert manager.get_profile_dir(user_a) != manager.get_profile_dir(user_b)


def test_get_profile_dir_creates_directory(manager, store):
    """profile_dir 应实际存在于文件系统"""
    user_id = _make_user(store)
    path = manager.get_profile_dir(user_id)
    assert os.path.isdir(path)


def test_delete_profile_removes_dir_and_db_mapping(manager, store):
    """删 profile 后目录消失 + DB 映射消失"""
    user_id = _make_user(store)
    path = manager.get_profile_dir(user_id)
    assert os.path.isdir(path)
    manager.delete_profile(user_id)
    assert not os.path.exists(path)
    assert store.get_profile_by_user(user_id) is None


# ─── per-profile 互斥锁 ────────────────────────────────────

def test_acquire_profile_lock_returns_context_manager(manager, store):
    user_id = _make_user(store)
    # 应支持 with 语法
    with manager.acquire_profile_lock(user_id, timeout=1):
        pass  # 不抛异常即可


def test_profile_lock_blocks_concurrent_same_user(manager, store):
    """同 user 第二个 acquire 应该被阻塞，直到第一个释放"""
    user_id = _make_user(store)
    order = []

    def first():
        with manager.acquire_profile_lock(user_id, timeout=5):
            order.append("first_enter")
            time.sleep(0.1)
            order.append("first_exit")

    def second():
        time.sleep(0.02)  # 确保 first 先拿锁
        with manager.acquire_profile_lock(user_id, timeout=5):
            order.append("second_enter")

    t1 = threading.Thread(target=first)
    t2 = threading.Thread(target=second)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # second 必须在 first_exit 之后
    assert order == ["first_enter", "first_exit", "second_enter"], \
        f"second 应等 first 退出，实际顺序 {order}"


def test_profile_lock_different_users_no_block(manager, store):
    """不同 user 的锁应并发，不互相阻塞"""
    user_a = _make_user(store)
    user_b = _make_user(store)
    order = []

    def hold_a():
        with manager.acquire_profile_lock(user_a, timeout=5):
            order.append("a_enter")
            time.sleep(0.1)
            order.append("a_exit")

    def hold_b():
        time.sleep(0.02)
        with manager.acquire_profile_lock(user_b, timeout=5):
            order.append("b_enter")

    t1 = threading.Thread(target=hold_a)
    t2 = threading.Thread(target=hold_b)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # b 应在 a 还持有锁时进入（不同 profile 互不阻塞）
    assert order.index("b_enter") < order.index("a_exit"), \
        f"不同 user profile 不该互相阻塞，顺序 {order}"


def test_profile_lock_timeout_raises(manager, store):
    """超时未拿到锁应抛 TimeoutError"""
    from backend.profile_manager import ProfileLockTimeout
    user_id = _make_user(store)

    def hold():
        with manager.acquire_profile_lock(user_id, timeout=5):
            time.sleep(0.5)

    t = threading.Thread(target=hold)
    t.start()
    time.sleep(0.05)
    # 第二个 acquire 短超时应抛
    with pytest.raises(ProfileLockTimeout):
        with manager.acquire_profile_lock(user_id, timeout=0.1):
            pass
    t.join()


# ─── 全局 Chrome Semaphore ─────────────────────────────────

def test_global_chrome_slot_blocks_at_limit(manager, store):
    """全局上限 2 → 第 3 个 acquire 应阻塞"""
    user_a = _make_user(store)
    user_b = _make_user(store)
    user_c = _make_user(store)

    held = threading.Event()
    third_entered = threading.Event()

    def hold(uid, name):
        with manager.acquire_chrome_slot(timeout=5):
            held.set()
            if name == "c":
                third_entered.set()
            time.sleep(0.2)

    t1 = threading.Thread(target=hold, args=(user_a, "a"))
    t2 = threading.Thread(target=hold, args=(user_b, "b"))
    t3 = threading.Thread(target=hold, args=(user_c, "c"))
    t1.start()
    t2.start()
    time.sleep(0.05)  # 让 a, b 先抢到 slot
    t3.start()
    time.sleep(0.05)
    # c 在此瞬间应该还没拿到（被 semaphore 卡）
    assert not third_entered.is_set(), "全局上限 2 时第 3 个应被阻塞"
    t1.join()
    t2.join()
    t3.join()
    assert third_entered.is_set(), "前 2 个释放后 c 应能拿到"


def test_global_chrome_slot_timeout(manager, store):
    """全局上限满 + 短超时 → 抛 TimeoutError"""
    from backend.profile_manager import ChromeSlotTimeout

    def hold():
        with manager.acquire_chrome_slot(timeout=5):
            time.sleep(0.5)

    t1 = threading.Thread(target=hold)
    t2 = threading.Thread(target=hold)
    t1.start()
    t2.start()
    time.sleep(0.05)
    with pytest.raises(ChromeSlotTimeout):
        with manager.acquire_chrome_slot(timeout=0.05):
            pass
    t1.join()
    t2.join()


# ─── 组合：profile 锁 + 全局 slot ──────────────────────────

def test_combined_acquire_releases_both_on_exit(manager, store):
    """acquire_for_task 应同时拿 profile 锁 + chrome slot；退出后都释放"""
    user_id = _make_user(store)
    with manager.acquire_for_task(user_id, timeout=5):
        pass  # 进入即出，不抛异常即可
    # 出来后能再次 acquire
    with manager.acquire_for_task(user_id, timeout=5):
        pass


# ─── Codex round 1 修复回归 ────────────────────────────────

def test_delete_profile_rejects_if_active_task(manager, store):
    """Codex P1-1：用户有 active 任务时不允许删 profile"""
    from backend.profile_manager import ProfileBusyError
    user_id = _make_user(store)
    manager.get_profile_dir(user_id)  # 创建 profile mapping
    # 模拟 active task
    store.create_task(user_id, keyword="x", city="shanghai")
    with pytest.raises(ProfileBusyError):
        manager.delete_profile(user_id)


def test_lock_timeout_not_subclass_of_timeout_error(manager, store):
    """Codex P2-2：ProfileLockTimeout 不应被 asyncio.TimeoutError 误捕"""
    import asyncio
    from backend.profile_manager import ProfileLockTimeout, ChromeSlotTimeout
    assert not issubclass(ProfileLockTimeout, TimeoutError), \
        "ProfileLockTimeout 继承 TimeoutError 会被 asyncio 误捕"
    assert not issubclass(ChromeSlotTimeout, TimeoutError)
    # 但应当能被自己的基类 ProfileResourceBusy 捕获
    from backend.profile_manager import ProfileResourceBusy
    assert issubclass(ProfileLockTimeout, ProfileResourceBusy)


def test_delete_profile_path_containment_checked(manager, store, monkeypatch):
    """Codex P2-3：UUID 格式非法时不删任何目录（path traversal 防御）"""
    user_id = _make_user(store)
    manager.get_profile_dir(user_id)
    # 直接污染 DB：手动改 UUID 为非法格式
    with store._connect() as conn:
        conn.execute("UPDATE profiles SET uuid = ? WHERE user_id = ?",
                     ("../../etc", user_id))
        conn.commit()
    with pytest.raises(ValueError):
        manager.delete_profile(user_id)


def test_combined_releases_slot_on_profile_timeout(manager, store):
    """获取 profile 锁失败时，已拿的 chrome slot 必须释放（避免泄漏）"""
    user_id = _make_user(store)

    def hold():
        with manager.acquire_profile_lock(user_id, timeout=5):
            time.sleep(0.3)

    t = threading.Thread(target=hold)
    t.start()
    time.sleep(0.05)

    # acquire_for_task 拿到 chrome slot 但 profile 锁超时
    from backend.profile_manager import ProfileLockTimeout
    with pytest.raises(ProfileLockTimeout):
        with manager.acquire_for_task(user_id, timeout=0.05):
            pass

    # 关键：现在 chrome slot 应该全部空闲，能再起 2 个并发
    s1 = manager.acquire_chrome_slot(timeout=0.1)
    s1.__enter__()
    s2 = manager.acquire_chrome_slot(timeout=0.1)
    s2.__enter__()
    s1.__exit__(None, None, None)
    s2.__exit__(None, None, None)
    t.join()
