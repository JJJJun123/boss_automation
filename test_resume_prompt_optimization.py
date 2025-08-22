#!/usr/bin/env python3
"""
测试优化后的简历分析提示词效果
"""

from analyzer.resume.resume_analyzer import ResumeAnalyzer

def test_resume_analysis():
    """测试严格简历分析"""
    
    # 模拟简历文本
    resume_text = """
    个人信息：
    姓名：张三
    学历：本科，计算机科学与技术，北京理工大学，2018届
    
    工作经历：
    2018.07 - 2021.05  某传统软件公司  Java开发工程师
    - 负责企业管理系统的后端开发
    - 使用Spring Boot开发RESTful API
    - 参与数据库设计和优化
    - 维护老系统，修复bug
    
    2021.06 - 至今     某互联网公司  高级Java开发工程师  
    - 负责用户中心微服务开发
    - 参与系统架构设计和技术选型
    - 使用Spring Cloud搭建微服务体系
    - 优化数据库性能，QPS提升30%
    
    技能：
    - Java、Spring Boot、Spring Cloud
    - MySQL、Redis
    - Docker基础
    - 了解Python、前端基础
    """
    
    print("="*60)
    print("测试优化后的简历分析提示词")
    print("="*60)
    
    try:
        analyzer = ResumeAnalyzer('deepseek')
        
        print(f"\n📋 分析简历（长度: {len(resume_text)}字符）")
        result = analyzer.analyze_resume(resume_text)
        
        print("\n✅ 分析结果:")
        print(f"优势数量: {len(result.get('strengths', []))}")
        print(f"劣势数量: {len(result.get('weaknesses', []))}")
        print(f"推荐岗位数量: {len(result.get('recommended_positions', []))}")
        
        print("\n🎯 优势分析:")
        for i, strength in enumerate(result.get('strengths', []), 1):
            print(f"{i}. {strength}")
            
        print("\n⚠️  劣势分析:")
        for i, weakness in enumerate(result.get('weaknesses', []), 1):
            print(f"{i}. {weakness}")
            
        print("\n💼 推荐岗位:")
        for i, position in enumerate(result.get('recommended_positions', []), 1):
            print(f"{i}. {position}")
            
        # 检查技能提取
        skills = result.get('resume_core', {}).get('skills', {})
        print(f"\n🛠️  提取的硬技能: {skills.get('hard_skills', [])}")
        print(f"🤝 提取的软技能: {skills.get('soft_skills', [])}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")

def compare_analysis_quality():
    """比较分析质量"""
    print("\n" + "="*60)
    print("分析质量期望对比")
    print("="*60)
    
    print("\n📊 优化前 vs 优化后预期:")
    
    print("\n【优势分析】")
    print("❌ 优化前: '有丰富的Java开发经验'")
    print("✅ 优化后: '精通Spring生态，有5年Java后端实战经验，主导过用户中心微服务架构设计'")
    
    print("\n【劣势分析】") 
    print("❌ 优化前: '可以进一步学习新技术'")
    print("✅ 优化后: '缺乏大型分布式系统经验，Docker仅为基础水平，前端能力薄弱'")
    
    print("\n【岗位推荐】")
    print("❌ 优化前: 'Java开发工程师', 'Spring开发工程师'")
    print("✅ 优化后: 'Java后端开发工程师（中高级）', '微服务架构工程师', 'Spring Cloud开发专家'")

if __name__ == "__main__":
    test_resume_analysis()
    compare_analysis_quality()
    print("\n✅ 简历分析提示词优化完成！")
    print("\n主要改进:")
    print("1. 角色从'全能型HR'改为'技术招聘专家'")
    print("2. 技能分级：精通(3年+) > 熟练(1-3年) > 了解")
    print("3. 优势必须基于具体项目成果和量化指标")
    print("4. 劣势明确指出技能缺口和经验短板")
    print("5. 岗位推荐务实匹配当前能力水平")
    print("6. JSON结构保持不变，前端无需修改")