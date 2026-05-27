#!/usr/bin/env python3
"""
Boss直聘自动化Web应用后端
Flask + SocketIO 实现

阶段 0 集成（F3）：phase 0 安全模块全部接入：
- SECRET_KEY 从环境变量 fail-fast
- CORS 白名单（不含 *）
- /login?invite= 流程 + 防枚举拉黑
- @require_user_id 装饰所有数据 API
- 上传走 validate_resume_file
- 简历存 StateStore（不再全局变量），按 user_id 隔离 TTL 24h
- 异常走 safe_error_response 脱敏
- 任务日志走 task_logger（JSONL + journald）
"""

import asyncio
import ipaddress
import logging
import os
import sys
import threading
from datetime import datetime

from flask import Flask, request, jsonify, render_template, make_response
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from werkzeug.exceptions import HTTPException

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.config_manager import ConfigManager
from crawler.unified_crawler_interface import unified_search_jobs
from analyzer.enhanced_job_analyzer import EnhancedJobAnalyzer

from backend.auth import require_user_id, set_session_cookie, extract_user_id, COOKIE_NAME
from backend.security import load_secret_key, get_cors_origins, safe_error_response
from backend.upload_validator import validate_resume_file, UploadValidationError
from backend.rate_limiter import invite_limiter
from backend.task_logger import task_logger
from utils.state_store import StateStore


logger = logging.getLogger(__name__)


# 任务超时（秒）—— design.md 要求 5 分钟
_TASK_DEADLINE_SECONDS = 300

# 全局配置管理器（无状态，只读）
_config_manager = None


# 可信反代白名单（按 Codex round 2 P1-1：默认只信 loopback，
# 不把整个内网段当 proxy。生产 nginx 同机部署 → remote_addr=127.0.0.1）
_TRUSTED_PROXY_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
)


def _ip_in_trusted_proxy(ip_str: str) -> bool:
    """判断 ip 是否落入可信反代网段（用 ipaddress 严格解析，避免前缀字符串误判）"""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except (ValueError, TypeError):
        return False
    return any(ip_obj in net for net in _TRUSTED_PROXY_NETWORKS)


def _is_same_origin(req) -> bool:
    """校验请求来自同源（白名单 origin）—— 默认拒绝（Codex round 2 P1-2 修订）

    严格策略：必须提供 Origin 或 Referer 之一，且值在白名单内。
    无 Origin/Referer 一律拒绝——避免 `referrerpolicy=no-referrer` 顶层跳转
    绕过 CSRF 防护。

    例外：FLASK_ENV=development 时放行无头请求，便于本地 curl/调试。
    """
    allowed = set(get_cors_origins())
    origin = req.headers.get("Origin", "").strip()
    referer = req.headers.get("Referer", "").strip()

    if origin:
        return origin in allowed
    if referer:
        from urllib.parse import urlparse
        parsed = urlparse(referer)
        ref_origin = f"{parsed.scheme}://{parsed.netloc}"
        return ref_origin in allowed

    # 无 Origin 无 Referer：默认拒绝。仅 dev mode 放行（curl/调试）
    return os.environ.get("FLASK_ENV", "production").lower() == "development"


def _get_client_ip(req) -> str:
    """从请求拿真实客户端 IP，防伪造

    Codex P1-1 / round 2 P1-1 修订：
    - 默认 remote_addr（socket peer，无法伪造）
    - 只在 remote_addr ∈ 127.0.0.0/8 或 ::1（loopback only！）时信 X-Real-IP
    - 内网段（10/8、192.168/16、172.16-31）不再算 proxy → LAN 内攻击者
      不能靠发 X-Real-IP 绕过限流
    - 不信 X-Forwarded-For（首段可被任意伪造）
    - X-Real-IP 必须是单个合法 IP，多值或非法格式不信
    """
    direct = req.remote_addr or "unknown"
    if _ip_in_trusted_proxy(direct):
        real_ip_header = req.headers.get("X-Real-IP", "").strip()
        if real_ip_header and "," not in real_ip_header:
            try:
                ipaddress.ip_address(real_ip_header)
                return real_ip_header
            except ValueError:
                pass  # 非法格式不信，降级 remote_addr
    return direct


