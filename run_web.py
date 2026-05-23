#!/usr/bin/env python3
"""
Boss 直聘自动化 Web 启动脚本。

职责：检查 Python 依赖与配置文件 → 以子进程方式启动 backend/app.py → 等 Ctrl+C 退出。
实际监听地址由 backend/app.py 读取 config/app_config.yaml 的 web.host/web.port 决定，
不在本脚本里重复写死。
"""

import os
import sys
import subprocess
import time
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def check_dependencies() -> bool:
    """检查关键 Python 依赖是否就绪。返回 True=通过、False=缺依赖。"""
    try:
        import flask  # noqa: F401
        import flask_cors  # noqa: F401
        import flask_socketio  # noqa: F401
        import yaml  # noqa: F401
        logger.info("✅ 后端依赖检查通过")
        return True
    except ImportError as e:
        logger.error(f"❌ 缺少依赖: {e}")
        logger.error("请先 `conda activate boss_dev`，再 `pip install -r requirements.txt`")
        return False


def check_config() -> bool:
    """检查三层配置文件是否齐备。返回 True=通过、False=缺文件。"""
    config_dir = PROJECT_ROOT / "config"
    required = ["secrets.env", "app_config.yaml", "user_preferences.yaml"]
    missing = [f for f in required if not (config_dir / f).exists()]
    if missing:
        logger.error(f"❌ 缺少配置文件: {missing}")
        return False
    logger.info("✅ 配置文件检查通过")
    return True


def start_backend() -> "subprocess.Popen | None":
    """以子进程方式启动 backend/app.py（端口/host 由其自身读 web.* 配置决定）"""
    backend_script = PROJECT_ROOT / "backend" / "app.py"
    if not backend_script.exists():
        logger.error("❌ 找不到 backend/app.py")
        return None
    try:
        logger.info("🚀 启动后端服务…（监听地址由 app_config.yaml 的 web.host/web.port 决定）")
        return subprocess.Popen([sys.executable, str(backend_script)], cwd=str(PROJECT_ROOT))
    except Exception as e:
        logger.error(f"❌ 启动后端失败: {e}")
        return None


def main():
    """主流程：检查依赖与配置 → 起后端子进程 → 等 Ctrl+C 退出"""
    if not check_dependencies():
        sys.exit(1)
    if not check_config():
        sys.exit(1)

    backend_process = start_backend()
    if not backend_process:
        sys.exit(1)

    try:
        # backend/app.py 自己会打印实际监听 URL；这里只负责保持前台、转发 Ctrl+C
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 收到中断，正在停止后端服务…")
        backend_process.terminate()
        backend_process.wait()
        logger.info("✅ 已停止")


if __name__ == "__main__":
    main()
