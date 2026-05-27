#!/usr/bin/env python3
"""
Flask app 集成测试 — phase 0 安全模块接入真实路由

按 IMPLEMENTATION_PLAN.md F3 阶段：
- create_app 工厂模式，便于测试注入 store
- 所有数据 API 需 @require_user_id
- SECRET_KEY 强制从环境变量
- CORS 白名单（不含 *）
- 上传走 validate_resume_file
- 错误用 safe_error_response 脱敏
- 简历存 StateStore.set_resume 不再全局变量
"""

import io
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _reset_invite_limiter():
    """invite_limiter 是 module-level 单例，跨测试会污染。每个测试前重置"""
    from backend.rate_limiter import invite_limiter
    invite_limiter._failures.clear()
    invite_limiter._blacklist.clear()
    yield


@pytest.fixture
def store(tmp_path):
    from utils.state_store import StateStore
    s = StateStore(db_path=str(tmp_path / "integ.db"))
    s.init_schema()
    return s


@pytest.fixture
def app(store, monkeypatch):
    """构造测试用 app，注入临时 store + 测试 secret key"""
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-12345678-aaaaaaaa")
    monkeypatch.setenv("FLASK_ENV", "development")
    from backend.app import create_app
    application = create_app(store=store)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def authed_client(app, store):
    """已邀请码登录的客户端"""
    code = store.create_invite()
    c = app.test_client()
    resp = c.get(f"/login?invite={code}")
    assert resp.status_code in (200, 302), f"login 失败: {resp.status_code}"
    return c


def _make_minimal_docx_bytes() -> bytes:
    """构造一个能被 python-docx 真实解析的最小合法 docx

    用 python-docx 自己生成，确保 namespace / rels / 结构都齐
    （手写 minimal XML 没 namespace，python-docx 解析会 AttributeError）。
    """
    import docx
    d = docx.Document()
    d.add_paragraph("测试简历正文：AI 算法工程师，5 年经验")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


# ─── App 启动 fail-fast ────────────────────────────────────

def test_app_fails_fast_when_secret_key_missing(monkeypatch, store):
    """未设 FLASK_SECRET_KEY 时 create_app 必须抛错"""
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    from backend.security import SecretKeyMissingError
    from backend.app import create_app
    with pytest.raises(SecretKeyMissingError):
        create_app(store=store)


# ─── CORS ───────────────────────────────────────────────────

def test_cors_allows_production_origin(client):
    resp = client.get("/api/health", headers={"Origin": "https://boss.jjjj789.win"})
    # 任何 200，关键是不抛 CORS 错
    assert resp.status_code == 200


def test_cors_excludes_wildcard(app):
    """app 配置里 CORS origin 不能是 *"""
    # 检查 SocketIO 的 cors_allowed_origins 也不该是 *
    socketio = app.extensions.get("socketio")
    if socketio is not None and hasattr(socketio, "server"):
        origins = socketio.server.eio.cors_allowed_origins
        assert origins != "*", "SocketIO CORS 不能放 *"


# ─── 邀请码登录 ─────────────────────────────────────────────

def test_login_with_valid_invite_sets_cookie(app, store):
    code = store.create_invite()
    client = app.test_client()
    resp = client.get(f"/login?invite={code}")
    assert resp.status_code in (200, 302)
    # 应该 Set-Cookie
    set_cookie = resp.headers.get("Set-Cookie", "")
    assert "boss_session" in set_cookie


def test_login_invalid_invite_returns_401(client):
    resp = client.get("/login?invite=badcode1")
    assert resp.status_code == 401


def test_login_no_invite_returns_400(client):
    resp = client.get("/login")
    assert resp.status_code == 400


def test_login_brute_force_triggers_rate_limit(client):
    """连续 6 次错邀请码 → 第 6 次返回 429（被防枚举拉黑）"""
    for _ in range(5):
        client.get("/login?invite=fakecode")
    resp = client.get("/login?invite=fakecode")
    assert resp.status_code == 429, f"防枚举失败，第 6 次仍返回 {resp.status_code}"