def create_app(store=None) -> Flask:
    """Flask 应用工厂

    参数：
        store - 可选 StateStore 注入（测试用临时 db）；不传则创建生产 data/state.db
    """
    global _config_manager

    app = Flask(__name__)

    # ─── SECRET_KEY 强制环境变量（fail-fast） ─────────────
    app.secret_key = load_secret_key()

    # ─── State store 初始化 ────────────────────────────────
    if store is None:
        store = StateStore(db_path=os.path.join(PROJECT_ROOT, "data/state.db"))
        store.init_schema()
    app.config["STORE"] = store

    # ─── CORS 白名单 ────────────────────────────────────────
    cors_origins = get_cors_origins()
    CORS(app, origins=cors_origins, supports_credentials=True)

    # ─── SocketIO（也走白名单，不再 *） ────────────────────
    socketio = SocketIO(
        app,
        cors_allowed_origins=cors_origins,
        async_mode="threading",
        ping_timeout=60,
        ping_interval=25,
    )
    app.extensions["socketio"] = socketio

    # ─── 配置 ───────────────────────────────────────────────
    if _config_manager is None:
        try:
            _config_manager = ConfigManager()
            logger.info("配置管理器初始化成功")
        except Exception as e:
            logger.error(f"配置管理器初始化失败: {e}")

    # ─── 全局错误处理 ──────────────────────────────────────
    @app.errorhandler(Exception)
    def _on_error(e):
        # Codex P2：HTTPException 应保留语义（404 / 405 / 415），不强转 500
        if isinstance(e, HTTPException):
            return jsonify({"error": e.description, "code": e.code}), e.code
        body, status = safe_error_response(e)
        return jsonify(body), status

    # ─── 路由 ───────────────────────────────────────────────

    @app.route("/")
    def serve_frontend():
        """前端页面。如果带 ?invite= 直接走登录"""
        invite = request.args.get("invite")
        if invite:
            return _do_login(invite)
        return render_template("index.html")

    @app.route("/login")
    def login_route():
        invite = request.args.get("invite", "").strip()
        if not invite:
            return jsonify({"error": "邀请码必填"}), 400
        return _do_login(invite)

    def _do_login(invite: str):
        """共用登录流程

        Codex P2-1：GET 消费邀请码有 CSRF 风险。最小防御：校验 Origin / Referer
        必须来自同源（白名单 origin），跨站发起拒绝。SameSite=Lax cookie 配合此
        校验阻止"诱导点击 magic link 覆盖登录态"攻击。
        """
        # 跨站请求拒绝（无 Origin/Referer 或来自非白名单）
        if not _is_same_origin(request):
            return jsonify({"error": "请从应用页面登录"}), 403

        ip = _get_client_ip(request)
        if invite_limiter.is_blacklisted(ip):
            return jsonify({"error": "尝试次数过多，请稍后再试"}), 429

        result = store.consume_invite(invite)
        if not result:
            invite_limiter.record_failure(ip)
            return jsonify({"error": "邀请码无效或已使用"}), 401

        user_id, token = result
        invite_limiter.record_success(ip)

        resp = make_response(jsonify({"success": True, "user_id": user_id}))
        set_session_cookie(resp, token)
        return resp

    @app.route("/api/health")
    def health_check():
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
        })

    @app.route("/api/auth/me")
    @require_user_id
    def whoami():
        """前端确认当前登录身份"""
        return jsonify({"user_id": request.user_id})

    @app.route("/api/config", methods=["GET"])
    @require_user_id
    def get_config():
        if not _config_manager:
            return jsonify({"error": "配置管理器未初始化"}), 500
        search_config = _config_manager.get_search_config()
        ai_config = _config_manager.get_ai_config()
        ai_config.pop("api_key", None)
        return jsonify({
            "search": search_config,
            "ai": ai_config,
            "app": _config_manager.get_app_config(),
        })

    @app.route("/api/upload_resume", methods=["POST"])
    @require_user_id
    def upload_resume():
        if "resume" not in request.files:
            return jsonify({"success": False, "error": "没有上传文件"}), 400
        file = request.files["resume"]
        if not file.filename:
            return jsonify({"success": False, "error": "未选择文件"}), 400

        # 阶段 0.7 校验：扩展名 + magic + ZIP 深度 + zip bomb 防护
        try:
            validate_resume_file(file)
        except UploadValidationError as e:
            return jsonify({"success": False, "error": str(e)}), 400

        # 解析
        try:
            filename_lower = file.filename.lower()
            if filename_lower.endswith(".pdf"):
                import PyPDF2
                from io import BytesIO
                pdf_reader = PyPDF2.PdfReader(BytesIO(file.read()))
                resume_text = "".join(p.extract_text() or "" for p in pdf_reader.pages)
            elif filename_lower.endswith((".docx", ".doc")):
                import docx
                from io import BytesIO
                doc = docx.Document(BytesIO(file.read()))
                resume_text = "\n".join(p.text for p in doc.paragraphs)
            else:
                return jsonify({"success": False, "error": "不支持的格式"}), 400

            if not resume_text.strip():
                return jsonify({"success": False, "error": "文件内容为空"}), 400
        except Exception as e:
            # 简历正文绝不落日志，仅记类型
            logger.error(f"简历解析失败 type={type(e).__name__}")
            return jsonify({"success": False, "error": "简历解析失败，请检查文件格式"}), 400

        # 仅长度入日志（不进正文）
        logger.info(f"简历解析成功，长度: {len(resume_text)} 字符")

        # 服务端 TTL 24h 隔离存储
        store.set_resume(
            user_id=request.user_id,
            resume_text=resume_text,
            filename=file.filename,
        )

        return jsonify({
            "success": True,
            "resume_data": {
                "name": file.filename.rsplit(".", 1)[0],
                "filename": file.filename,
                "length": len(resume_text),
                "upload_time": datetime.now().isoformat(),
            },
            "message": "简历上传成功",
        })

    @app.route("/api/delete_resume", methods=["POST"])
    @require_user_id
    def delete_resume():
        store.delete_resume(request.user_id)
        return jsonify({"success": True})

    @app.route("/api/resume/info", methods=["GET"])
    @require_user_id
    def get_resume_info():
        resume = store.get_resume(request.user_id)
        if not resume:
            return jsonify({"success": True, "has_resume": False, "message": "请先上传简历"})
        return jsonify({
            "success": True,
            "has_resume": True,
            "resume_info": {
                "name": (resume.get("filename") or "用户").rsplit(".", 1)[0],
                "filename": resume.get("filename", ""),
                "intentions": resume.get("intentions", []),
            },
        })

    @app.route("/api/resume/update_intentions", methods=["POST"])
    @require_user_id
    def update_job_intentions():
        data = request.get_json() or {}
        intentions = data.get("intentions", [])
        if not store.update_resume_intentions(request.user_id, intentions):
            return jsonify({"success": False, "error": "请先上传简历"}), 400
        return jsonify({"success": True, "message": "求职意向已更新"})

    @app.route("/api/jobs/search", methods=["POST"])
    @require_user_id
    def start_job_search():
        """启动搜索任务

        Codex P1-2：用 partial unique index 强制每用户最多 1 个 active task。
        create_task 抛 IntegrityError → 409。不再依赖应用层 check-then-insert
        （并发竞态会让两个 task 同时插）。
        """
        data = request.get_json() or {}
        keyword = data.get("keyword", "AI算法工程师")
        city = data.get("city", "shanghai")
        max_jobs = data.get("max_jobs", 30)

        import sqlite3 as _sqlite3
        try:
            task_id = store.create_task(request.user_id, keyword=keyword, city=city)
        except _sqlite3.IntegrityError as e:
            # Codex round 2 P2-1：仅当 tasks.user_id 上 unique 冲突时当作 active 任务
            # 其它完整性错误（FK 违约等）重抛，不被静默吞
            err_msg = str(e).lower()
            if "unique" in err_msg and "tasks.user_id" in err_msg:
                existing = store.get_user_active_task(request.user_id)
                return jsonify({
                    "error": "已有任务正在运行中",
                    "task_id": existing["task_id"] if existing else None,
                }), 409
            raise

        resume = store.get_resume(request.user_id)
        session_data = {
            "has_resume_data": resume is not None,
            "resume_data": resume,
            "user_id": request.user_id,
            "task_id": task_id,
            "keyword": keyword,
            "city": city,
            "max_jobs": max_jobs,
        }

        thread = threading.Thread(
            target=_run_job_search_task,
            args=(session_data, socketio, store),
        )
        thread.daemon = True
        thread.start()
        return jsonify({"message": "任务已启动", "task_id": task_id}), 202

    @app.route("/api/jobs/cancel", methods=["POST"])
    @require_user_id
    def cancel_job():
        """用户主动取消任务

        Codex P1-2 / 阶段 1.4：用户必须能 cancel；后台线程通过查 SQLite
        status='cancelled' 检测取消信号并清理。
        """
        data = request.get_json() or {}
        task_id = data.get("task_id")
        if not task_id:
            return jsonify({"error": "task_id 必填"}), 400
        if store.cancel_task(task_id, request.user_id):
            return jsonify({"success": True})
        return jsonify({"error": "任务不存在或已结束"}), 404

    @app.route("/api/jobs/all")
    @require_user_id
    def get_all_jobs():
        """取指定 task 的所有岗位（含被筛掉的）

        必须传 task_id；不传则取最新**完成且有结果**的任务
        （Codex P2-2：不能 fallback 到 cancelled/failed）。
        """
        task_id = request.args.get("task_id")
        if not task_id:
            recent = store.get_latest_completed_task(request.user_id)
            if not recent:
                return jsonify({"error": "没有可用的搜索结果"}), 404
            task_id = recent["task_id"]

        task = store.get_task(task_id, user_id=request.user_id)
        if not task or not task.get("result_json"):
            return jsonify({"error": "没有可用的搜索结果"}), 404

        import json as _json
        try:
            payload = _json.loads(task["result_json"])
        except (ValueError, TypeError):
            return jsonify({"error": "结果解析失败"}), 500
        jobs = payload.get("analyzed_jobs", payload.get("jobs", []))
        return jsonify({"jobs": jobs, "total": len(jobs)})

    @app.route("/api/jobs/results")
    @require_user_id
    def get_job_results():
        task_id = request.args.get("task_id")
        if not task_id:
            recent = store.get_latest_completed_task(request.user_id)
            if not recent:
                return jsonify({"error": "没有可用的搜索结果"}), 404
            task_id = recent["task_id"]

        task = store.get_task(task_id, user_id=request.user_id)
        if not task:
            return jsonify({"error": "没有可用的搜索结果"}), 404

        import json as _json
        result = {}
        if task.get("result_json"):
            try:
                result = _json.loads(task["result_json"])
            except (ValueError, TypeError):
                result = {}
        return jsonify({
            "task_id": task_id,
            "status": task.get("status"),
            "results": result.get("qualified_jobs", []),
            "stats": {
                "total_jobs": result.get("total", 0),
                "analyzed_jobs": result.get("analyzed_count", 0),
                "qualified_jobs": result.get("qualified_count", 0),
            },
            "start_time": task.get("created_at"),
            "end_time": task.get("finished_at"),
        })

    @app.route("/api/jobs/status")
    @require_user_id
    def get_job_status():
        task_id = request.args.get("task_id")
        if task_id:
            task = store.get_task(task_id, user_id=request.user_id)
            if not task:
                return jsonify({"status": "idle"})
            return jsonify({
                "task_id": task_id,
                "status": task.get("status", "idle"),
                "progress": task.get("progress", 0),
                "start_time": task.get("created_at"),
            })
        # 无 task_id 查最新
        active = store.get_user_active_task(request.user_id)
        if active:
            return jsonify({
                "task_id": active["task_id"],
                "status": active["status"],
                "progress": active.get("progress", 0),
                "start_time": active.get("created_at"),
            })
        return jsonify({"status": "idle"})

    @app.route("/api/jobs/list")
    @require_user_id
    def list_jobs():
        """该用户最近的任务列表（用于历史/刷新页面恢复）"""
        tasks = store.list_user_tasks(request.user_id, limit=10)
        return jsonify({
            "tasks": [{
                "task_id": t["task_id"],
                "keyword": t.get("keyword"),
                "city": t.get("city"),
                "status": t.get("status"),
                "created_at": t.get("created_at"),
            } for t in tasks]
        })

    # ─── SocketIO ───────────────────────────────────────────

    @socketio.on("connect")
    def handle_connect():
        """连接时按 user_id 加入私有 room

        Codex round 2 P0：原全局 broadcast 会把 A 的结果推给 B。
        改成每个连接根据 cookie 解出的 user_id 加入对应 room，
        emit 时 to=user_id 仅推给该用户的活跃连接。
        未登录连接（无 cookie）不加任何 room，仅能接收 connected ack。
        """
        user_id = extract_user_id(request, store)
        if user_id:
            join_room(user_id)
            logger.info(f"客户端已连接 + 加入 room user_id={user_id}")
        else:
            logger.info("客户端已连接（未登录，不加入用户 room）")
        emit("connected", {"message": "连接成功"})

    @socketio.on("disconnect")
    def handle_disconnect():
        logger.info("客户端已断开连接")

    return app


