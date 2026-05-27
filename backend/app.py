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
from flask_socketio import SocketIO, emit
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


# ─── 全局任务态（多用户改造前的临时方案，阶段 1 会按 task_id 入 SQLite） ──
_current_job = None
_current_spider = None
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
        global _current_job
        if _current_job and _current_job.get("status") == "running":
            return jsonify({"error": "已有任务正在运行中"}), 400

        data = request.get_json() or {}
        resume = store.get_resume(request.user_id)
        session_data = {
            "has_resume_data": resume is not None,
            "resume_data": resume,
            "user_id": request.user_id,
        }

        _current_job = {
            "status": "starting",
            "start_time": datetime.now(),
            "user_id": request.user_id,
        }

        thread = threading.Thread(
            target=_run_job_search_task,
            args=(data, session_data, socketio),
        )
        thread.daemon = True
        thread.start()
        return jsonify({"message": "任务已启动", "task_id": "default"})

    @app.route("/api/jobs/all")
    @require_user_id
    def get_all_jobs():
        global _current_job
        if _current_job and "analyzed_jobs" in _current_job:
            # 阶段 1 会按 user_id 隔离；本期仍单用户视图
            if _current_job.get("user_id") != request.user_id:
                return jsonify({"error": "没有可用的搜索结果"}), 404
            jobs = _current_job.get("analyzed_jobs", [])
            return jsonify({"jobs": jobs, "total": len(jobs)})
        return jsonify({"error": "没有可用的搜索结果，请先进行搜索"}), 404

    @app.route("/api/jobs/results")
    @require_user_id
    def get_job_results():
        if not _current_job:
            return jsonify({"error": "没有可用的搜索结果"}), 404
        if _current_job.get("user_id") != request.user_id:
            return jsonify({"error": "没有可用的搜索结果"}), 404
        return jsonify({
            "status": _current_job.get("status"),
            "results": _current_job.get("results", []),
            "stats": {
                "total_jobs": _current_job.get("total_jobs", 0),
                "analyzed_jobs": _current_job.get("analyzed_jobs_count", 0),
                "qualified_jobs": _current_job.get("qualified_jobs", 0),
            },
            "start_time": _current_job.get("start_time"),
            "end_time": _current_job.get("end_time"),
        })

    @app.route("/api/jobs/status")
    @require_user_id
    def get_job_status():
        if not _current_job:
            return jsonify({"status": "idle"})
        if _current_job.get("user_id") != request.user_id:
            return jsonify({"status": "idle"})
        return jsonify({
            "status": _current_job.get("status", "idle"),
            "start_time": _current_job.get("start_time"),
            "error": _current_job.get("error"),
        })

    # ─── SocketIO ───────────────────────────────────────────

    @socketio.on("connect")
    def handle_connect():
        logger.info("客户端已连接")
        emit("connected", {"message": "连接成功"})

    @socketio.on("disconnect")
    def handle_disconnect():
        logger.info("客户端已断开连接")

    return app


