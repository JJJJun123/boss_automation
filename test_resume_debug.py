#!/usr/bin/env python3
"""
简历分析调试脚本
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_resume_analyzer():
    """测试简历分析器"""
    print("=== 开始测试简历分析器 ===")
    
    try:
        from analyzer.resume.resume_analyzer import ResumeAnalyzer
        print("✅ 成功导入ResumeAnalyzer")
        
        # 创建分析器实例
        analyzer = ResumeAnalyzer(ai_provider='deepseek')
        print("✅ 成功创建分析器实例")
        
        # 测试简历文本
        test_resume = """
        姓名：张三
        教育背景：北京大学计算机科学学士
        工作经验：
        - 阿里巴巴软件工程师（2020-2023）
        - 负责后端系统开发
        技能：Python, Java, MySQL
        """
        
        print("开始分析测试简历...")
        result = analyzer.analyze_resume(test_resume)
        print("✅ 分析完成")
        print(f"结果类型: {type(result)}")
        print(f"结果键: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 尝试写入错误日志
        try:
            with open("debug_error.txt", "w", encoding='utf-8') as f:
                f.write(f"错误: {e}\n")
                f.write("完整堆栈:\n")
                f.write(traceback.format_exc())
            print("错误信息已写入 debug_error.txt")
        except:
            pass

if __name__ == "__main__":
    test_resume_analyzer()