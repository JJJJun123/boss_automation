#!/usr/bin/env python3
"""
调试session错误的脚本
在出现session错误时运行这个脚本
"""

import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_flask_imports():
    """检查所有导入的模块中是否有Flask相关的session使用"""
    print("🔍 检查Flask相关导入...")
    
    import importlib
    import pkgutil
    
    # 检查analyzer目录下所有模块
    analyzer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analyzer')
    
    for importer, modname, ispkg in pkgutil.walk_packages([analyzer_path], 'analyzer.'):
        try:
            module = importlib.import_module(modname)
            module_file = getattr(module, '__file__', '')
            
            if hasattr(module, 'session') or 'flask' in str(module).lower():
                print(f"⚠️  发现可能的Flask相关模块: {modname} - {module_file}")
                
        except Exception as e:
            # 忽略导入错误
            pass

def check_for_session_usage():
    """搜索所有Python文件中的session使用"""
    print("\n🔍 搜索session使用...")
    
    import subprocess
    
    try:
        # 使用grep搜索session使用
        result = subprocess.run([
            'grep', '-r', '--include=*.py', 
            'session\[', 
            '/Users/cl/claude_project/boss_automation_multi/boss_automation_personal/'
        ], capture_output=True, text=True)
        
        if result.stdout:
            print("发现以下session使用:")
            for line in result.stdout.split('\n'):
                if line.strip():
                    print(f"  {line}")
        else:
            print("✅ 未发现session[]使用")
            
    except Exception as e:
        print(f"搜索失败: {e}")

def suggest_fixes():
    """建议修复方案"""
    print(f"\n💡 建议的调试步骤:")
    print("1. 重启Web应用，清除所有session状态")
    print("2. 在浏览器中清除所有cookies和缓存")
    print("3. 检查是否有多个Flask应用实例在运行")
    print("4. 确保没有在导入时就执行session相关代码")
    
    print(f"\n🔧 临时修复方案:")
    print("1. 修改backend/app.py，在run_job_search_task中添加更详细的错误处理")
    print("2. 在线程函数中添加Flask应用上下文")
    print("3. 将所有session相关操作移到主线程中完成")

if __name__ == "__main__":
    print("🐛 Session错误调试脚本")
    print("=" * 50)
    
    check_flask_imports()
    check_for_session_usage()
    suggest_fixes()
    
    print("\n" + "=" * 50)
    print("📝 如果错误仍然存在，请:")
    print("1. 停止当前运行的Web应用")
    print("2. 重新启动: python run_web.py")
    print("3. 在浏览器中刷新页面")
    print("4. 重新尝试岗位搜索")