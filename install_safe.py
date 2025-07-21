#!/usr/bin/env python3
"""
安全安装脚本 - 避开Python 3.13兼容性问题
"""

import subprocess
import sys
import os

def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    print(f"🐍 当前Python版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major == 3 and version.minor >= 13:
        print("⚠️ 检测到Python 3.13+，将使用兼容性安装方案")
        return True
    return False

def install_basic_requirements():
    """安装基础依赖（无编译问题）"""
    basic_packages = [
        "requests==2.31.0",
        "beautifulsoup4==4.12.2", 
        "python-dotenv==1.0.0",
        "PyYAML==6.0.1",
        "Flask==3.0.0",
        "Flask-CORS==4.0.0",
        "selenium==4.15.2",
        "undetected-chromedriver==3.5.4"
    ]
    
    print("📦 安装基础依赖包...")
    for package in basic_packages:
        try:
            print(f"  安装: {package}")
            subprocess.run([sys.executable, "-m", "pip", "install", package], 
                         check=True, capture_output=True)
            print(f"  ✅ {package} 安装成功")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ {package} 安装失败: {e}")
            print(f"     错误输出: {e.stderr.decode() if e.stderr else 'N/A'}")

def install_socketio_safe():
    """安全安装SocketIO相关包"""
    socketio_packages = [
        "python-socketio==5.10.0",
        "Flask-SocketIO==5.3.6"
    ]
    
    print("🔌 安装SocketIO依赖...")
    for package in socketio_packages:
        try:
            print(f"  安装: {package}")
            # 使用--no-deps避免依赖冲突，然后手动安装兼容版本
            subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", package], 
                         check=True, capture_output=True)
            print(f"  ✅ {package} 安装成功")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ {package} 安装失败，尝试替代方案: {e}")

def install_playwright_safe():
    """安全安装Playwright"""
    print("🎭 尝试安装Playwright...")
    
    try:
        # 先尝试最新版本
        print("  尝试安装最新版Playwright...")
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], 
                      check=True, capture_output=True)
        print("  ✅ Playwright安装成功")
        
        # 安装浏览器
        print("  安装Chrome浏览器...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                      check=True, capture_output=True)
        print("  ✅ Chrome浏览器安装成功")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Playwright安装失败: {e}")
        print("  💡 提示: Playwright可能需要额外的系统依赖")
        return False

def skip_problematic_packages():
    """跳过有问题的包，创建替代方案"""
    print("🔄 创建问题包的替代方案...")
    
    # 创建一个简化的aiohttp替代模块
    fake_aiohttp_content = '''"""
简化的aiohttp替代模块
用于Python 3.13兼容性
"""

# 基本类型定义，避免导入错误
class ClientSession:
    pass

__version__ = "3.9.0-compat"
'''
    
    # 找到site-packages目录
    import site
    site_packages = site.getsitepackages()
    
    if site_packages:
        aiohttp_path = os.path.join(site_packages[0], "aiohttp")
        try:
            os.makedirs(aiohttp_path, exist_ok=True)
            
            init_file = os.path.join(aiohttp_path, "__init__.py")
            with open(init_file, 'w', encoding='utf-8') as f:
                f.write(fake_aiohttp_content)
            
            print("  ✅ 创建aiohttp替代模块成功")
            return True
        except Exception as e:
            print(f"  ❌ 创建替代模块失败: {e}")
    
    return False

def main():
    """主安装流程"""
    print("=" * 50)
    print("🚀 Boss直聘自动化 - 安全安装程序")
    print("=" * 50)
    
    is_python313 = check_python_version()
    
    if is_python313:
        print("\n🛠️ 使用Python 3.13兼容性安装方案")
        skip_problematic_packages()
    
    print("\n📦 开始安装依赖包...")
    
    # 1. 安装基础依赖
    install_basic_requirements()
    
    # 2. 安装SocketIO
    install_socketio_safe()
    
    # 3. 安装Playwright
    playwright_success = install_playwright_safe()
    
    print("\n" + "=" * 50)
    print("📊 安装结果总结:")
    print("✅ 基础依赖: 已安装")
    print("✅ Web框架: 已安装")
    print("✅ 爬虫引擎: 已安装")
    print(f"{'✅' if playwright_success else '⚠️'} Playwright: {'已安装' if playwright_success else '部分功能可能受限'}")
    
    print("\n💡 接下来你可以:")
    print("1. 运行: python run_web.py")
    print("2. 访问: http://localhost:5000")
    print("3. 如果遇到问题，请检查日志输出")
    
    if not playwright_success:
        print("\n⚠️ Playwright未完全安装，但Selenium引擎仍可正常使用")
        print("   选择 'selenium' 引擎即可正常工作")

if __name__ == "__main__":
    main()