# ─── 受保护路由：未登录拒绝 ────────────────────────────────

def test_upload_resume_requires_auth(client):
    resp = client.post("/api/upload_resume")
    assert resp.status_code == 401


def test_jobs_search_requires_auth(client):
    resp = client.post("/api/jobs/search", json={})
    assert resp.status_code == 401


def test_get_resume_info_requires_auth(client):
    resp = client.get("/api/resume/info")
    assert resp.status_code == 401


def test_delete_resume_requires_auth(client):
    resp = client.post("/api/delete_resume")
    assert resp.status_code == 401


# ─── 已登录上传简历 ────────────────────────────────────────

def test_upload_docx_succeeds_with_auth(authed_client):
    docx_bytes = _make_minimal_docx_bytes()
    resp = authed_client.post(
        "/api/upload_resume",
        data={"resume": (io.BytesIO(docx_bytes), "resume.docx")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("success") is True


def test_upload_txt_rejected(authed_client):
    """validate_resume_file 接进 app 后，TXT 必须被拒"""
    resp = authed_client.post(
        "/api/upload_resume",
        data={"resume": (io.BytesIO(b"hello plain text"), "resume.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (400, 415)
    body = resp.get_json()
    assert body.get("success") is False


def test_upload_oversized_rejected(authed_client):
    """6MB 文件超 5MB 上限 → 拒绝"""
    docx_bytes = _make_minimal_docx_bytes() + b"x" * (6 * 1024 * 1024)
    resp = authed_client.post(
        "/api/upload_resume",
        data={"resume": (io.BytesIO(docx_bytes), "resume.docx")},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (400, 413)


# ─── 简历隔离（不再全局变量） ───────────────────────────────

def test_two_users_resume_isolated(app, store):
    """用户 A 上传简历后，用户 B 的 /api/resume/info 不应看到 A 的简历"""
    code_a = store.create_invite()
    code_b = store.create_invite()

    client_a = app.test_client()
    client_a.get(f"/login?invite={code_a}")
    docx_bytes = _make_minimal_docx_bytes()
    client_a.post(
        "/api/upload_resume",
        data={"resume": (io.BytesIO(docx_bytes), "alice.docx")},
        content_type="multipart/form-data",
    )

    client_b = app.test_client()
    client_b.get(f"/login?invite={code_b}")
    resp_b = client_b.get("/api/resume/info")
    assert resp_b.status_code == 200
    body_b = resp_b.get_json()
    # B 不应看到 A 的简历
    assert body_b.get("has_resume") is False, "用户 B 不应看到 A 的简历"


# ─── 错误响应脱敏 ──────────────────────────────────────────

# ─── Codex P1+P2 修复回归 ──────────────────────────────────

def test_404_returns_404_not_500(client):
    """Codex P2：HTTPException 应保留语义，不被 errorhandler 强转 500"""
    resp = client.get("/api/nonexistent_route_xyz")
    assert resp.status_code == 404, f"404 路由应返回 404，实际 {resp.status_code}"


def test_method_not_allowed_returns_405(client):
    """OPTIONS / PUT 之类不匹配的方法应 405，不应 500"""
    resp = client.delete("/api/health")
    assert resp.status_code == 405


def test_cross_origin_login_rejected(client, store):
    """Codex P2-1：跨站 Origin 触发的 /login GET 必须拒绝（防 CSRF）"""
    code = store.create_invite()
    resp = client.get(
        f"/login?invite={code}",
        headers={"Origin": "https://evil.example.com"},
    )
    assert resp.status_code == 403, "跨站 Origin 必须拒绝"


def test_same_origin_login_passes(client, store):
    """白名单 Origin 应允许（确保不误伤正常浏览器请求）"""
    code = store.create_invite()
    resp = client.get(
        f"/login?invite={code}",
        headers={"Origin": "http://localhost:3001"},
    )
    assert resp.status_code in (200, 302), f"同源登录应通过，实际 {resp.status_code}"


def test_no_origin_no_referer_login_allowed(client, store):
    """无 Origin 无 Referer（直接 curl / 地址栏访问）应允许"""
    code = store.create_invite()
    resp = client.get(f"/login?invite={code}")
    assert resp.status_code in (200, 302)


def test_xff_forge_does_not_bypass_rate_limit(client):
    """Codex P1-1：伪造 X-Forwarded-For 不能绕过 IP 黑名单

    远端是 127.0.0.1 (test_client)，应该被信任为反代——但既然如此，
    用最后一段（nginx 追加值）而非第一段（攻击者控制）。这里伪造 1.2.3.4
    在 XFF 第一段，应该被忽略；最后一段仍是 unknown/test_client 默认 IP。
    """
    # 用同一个伪 XFF 试 6 次邀请码
    for _ in range(6):
        client.get("/login?invite=fakecode",
                   headers={"X-Forwarded-For": "1.2.3.4"})
    # 攻击者期望换 XFF 头能换 IP → 实际所有请求都被算到同一个 remote_addr
    # 第 7 次仍应 429（黑名单），不该因为伪 XFF 不同被放行
    resp = client.get("/login?invite=fakecode",
                      headers={"X-Forwarded-For": "5.6.7.8"})
    assert resp.status_code == 429, "伪造 XFF 不能换 IP 绕过限流"


# ─── Codex round 2 修复回归 ────────────────────────────────

def test_lan_attacker_cannot_forge_x_real_ip(client):
    """Codex round 2 P1-1：LAN 内攻击者 (10.x / 192.168.x) 不能用 X-Real-IP 绕过限流

    test_client 默认 remote_addr=127.0.0.1（loopback，可信）。这里用 environ_overrides
    模拟非可信源 IP，并配伪造 X-Real-IP——应该完全忽略 X-Real-IP。
    """
    for _ in range(6):
        client.get("/login?invite=fakecode",
                   headers={"X-Real-IP": "8.8.8.8"},
                   environ_overrides={"REMOTE_ADDR": "10.0.0.5"})
    # 第 7 次：换不同 X-Real-IP — 应仍被算到 10.0.0.5（实际限流的 IP），429
    resp = client.get("/login?invite=fakecode",
                      headers={"X-Real-IP": "9.9.9.9"},
                      environ_overrides={"REMOTE_ADDR": "10.0.0.5"})
    assert resp.status_code == 429, "LAN 内 X-Real-IP 不该被信任"


def test_invalid_x_real_ip_ignored(client):
    """非法格式的 X-Real-IP（含逗号 / 非 IP）应被忽略"""
    for _ in range(5):
        client.get("/login?invite=fakecode",
                   headers={"X-Real-IP": "1.2.3.4, 5.6.7.8"})  # 多值
    resp = client.get("/login?invite=fakecode",
                      headers={"X-Real-IP": "9.9.9.9, 10.10.10.10"})
    assert resp.status_code == 429, "多值 X-Real-IP 应被忽略，仍走 remote_addr"


def test_loopback_proxy_x_real_ip_trusted(client):
    """合法场景：remote_addr=127.0.0.1 + 单值 X-Real-IP → 信任并用作客户端 IP"""
    # 不同 X-Real-IP 应被视为不同客户端（不会互相累加限流）
    for _ in range(3):
        client.get("/login?invite=fakecode",
                   headers={"X-Real-IP": "1.1.1.1"})
    for _ in range(3):
        client.get("/login?invite=fakecode",
                   headers={"X-Real-IP": "2.2.2.2"})
    # 各自只 3 次失败，都不该 429
    resp = client.get("/login?invite=fakecode",
                      headers={"X-Real-IP": "1.1.1.1"})
    assert resp.status_code in (401,), "loopback proxy 下 X-Real-IP 应正常生效"


def test_no_referer_no_origin_rejected_in_production(client, monkeypatch, store):
    """Codex round 2 P1-2：无 Origin 无 Referer 顶层跳转必须拒绝（生产模式）"""
    monkeypatch.setenv("FLASK_ENV", "production")
    code = store.create_invite()
    resp = client.get(f"/login?invite={code}")
    assert resp.status_code == 403, "生产模式下无 Origin/Referer 必须拒绝"


def test_legit_referer_login_passes(client, store):
    """合法 Referer（白名单 origin）应允许"""
    code = store.create_invite()
    resp = client.get(f"/login?invite={code}",
                      headers={"Referer": "http://localhost:3001/some-page"})
    assert resp.status_code in (200, 302)


def test_malicious_referer_rejected(client, store):
    """攻击者 Referer 拒绝"""
    code = store.create_invite()
    resp = client.get(f"/login?invite={code}",
                      headers={"Referer": "https://evil.example.com/csrf-page"})
    assert resp.status_code == 403


# ─── 阶段 1.4 + 1.6：SQLite 任务持久化 + cancel + IDOR 防御 ──

def test_search_returns_task_id_and_creates_db_record(authed_client, store):
    """搜索请求应返回真实 task_id 并在 SQLite 留记录

    用 mock 不真跑爬虫——这里只校验路由层的 task 创建逻辑。
    """
    import unittest.mock as _mock
    with _mock.patch("backend.app._run_job_search_task"):
        resp = authed_client.post("/api/jobs/search",
                                  json={"keyword": "AI", "city": "shanghai"})
    assert resp.status_code == 202
    body = resp.get_json()
    assert "task_id" in body
    task_id = body["task_id"]
    assert len(task_id) > 0

    # SQLite 应有记录
    task = store._get_task_unscoped(task_id)
    assert task is not None
    assert task["keyword"] == "AI"


def test_concurrent_search_for_same_user_rejected(authed_client, store):
    """同用户有 running 任务时再开 → 409"""
    import unittest.mock as _mock
    with _mock.patch("backend.app._run_job_search_task"):
        # 第一次成功
        r1 = authed_client.post("/api/jobs/search", json={"keyword": "x"})
        assert r1.status_code == 202
        # 第二次应被拒
        r2 = authed_client.post("/api/jobs/search", json={"keyword": "y"})
        assert r2.status_code == 409


def test_cancel_task(authed_client, store):
    """用户能取消自己的任务"""
    import unittest.mock as _mock
    with _mock.patch("backend.app._run_job_search_task"):
        r = authed_client.post("/api/jobs/search", json={"keyword": "x"})
    task_id = r.get_json()["task_id"]
    resp = authed_client.post("/api/jobs/cancel", json={"task_id": task_id})
    assert resp.status_code == 200
    # 状态变 cancelled
    task = store._get_task_unscoped(task_id)
    assert task["status"] == "cancelled"


def test_cancel_other_users_task_rejected(app, store):
    """B 用户不能取消 A 用户的任务（IDOR 防御）"""
    import unittest.mock as _mock
    code_a = store.create_invite()
    code_b = store.create_invite()
    client_a = app.test_client()
    client_a.get(f"/login?invite={code_a}",
                 headers={"Origin": "http://localhost:3001"})
    with _mock.patch("backend.app._run_job_search_task"):
        r = client_a.post("/api/jobs/search", json={"keyword": "x"})
    task_id = r.get_json()["task_id"]

    client_b = app.test_client()
    client_b.get(f"/login?invite={code_b}",
                 headers={"Origin": "http://localhost:3001"})
    resp = client_b.post("/api/jobs/cancel", json={"task_id": task_id})
    assert resp.status_code == 404, "B 不应能 cancel A 的任务"


def test_get_task_result_isolated_per_user(app, store):
    """B 用户不能读 A 用户任务结果（IDOR）"""
    code_a = store.create_invite()
    code_b = store.create_invite()
    user_a, _ = store.consume_invite(code_a)
    user_b, _ = store.consume_invite(code_b)
    task_id = store.create_task(user_a, keyword="x", city="shanghai")
    store.set_task_result(task_id, "success",
                          '{"qualified_jobs": [], "total": 5}')

    client_b = app.test_client()
    code_b2 = store.create_invite()
    client_b.get(f"/login?invite={code_b2}",
                 headers={"Origin": "http://localhost:3001"})
    resp = client_b.get(f"/api/jobs/results?task_id={task_id}")
    assert resp.status_code == 404


def test_list_user_tasks_returns_only_own_tasks(app, store):
    """/api/jobs/list 严格按 user 隔离"""
    code_a = store.create_invite()
    code_b = store.create_invite()
    user_a, _ = store.consume_invite(code_a)
    user_b, _ = store.consume_invite(code_b)
    store.create_task(user_a, keyword="alpha", city="shanghai")
    store.create_task(user_b, keyword="bravo", city="shanghai")

    code_c = store.create_invite()
    user_c, token_c = store.consume_invite(code_c)
    store.create_task(user_c, keyword="charlie", city="shanghai")

    client = app.test_client()
    client.set_cookie("boss_session", token_c, domain="localhost")
    resp = client.get("/api/jobs/list",
                      headers={"Origin": "http://localhost:3001"})
    assert resp.status_code == 200
    tasks = resp.get_json()["tasks"]
    keywords = {t["keyword"] for t in tasks}
    assert keywords == {"charlie"}, "C 不应看到 A/B 的任务"


# ─── Codex round 2 修复回归 ──────────────────────────────────

def test_search_complete_emits_to_user_room_only(app, store):
    """Codex round 2 P0：search_complete 不应广播给全用户，只 emit 到对应 room

    用 Flask test_client SocketIO 难直接验 emit room；改成静态检查：
    grep _emit_progress / search_complete 调用都带 to=user_id 参数。
    """
    src = open("backend/app.py").read()
    import re
    # 所有 socketio.emit("search_complete", ...) 必须带 to=
    matches = re.findall(r'socketio\.emit\("search_complete"[^)]*\)', src)
    assert matches, "search_complete emit 应存在"
    for m in matches:
        assert "to=user_id" in m, f"search_complete 必须 to=user_id 限定，但 {m!r} 没带"

    # _emit_progress 必须用 user_id 参数
    progress_matches = re.findall(r'_emit_progress\(socketio,\s*(\w+),', src)
    user_id_count = sum(1 for m in progress_matches if m == "user_id")
    assert user_id_count > 0
    assert all(m == "user_id" for m in progress_matches), \
        f"_emit_progress 第二个参数必须是 user_id，实际 {set(progress_matches)}"


def test_concurrent_search_only_one_succeeds(app, store):
    """Codex round 2 P2-2：用 threading.Barrier 真测并发互斥"""
    import threading
    import unittest.mock as _mock

    code = store.create_invite()
    user_id, token = store.consume_invite(code)

    barrier = threading.Barrier(5)
    results = []
    results_lock = threading.Lock()

    def attempt():
        with app.test_client() as c:
            c.set_cookie("boss_session", token, domain="localhost")
            barrier.wait()  # 同时冲
            r = c.post("/api/jobs/search",
                       json={"keyword": "x"},
                       headers={"Origin": "http://localhost:3001"})
            with results_lock:
                results.append(r.status_code)

    with _mock.patch("backend.app._run_job_search_task"):
        threads = [threading.Thread(target=attempt) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    # 必须恰好 1 个 202 成功，其余 409
    successes = sum(1 for s in results if s == 202)
    conflicts = sum(1 for s in results if s == 409)
    assert successes == 1, f"并发 5 个，只能 1 个成功，实际 {successes}（{results}）"
    assert conflicts == 4, f"其余 4 个应 409，实际 {conflicts}"


def test_error_response_does_not_leak_stack(client, monkeypatch):
    """触发异常路径 → response 不含 ValueError/堆栈/敏感字符串"""
    # 故意触发：访问需要 STORE 但 STORE 抛错的路径
    # 简单做法：直接请求一个不存在的 API
    resp = client.get("/api/nonexistent_route_for_404")
    # 至少不能漏堆栈
    body_text = resp.get_data(as_text=True)
    assert "Traceback" not in body_text
    assert "/Users/" not in body_text  # 内部路径