def _emit_progress(socketio, user_id, task_id, message, progress=None, data=None):
    """发送进度更新 — 仅推给该 user_id room（Codex round 2 P0：防跨用户泄露）"""
    payload = {
        "task_id": task_id,
        "message": message,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
    if progress is not None:
        payload["progress"] = progress
    if data is not None:
        payload["data"] = data
    socketio.emit("progress_update", payload, to=user_id)


def _check_cancelled(store, task_id: str, user_id: str) -> bool:
    """检查任务是否被用户取消（用户调 /api/jobs/cancel 后 status=cancelled）"""
    task = store.get_task(task_id, user_id=user_id)
    return bool(task) and task.get("status") == "cancelled"


def _check_deadline(started_at: datetime) -> bool:
    """检查任务整体是否已超过 deadline（5 分钟）

    Codex P1-4：原 wait_for 只包爬虫，不包 AI 分析。改成全任务 checkpoint
    检查 elapsed time。
    """
    return (datetime.now() - started_at).total_seconds() > _TASK_DEADLINE_SECONDS


def _bail_if_cancelled_or_timeout(store, socketio, task_id: str, user_id: str,
                                   started: datetime) -> bool:
    """统一的 abort checkpoint。返回 True 表示已 abort，调用方应直接 return

    Codex round 2 P1-2：原 _check_deadline 命中后只 return，task 留 running
    挡用户新任务。这里超时时主动 set_task_result('failed') + emit。
    cancel 时不动 DB（status 已是 cancelled），仅 emit 终态便于前端关闭等待。
    """
    if _check_cancelled(store, task_id, user_id):
        # cancel 已写 DB，emit 让前端 UI 收到关闭信号
        try:
            socketio.emit("search_complete",
                {"task_id": task_id, "status": "cancelled", "message": "已取消"},
                to=user_id)
        except Exception:
            pass
        return True
    if _check_deadline(started):
        # 超时主动写 failed 终态（被 status guard 保护，cancel 已发生时不覆盖）
        import json as _json
        store.set_task_result(task_id, "failed",
            _json.dumps({"error": "timeout",
                        "deadline_sec": _TASK_DEADLINE_SECONDS}, ensure_ascii=False))
        try:
            socketio.emit("search_complete",
                {"task_id": task_id, "status": "failed", "message": "任务超时"},
                to=user_id)
        except Exception:
            pass
        return True
    return False


def _run_job_search_task(session_data, socketio, store):
    """后台运行岗位搜索任务

    SQLite tasks 表持久化（阶段 1.4 + 1.6）：
    - 状态流转 pending → running → success/failed/cancelled
    - 5 分钟 deadline（design.md 要求）
    - 用户可调 /api/jobs/cancel 中途停
    - 结果 JSON 落 result_json 字段，TTL 24h（支持刷新页面恢复）
    """
    task_id = session_data["task_id"]
    user_id = session_data["user_id"]
    keyword = session_data["keyword"]
    city = session_data["city"]
    max_jobs = session_data["max_jobs"]

    import json as _json
    started = datetime.now()
    try:
        # set_task_status 现返回 bool；False 表示已被 cancel（不能改回 running）
        if not store.set_task_status(task_id, "running", progress=5):
            return  # 用户已 cancel
        _emit_progress(socketio, user_id, task_id, "🚀 开始初始化爬虫...", 5)

        deepseek_model = "deepseek-v4-flash"
        if _config_manager:
            deepseek_model = _config_manager.get_app_config(
                "ai.models.deepseek.model_name", "deepseek-v4-flash"
            )

        task_logger.log_task_event(
            task_id=task_id, kind="task_start",
            user_id=user_id, keyword=keyword, city=city, max_jobs=max_jobs,
        )

        _emit_progress(socketio, user_id, task_id,
            f"🤖 AI模型: DeepSeek({deepseek_model})", 8)
        _emit_progress(socketio, user_id, task_id,
            f"🔍 搜索设置: {keyword} | {city} | {max_jobs}个岗位", 10)

        if _bail_if_cancelled_or_timeout(store, socketio, task_id, user_id, started):
            return

        if not store.set_task_status(task_id, "running", progress=20):
            return
        _emit_progress(socketio, user_id, task_id, "🕷️ 启动统一爬虫引擎...", 20)

        # 爬虫层超时 = 剩余预算（不是固定 5 分钟）
        remaining = _TASK_DEADLINE_SECONDS - (datetime.now() - started).total_seconds()
        async def _crawl_with_timeout():
            return await asyncio.wait_for(
                unified_search_jobs(keyword, city, max_jobs),
                timeout=max(remaining, 1),
            )
        jobs = asyncio.run(_crawl_with_timeout())
        _emit_progress(socketio, user_id, task_id, f"🔍 搜索完成: 找到 {len(jobs)} 个岗位", 50)

        if _bail_if_cancelled_or_timeout(store, socketio, task_id, user_id, started):
            return

        if not jobs:
            raise RuntimeError("未找到任何岗位")

        if not session_data.get("has_resume_data"):
            result_payload = {
                "qualified_jobs": [],
                "analyzed_jobs": [],
                "total": len(jobs),
                "analyzed_count": 0,
                "qualified_count": 0,
                "requires_resume": True,
            }
            # Codex round 2 P1-4：尊重 set_task_result 返回值；False=用户已 cancel
            if not store.set_task_result(task_id, "requires_resume",
                                         _json.dumps(result_payload, ensure_ascii=False)):
                return  # cancel 优先生效，不发 requires_resume 终态
            _emit_progress(socketio, user_id, task_id, "❌ 请先上传简历后再进行AI匹配", 100, {
                "requires_resume": True,
                "results": [],
                "all_jobs": [],
                "stats": {"total": len(jobs), "analyzed": 0, "qualified": 0},
            })
            socketio.emit("search_complete",
                {"task_id": task_id, "status": "requires_resume",
                 "message": "请先上传简历"}, to=user_id)
            return

        if _bail_if_cancelled_or_timeout(store, socketio, task_id, user_id, started):
            return
        if not store.set_task_status(task_id, "running", progress=60):
            return
        _emit_progress(socketio, user_id, task_id, "🤖 启动AI两阶段分析...", 60)

        analyzer = EnhancedJobAnalyzer(
            extraction_provider="deepseek",
            analysis_provider="deepseek",
            model_name=deepseek_model,
            extraction_model_name=deepseek_model,
        )
        resume_text = session_data.get("resume_data", {}).get("resume_text", "")
        analyzed_jobs = analyzer.analyze_jobs(jobs, resume_text=resume_text, keyword=keyword)
        _emit_progress(socketio, user_id, task_id,
            f"📈 AI分析完成，{len(analyzed_jobs)} 个岗位通过筛选", 90)

        if _bail_if_cancelled_or_timeout(store, socketio, task_id, user_id, started):
            return

        min_score = 0
        if _config_manager:
            min_score = _config_manager.get_ai_config().get("min_score", 0)
        qualified_jobs = [j for j in analyzed_jobs if j.get("score", 0) >= min_score]

        result_payload = {
            "qualified_jobs": qualified_jobs,
            "analyzed_jobs": analyzed_jobs,
            "total": len(analyzed_jobs),
            "analyzed_count": len(analyzed_jobs),
            "qualified_count": len(qualified_jobs),
        }
        # set_task_result 现返回 bool；False = 用户已 cancel 不能写终态
        if not store.set_task_result(task_id, "success",
                                     _json.dumps(result_payload, ensure_ascii=False)):
            return  # 用户 cancel 优先生效

        _emit_progress(socketio, user_id, task_id,
            f"✅ 任务完成! 找到 {len(qualified_jobs)} 个合适岗位", 100, {
                "results": qualified_jobs,
                "all_jobs": analyzed_jobs,
                "stats": {
                    "total": len(analyzed_jobs),
                    "analyzed": len(analyzed_jobs),
                    "qualified": len(qualified_jobs),
                },
            })
        socketio.emit("search_complete",
            {"task_id": task_id, "status": "success", "message": "搜索完成"}, to=user_id)

        task_logger.log_task_event(
            task_id=task_id, kind="task_end", status="success",
            total=len(analyzed_jobs), qualified=len(qualified_jobs),
            duration_sec=(datetime.now() - started).total_seconds(),
        )

    except asyncio.TimeoutError:
        logger.warning(f"task {task_id} timed out after {_TASK_DEADLINE_SECONDS}s")
        # Codex P1-4：尊重返回值；cancel 已发生时不覆盖
        if store.set_task_result(task_id, "failed",
                _json.dumps({"error": "timeout",
                            "deadline_sec": _TASK_DEADLINE_SECONDS}, ensure_ascii=False)):
            task_logger.log_task_event(task_id=task_id, kind="task_failed",
                                       error_type="TimeoutError")
            _emit_progress(socketio, user_id, task_id,
                f"⏰ 任务超时（{_TASK_DEADLINE_SECONDS // 60} 分钟），已中断", None)
            socketio.emit("search_complete",
                {"task_id": task_id, "status": "failed", "message": "任务超时"}, to=user_id)
    except Exception as e:
        logger.error(f"搜索任务失败 type={type(e).__name__}")
        if store.set_task_result(task_id, "failed",
                _json.dumps({"error": "internal", "type": type(e).__name__})):
            task_logger.log_task_event(task_id=task_id, kind="task_failed",
                                       error_type=type(e).__name__)
            _emit_progress(socketio, user_id, task_id, "❌ 任务执行出错，详情见后台日志", None)
            socketio.emit("search_complete",
                {"task_id": task_id, "status": "failed", "message": "任务执行出错"}, to=user_id)


# ─── 主入口 ────────────────────────────────────────────────

if __name__ == "__main__":
    # 配置日志
    LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))

    # 创建 app（会触发 SECRET_KEY fail-fast 校验）
    app = create_app()

    web_cfg = _config_manager.get_app_config("web", {}) if _config_manager else {}
    host = web_cfg.get("host", "127.0.0.1")
    port = int(web_cfg.get("port", 3001))
    debug = bool(web_cfg.get("debug", False))

    socketio = app.extensions["socketio"]
    logger.info(f"启动 Boss直聘 → http://{host}:{port}")
    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
