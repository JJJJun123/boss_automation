#!/usr/bin/env python3
"""
Boss直聘自动化Web版本启动脚本
"""

import os
import sys
import subprocess
import time
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies():
    """检查依赖是否安装"""
    try:
        import flask
        import flask_cors
        import flask_socketio
        import yaml
        logger.info("✅ 后端依赖检查通过")
        return True
    except ImportError as e:
        logger.error(f"❌ 缺少依赖: {e}")
        logger.info("请运行: pip install -r requirements.txt")
        return False

def check_config():
    """检查配置文件"""
    config_dir = Path("config")
    required_files = [
        "secrets.env",
        "app_config.yaml", 
        "user_preferences.yaml"
    ]
    
    missing_files = []
    for file in required_files:
        if not (config_dir / file).exists():
            missing_files.append(file)
    
    if missing_files:
        logger.error(f"❌ 缺少配置文件: {missing_files}")
        return False
    
    logger.info("✅ 配置文件检查通过")
    return True

def start_backend():
    """启动后端服务"""
    logger.info("🚀 启动后端服务...")
    backend_script = Path("backend/app.py")
    
    if not backend_script.exists():
        logger.error("❌ 找不到后端启动脚本")
        return None
    
    try:
        process = subprocess.Popen([
            sys.executable, str(backend_script)
        ], cwd=os.getcwd())
        logger.info("✅ 后端服务启动成功，端口: 5000")
        return process
    except Exception as e:
        logger.error(f"❌ 启动后端服务失败: {e}")
        return None

def check_frontend():
    """检查前端是否存在"""
    frontend_dir = Path("frontend")
    package_json = frontend_dir / "package.json"
    
    if not package_json.exists():
        logger.warning("⚠️ 前端项目不存在，仅启动后端服务")
        return False
    
    return True

def main():
    """主函数"""
    logger.info("🍎 Boss直聘自动化Web版本")
    logger.info("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查配置
    if not check_config():
        sys.exit(1)
    
    # 启动后端
    backend_process = start_backend()
    if not backend_process:
        sys.exit(1)
    
    # 检查前端
    has_frontend = check_frontend()
    
    try:
        logger.info("\n🌟 服务已启动!")
        logger.info(f"📱 Web界面: http://localhost:5000")
        logger.info(f"🔗 API文档: http://localhost:5000/api/health")
        
        if not has_frontend:
            logger.info("\n💡 提示: 当前只有后端服务，如需完整Web界面请安装前端依赖")
            logger.info("   cd frontend && npm install && npm run build")
        
        logger.info("\n按 Ctrl+C 停止服务")
        
        # 等待用户中断
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\n🛑 正在停止服务...")
        backend_process.terminate()
        backend_process.wait()
        logger.info("✅ 服务已停止")

if __name__ == "__main__":
    main()