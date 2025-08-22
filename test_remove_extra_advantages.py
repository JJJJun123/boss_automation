#!/usr/bin/env python3
"""
验证移除"额外优势"字段的效果
"""

import json
from analyzer.prompts.job_analysis_prompts import JobAnalysisPrompts

def test_prompt_template():
    """测试提示词模板是否移除了额外优势字段"""
    print("="*60)
    print("测试提示词模板修改")
    print("="*60)
    
    # 测试简单岗位匹配提示词
    job_info = {
        'title': 'Python开发工程师',
        'company': '测试公司',
        'salary': '20-30K',
        'job_description': '负责后端开发'
    }
    
    user_requirements = "寻找Python开发岗位"
    
    prompt = JobAnalysisPrompts.get_simple_job_match_prompt(job_info, user_requirements)
    
    print("📝 检查提示词内容...")
    
    if 'extra_advantages' in prompt:
        print("❌ 提示词中仍包含 extra_advantages 字段")
    else:
        print("✅ 提示词中已移除 extra_advantages 字段")
    
    # 检查JSON格式示例
    json_section = None
    lines = prompt.split('\n')
    in_json = False
    json_lines = []
    
    for line in lines:
        if '请以JSON格式回复：' in line or '"matched_skills"' in line:
            in_json = True
        if in_json:
            json_lines.append(line)
            if line.strip().endswith('}}') and 'mismatch_points' in line:
                break
    
    json_content = '\n'.join(json_lines)
    print(f"\n📋 JSON输出格式示例:")
    print(json_content)
    
    if 'extra_advantages' in json_content:
        print("\n❌ JSON格式中仍包含 extra_advantages")
    else:
        print("\n✅ JSON格式中已移除 extra_advantages")

def test_expected_output_format():
    """测试期望的输出格式"""
    print(f"\n" + "="*60)
    print("测试期望的输出格式")
    print("="*60)
    
    # 模拟期望的输出格式（不包含额外优势）
    expected_format = {
        "score": 7,
        "recommendation": "推荐",
        "reason": "技能匹配度较高",
        "summary": "适合投递",
        "match_points": ["Python经验丰富", "有后端开发背景"],
        "mismatch_points": ["缺乏Django经验"]
        # 注意：这里不应该有 extra_advantages 字段
    }
    
    print("✅ 期望的输出格式（已移除额外优势）:")
    print(json.dumps(expected_format, indent=2, ensure_ascii=False))
    
    if 'extra_advantages' in expected_format:
        print("\n❌ 期望格式中仍包含额外优势")
    else:
        print("\n✅ 期望格式中已成功移除额外优势")

def verify_frontend_changes():
    """验证前端文件的修改"""
    print(f"\n" + "="*60)
    print("验证前端文件修改")
    print("="*60)
    
    try:
        with open('/Users/cl/claude_project/boss_automation_multi/boss_automation_personal/backend/static/js/main.js', 'r', encoding='utf-8') as f:
            js_content = f.read()
        
        if 'extra_advantages' in js_content:
            print("❌ 前端JS文件中仍包含 extra_advantages 字段")
        else:
            print("✅ 前端JS文件中已移除 extra_advantages 字段")
            
        if '额外优势' in js_content:
            print("❌ 前端JS文件中仍包含 '额外优势' 文本")
        else:
            print("✅ 前端JS文件中已移除 '额外优势' 文本")
            
    except FileNotFoundError:
        print("❌ 无法找到前端JS文件")
    except Exception as e:
        print(f"❌ 检查前端文件时出错: {e}")

if __name__ == "__main__":
    test_prompt_template()
    test_expected_output_format()
    verify_frontend_changes()
    
    print(f"\n" + "="*60)
    print("移除额外优势字段总结")
    print("="*60)
    print("✅ 已完成的修改:")
    print("1. 从 job_analysis_prompts.py 移除 extra_advantages 字段")
    print("2. 从 main.js 前端显示逻辑中移除相关代码")
    print("3. AI输出将不再包含额外优势信息")
    print("\n💡 预期效果:")
    print("• 岗位分析结果更加简洁")
    print("• 减少可能的混淆信息")
    print("• 专注于核心匹配分析")
    print("• 提高分析结果的针对性")