def _emit_progress(socketio, message, progress=None, data=None):
    """发送进度更新到前端"""
    payload = {
        "message": message,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
    if progress is not None:
        payload["progress"] = progress
    if data is not None:
        payload["data"] = data
    socketio.emit("progress_update", payload)


def _run_job_search_task(params, session_data, socketio):
    """在后台运行岗位搜索任务"""
    global _current_job, _current_spider
    try:
        _current_job["status"] = "running"
        _emit_progress(socketio, "🚀 开始初始化爬虫...", 5)

        deepseek_model = "deepseek-v4-flash"
        if _config_manager:
            deepseek_model = _config_manager.get_app_config(
                "ai.models.deepseek.model_name", "deepseek-v4-flash"
            )

        _emit_progress(socketio,
            f"🤖 AI模型: DeepSeek({deepseek_model}) - 筛选 + 匹配", 8)

        keyword = params.get("keyword", "AI算法工程师")
        max_jobs = params.get("max_jobs", 30)
        selected_city = params.get("city", "shanghai")

        task_logger.log_task_event(
            task_id=f"task-{_current_job['start_time'].timestamp()}",
            kind="task_start",
            user_id=session_data.get("user_id"),
            keyword=keyword,
            city=selected_city,
            max_jobs=max_jobs,
        )

        _emit_progress(socketio,
            f"🔍 搜索设置: {keyword} | {selected_city} | {max_jobs}个岗位", 10)
        _emit_progress(socketio, "🕷️ 启动统一爬虫引擎...", 20)

        jobs = asyncio.run(unified_search_jobs(keyword, selected_city, max_jobs))
        _emit_progress(socketio, f"🔍 搜索完成: 找到 {len(jobs)} 个岗位", 50)

        if not jobs:
            raise Exception("未找到任何岗位")

        if not session_data.get("has_resume_data"):
            _current_job.update({
                "status": "requires_resume",
                "end_time": datetime.now(),
                "results": [],
                "analyzed_jobs": [],
                "total_jobs": len(jobs),
                "analyzed_jobs_count": 0,
                "qualified_jobs": 0,
            })
            _emit_progress(socketio, "❌ 请先上传简历后再进行AI匹配", 100, {
                "requires_resume": True,
                "results": [],
                "all_jobs": [],
                "stats": {"total": len(jobs), "analyzed": 0, "qualified": 0},
            })
            socketio.emit("search_complete",
                {"status": "requires_resume", "message": "请先上传简历"})
            return

        _emit_progress(socketio, "🤖 启动AI两阶段分析...", 60)
        analyzer = EnhancedJobAnalyzer(
            extraction_provider="deepseek",
            analysis_provider="deepseek",
            model_name=deepseek_model,
            extraction_model_name=deepseek_model,
        )

        resume_text = session_data.get("resume_data", {}).get("resume_text", "")
        analyzed_jobs = analyzer.analyze_jobs(jobs, resume_text=resume_text, keyword=keyword)
        _emit_progress(socketio,
            f"📈 AI分析完成，{len(analyzed_jobs)} 个岗位通过筛选", 90)

        min_score = 0
        if _config_manager:
            min_score = _config_manager.get_ai_config().get("min_score", 0)
        qualified_jobs = [j for j in analyzed_jobs if j.get("score", 0) >= min_score]

        _current_job.update({
            "status": "completed",
            "end_time": datetime.now(),
            "results": qualified_jobs,
            "analyzed_jobs": analyzed_jobs,
            "total_jobs": len(analyzed_jobs),
            "analyzed_jobs_count": len(analyzed_jobs),
            "qualified_jobs": len(qualified_jobs),
        })

        _emit_progress(socketio,
            f"✅ 任务完成! 找到 {len(qualified_jobs)} 个合适岗位", 100, {
                "results": qualified_jobs,
                "all_jobs": analyzed_jobs,
                "stats": {
                    "total": len(analyzed_jobs),
                    "analyzed": len(analyzed_jobs),
                    "qualified": len(qualified_jobs),
                },
            })
        socketio.emit("search_complete", {"status": "success", "message": "搜索完成"})

        task_logger.log_task_event(
            task_id=f"task-{_current_job['start_time'].timestamp()}",
            kind="task_end",
            status="success",
            total=len(analyzed_jobs),
            qualified=len(qualified_jobs),
        )

    except Exception as e:
        logger.error(f"搜索任务失败 type={type(e).__name__}")
        task_logger.log_task_event(
            task_id=f"task-{_current_job['start_time'].timestamp()}",
            kind="task_failed",
            error_type=type(e).__name__,
        )
        _current_job.update({
            "status": "failed",
            "error": "任务执行出错",  # 不向前端暴露具体错误
            "end_time": datetime.now(),
        })
        _emit_progress(socketio, "❌ 任务执行出错，详情见后台日志", None)
        socketio.emit("search_complete",
            {"status": "failed", "message": "任务执行出错，详情见后台日志"})
    finally:
        if _current_spider:
            try:
                _current_spider.close()
            except Exception:
                pass
            _current_spider = None


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
